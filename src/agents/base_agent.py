# Define basic data structures for clarity
import abc
import asyncio
import contextlib
import json
import uuid  # Added import
from dataclasses import field  # Keep field for default_factory if needed with Pydantic
from typing import Any, Callable, Dict, List, Optional, TypedDict

from adalflow.core import Generator
from adalflow.core.model_client import ModelClient
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import trace
from opentelemetry.context import attach, detach
from opentelemetry.trace import Span, Status, StatusCode
from pydantic import BaseModel, Field  # Import BaseModel and Field

from src.agents.models import AgentResponse, ToolCall, ToolResult
from src.config.constants import GEMINI_20_FLASH
from src.memory.base_memory import BaseMemory
from src.observability.context import get_conversation_id, set_conversation_id
from src.providers.gemini_client import GeminiClient
from src.utils.config_loader import Config
from src.utils.logger import logger


class BaseAgent(abc.ABC):
    """
    Abstract base class for an agent that interacts with an LLM and uses tools.
    """

    def __init__(
        self,
        tools: Dict[str, Callable] = None,
        model_kwargs: Dict = Config[GEMINI_20_FLASH],
        prompt_template: str = r"""<SYS> You are a philosopher, reply in abstract sentences. </SYS> User: {{input_str}}""",
        llm_client: ModelClient = GeminiClient(),
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        memory_service: Optional[BaseMemory] = None,
        max_iterations: int = 3,
        max_tool_concurrency: int = 1,
        enable_tracing: bool = False,
        agent_name: str = "BaseAgent",
    ):
        self.tools = tools
        self.model_kwargs = model_kwargs
        self.prompt_template = prompt_template
        self.llm_client = llm_client
        self.conversation_history = (
            conversation_history if conversation_history is not None else []
        )
        self.max_iterations = max_iterations
        self.max_tool_concurrency = max_tool_concurrency
        self.memory_service = memory_service
        self.enable_tracing = enable_tracing
        self.agent_name = agent_name
        self._tracer = (
            trace.get_tracer(self.agent_name) if self.enable_tracing else None
        )

    def _get_common_span_attributes(self, input_value: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a dictionary of common attributes for OpenTelemetry spans.
        """
        attributes = {}
        if not self.enable_tracing or not self._tracer:
            return attributes

        # Automatically add conversation_id if available in context
        conv_id = get_conversation_id()
        if conv_id:
            attributes["conversation_id"] = conv_id

        # Add LLM model name if available (assuming llm_provider has this info)
        if hasattr(self.llm_client, "model_name"):
             attributes[SpanAttributes.LLM_MODEL_NAME] = self.llm_client.model_name
        elif hasattr(self.llm_client, "model"): # Common attribute name
             attributes[SpanAttributes.LLM_MODEL_NAME] = self.llm_client.model

        attributes["initial_message_count"] = len(self.conversation_history)
        if input_value:
            attributes[SpanAttributes.INPUT_VALUE] = input_value

        return attributes

    def _set_span_attributes(self, span: Optional[Span], **attributes):
        """Sets attributes on a span if tracing is enabled and span exists."""
        if span and self.enable_tracing and span.is_recording():
            for key, value in attributes.items():
                # Basic serialization attempt for non-standard types
                if not isinstance(value, (str, int, float, bool)):
                    try:
                        value = json.dumps(value, default=str)
                    except Exception:
                        value = str(value)
                span.set_attribute(key, value)

    def _set_success_span(self, span: Optional[Span], result: Optional[Any] = None):
        """Marks a span as successful (OK) if tracing is enabled."""
        if span and self.enable_tracing and span.is_recording():
            if result is not None:
                self._set_span_attributes(span, result=result)
            span.set_status(Status(StatusCode.OK))
            span.end()

    def _set_error_span(self, span: Optional[Span], error: Exception):
        """Marks a span as failed (ERROR) if tracing is enabled."""
        if span and self.enable_tracing and span.is_recording():
            span.set_status(Status(StatusCode.ERROR, description=str(error)))
            span.record_exception(error)
            span.end()

    def parse_tool_arguments(
        self, tool_name: str, tool_arguments_str: str
    ) -> Dict[str, Any]:
        """
        Parses the JSON string arguments for a tool.
        Handles potential JSON decoding errors.
        """
        # --- Start Span ---
        span: Optional[Span] = None
        if self.enable_tracing and self._tracer:
            attributes = self._get_common_span_attributes(input_value=tool_arguments_str)
            attributes[SpanAttributes.TOOL_NAME] = tool_name
            span = self._tracer.start_span(f"parse_tool_arguments.{tool_name}", attributes=attributes)
        # --- End Span ---
        try:
            args = json.loads(tool_arguments_str)
            if not isinstance(args, dict):
                raise ValueError("Parsed arguments are not a dictionary.")
            self._set_success_span(span, result=args) # Set parsed args as result
            return args
        except json.JSONDecodeError as e:
            error_msg = f"Error decoding JSON arguments for tool '{tool_name}': {e}. Input: '{tool_arguments_str}'"
            logger.error(f"Warning: {error_msg}")  # Or use logger
            self._set_error_span(span, e)
            raise ValueError(error_msg) from e  # Re-raise for handling
        except ValueError as e:
            error_msg = f"Argument validation error for tool '{tool_name}': {e}. Input: '{tool_arguments_str}'"
            logger.error(f"Warning: {error_msg}")  # Or use logger
            self._set_error_span(span, e)
            raise  # Re-raise for handling

    def handle_invalid_tool(self, tool_call: ToolCall) -> ToolResult:
        """Handles the case where the LLM requested a non-existent tool."""
        error_msg = f"Error: Tool '{tool_call.name}' not found."
        logger.warning(f"Warning: {error_msg}")  # Or use logger
        # --- Start Span ---
        span: Optional[Span] = None
        if self.enable_tracing and self._tracer:
            attributes = self._get_common_span_attributes(input_value=tool_call.arguments_str)
            attributes[SpanAttributes.TOOL_NAME] = tool_call.name
            attributes["error.message"] = error_msg # Add specific error message
            span = self._tracer.start_span(f"invalid_tool_call.{tool_call.name}", attributes=attributes)
            self._set_error_span(span, ValueError(error_msg))
        # --- End Span ---
        # Note: Span is ended in _set_error_span
        return ToolResult(
            call_id=tool_call.id,
            content=error_msg,
            is_error=True,
            tool_name=tool_call.name,
        )

    async def _run_tool(self, tool_call: ToolCall) -> ToolResult:
        """Helper method to execute a single tool call."""
        tool_func = self.tools.get(tool_call.name)
        if not tool_func:
            return self.handle_invalid_tool(tool_call)

        # --- Start Span ---
        span: Optional[Span] = None
        if self.enable_tracing and self._tracer:
            attributes = self._get_common_span_attributes(input_value=tool_call.arguments_str)
            attributes[SpanAttributes.OPENINFERENCE_SPAN_KIND] = OpenInferenceSpanKindValues.TOOL
            attributes[SpanAttributes.TOOL_NAME] = tool_call.name
            attributes[SpanAttributes.TOOL_ARGUMENTS] = tool_call.arguments_str
            span = self._tracer.start_span(f"tool_call.{tool_call.name}", attributes=attributes)
        # --- End Span ---
        try:
            # Parse arguments
            parsed_args = self.parse_tool_arguments(
                tool_call.name, tool_call.arguments_str
            )

            # Execute tool function (handle both sync and async tools)
            if asyncio.iscoroutinefunction(tool_func):
                result_content = await tool_func(**parsed_args)
            else:
                # Consider running sync functions in a thread pool executor for non-blocking IO
                # For simplicity here, we run it directly.
                # loop = asyncio.get_running_loop()
                # result_content = await loop.run_in_executor(None, lambda: tool_func(**parsed_args))
                result_content = tool_func(**parsed_args)  # Simplest approach

            # Serialize result if needed (e.g., if it's not a string)
            if not isinstance(result_content, str):
                try:
                    result_content_str = json.dumps(result_content, default=str)
                except Exception:
                    result_content_str = str(result_content)
            else:
                result_content_str = result_content

            # Set standard OUTPUT_VALUE attribute
            self._set_success_span(span, **{SpanAttributes.OUTPUT_VALUE: result_content_str})
            return ToolResult(
                call_id=tool_call.id,
                content=result_content_str,
                is_error=False,
                tool_name=tool_call.name,
            )
        except Exception as e:
            error_msg = f"Error executing tool '{tool_call.name}': {e}"
            logger.error(f"Error: {error_msg}")  # Or use logger
            self._set_error_span(span, e)
            return ToolResult(
                call_id=tool_call.id,
                content=error_msg,
                is_error=True,
                tool_name=tool_call.name,
            )

    async def process_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """Processes a list of tool calls sequentially."""
        # --- Start Span ---
        span: Optional[Span] = None
        if self.enable_tracing and self._tracer:
            attributes = self._get_common_span_attributes()
            span = self._tracer.start_span("process_tool_calls_sequential", attributes=attributes)
        # --- End Span ---
        results = []
        try:
            for tool_call in tool_calls:
                result = await self._run_tool(tool_call)
                results.append(result)
            self._set_success_span(span, result_count=len(results))
            return results
        except Exception as e:
            self._set_error_span(span, e)
            raise  # Re-raise the exception after marking the span

    async def process_tool_calls_concurrent(
        self, tool_calls: List[ToolCall]
    ) -> List[ToolResult]:
        """Processes a list of tool calls concurrently."""
        if not tool_calls:
            return []

        tasks = [self._run_tool(tool_call) for tool_call in tool_calls]
        # --- Start Span ---
        span: Optional[Span] = None
        if self.enable_tracing and self._tracer:
            attributes = self._get_common_span_attributes()
            span = self._tracer.start_span("process_tool_calls_concurrent", attributes=attributes)

        # Limit concurrency if max_tool_concurrency < len(tasks)
        semaphore = asyncio.Semaphore(self.max_tool_concurrency)

        async def run_with_semaphore(task):
            async with semaphore:
                return await task

        concurrent_tasks = [run_with_semaphore(task) for task in tasks]
        # --- End Span ---

        try:
            results_or_errors = await asyncio.gather(
                *concurrent_tasks, return_exceptions=True
            )

            # Process results, converting exceptions back to ToolResult errors
            final_results = []
            for i, res_or_err in enumerate(results_or_errors):
                original_call = tool_calls[i]
                if isinstance(res_or_err, Exception):
                    error_msg = f"Unhandled exception during concurrent execution of tool '{original_call.name}': {res_or_err}"
                    logger.error(f"Error: {error_msg}")
                    # Create an error result
                    final_results.append(
                        ToolResult(
                            call_id=original_call.id,
                            content=error_msg,
                            is_error=True,
                            tool_name=original_call.name,
                        )
                    )
                    # Optionally mark the main concurrent span with a general error note
                    if span and span.is_recording():
                        span.add_event(
                            "concurrent_tool_error",
                            {"tool_name": original_call.name, "error": str(res_or_err)},
                        )
                elif isinstance(res_or_err, ToolResult):
                    final_results.append(res_or_err)
                else:  # Should not happen if _run_tool always returns ToolResult or raises
                    final_results.append(
                        ToolResult(
                            call_id=original_call.id,
                            content=f"Unexpected result type: {type(res_or_err)}",
                            is_error=True,
                            tool_name=original_call.name,
                        )
                    )

            # Decide overall status of the concurrent span
            if any(r.is_error for r in final_results):
                if span and span.is_recording():
                    span.set_status(
                        Status(
                            StatusCode.ERROR,
                            description="One or more concurrent tool calls failed",
                        )
                    )
                    span.end()
            else:
                self._set_success_span(span, result_count=len(final_results))

            return final_results

        except Exception as e:  # Catch errors in asyncio.gather itself (less likely with return_exceptions=True)
            self._set_error_span(span, e)
            raise


    async def _get_llm_response(
        self, messages: List[Dict[str, Any]] # Assuming messages is a list of dicts like conversation history
    ) -> Any:
        """
        Calls the LLM provider with the user input and conversation history.
        Returns the LLM response.
        """
        # Serialize messages for input value attribute if needed, or just use the last user message?
        # For simplicity, let's represent the input as the number of messages for now.
        # A better approach might be to serialize the whole list or just the last message.
        input_repr = f"Conversation history with {len(messages)} messages."

        # --- Start Span ---
        span: Optional[Span] = None
        if self.enable_tracing and self._tracer:
            attributes = self._get_common_span_attributes(input_value=input_repr)
            attributes[SpanAttributes.OPENINFERENCE_SPAN_KIND] = OpenInferenceSpanKindValues.LLM.value
            attributes[SpanAttributes.LLM_MODEL_NAME] = self.model_kwargs.get("model")
            attributes[SpanAttributes.INPUT_VALUE] = messages[0]  # Assuming the first message is the user input
            span = self._tracer.start_span(f"{self.agent_name}.llm_response", attributes=attributes)
        # --- End Span ---
        try:
            # Call the LLM provider (assuming it has a method to handle this)
            # Note: The original code passed conversation_id in model_kwargs,
            # but conversation_id is usually handled by context propagation.
            # Adjust the call signature based on your llm_client's actual requirements.
            # TODO: Check where to define the prompt template
            llm_provider = Generator(
                template=self.prompt_template,
                model_client=self.llm_client,
                model_kwargs=self.model_kwargs,
            )

            # TODO: Check if below call makes more sense or not, how to construct messages
            response = llm_provider(prompt_kwargs={"input_str": messages[0]})
            self._set_success_span(span, result=response)

            return response
        except Exception as e:
            logger.error(f"Error calling LLM: {e}", exc_info=True)
            self._set_error_span(span, e)
            raise

    @abc.abstractmethod
    async def _agent_loop(self, user_input: str) -> AgentResponse:
        """
        The main loop of the agent's reasoning process. Should:
        1. Add the user_input to self.conversation_history.
        2. Repeatedly call the LLM with self.conversation_history.
        3. Process tool calls, adding results back to self.conversation_history.
        4. Return the final AgentResponse.
        5. Append the final assistant response to self.conversation_history.
        Must be implemented by subclasses.
        """
        pass

    # TODO: Check if input should be string or list of messages
    async def run(
        self, user_input: str, conversation_id: Optional[str] = None
    ) -> AgentResponse:
        """
        Public entry point to run the agent for a given user input.
        Sets up context and tracing for the agent execution.
        """
        # Determine and set conversation ID in context
        conv_id = (
            conversation_id or get_conversation_id() or str(uuid.uuid4())
        )  # Generate if needed

        with set_conversation_id(conv_id):
            if self.memory_service and not self.conversation_history:
                try:
                    self.conversation_history = self.memory_service.get_history(conv_id)
                    logger.info(
                        f"Loaded {len(self.conversation_history)} messages from history for {conv_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to load history for {conv_id}: {e}")
                    self.conversation_history = []

            main_span: Optional[Span] = None
            if self.enable_tracing and self._tracer:
                attributes = self._get_common_span_attributes(input_value=user_input)
                attributes[SpanAttributes.OPENINFERENCE_SPAN_KIND] = OpenInferenceSpanKindValues.AGENT.value
                # conversation_id is already added in _get_common_span_attributes
                main_span = self._tracer.start_span(f"{self.agent_name}.run", attributes=attributes)

            try:
                # Call the subclass's implementation of the agent loop
                response = await self._agent_loop(user_input)
                self._set_success_span(main_span, **{SpanAttributes.OUTPUT_VALUE: response.output})

                if self.memory_service:
                    try:
                        self.memory_service.save_history(
                            conv_id, self.conversation_history
                        )
                    except Exception as e:
                        logger.error(f"Failed to save history for {conv_id}: {e}")
                return response

            except Exception as e:
                logger.error(f"Error during agent run: {e}")  # Or use logger
                self._set_error_span(main_span, e)

                return AgentResponse(
                    output=f"An error occurred: {e}", intermediate_steps=[]
                )

    async def __call__(
        self, user_input: str, conversation_id: Optional[str] = None
    ) -> AgentResponse:
        """Allows calling the agent instance like a function."""
        return await self.run(user_input, conversation_id)
