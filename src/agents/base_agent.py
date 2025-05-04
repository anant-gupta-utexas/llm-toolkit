# Define basic data structures for clarity
import abc
import asyncio
import contextlib
import json
import uuid  # Added import
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypedDict

from adalflow.core.model_client import ModelClient
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import trace
from opentelemetry.context import attach, detach
from opentelemetry.trace import Span, Status, StatusCode

from src.observability.context import get_conversation_id, set_conversation_id


@dataclass
class ToolCall:
    """Represents a tool call requested by the LLM."""

    id: str  # Unique ID for this specific call instance
    name: str
    arguments_str: str  # Raw arguments string (usually JSON) from the LLM


@dataclass
class ToolResult:
    """Represents the result of executing a tool."""

    call_id: str  # Corresponds to the ToolCall id
    content: str  # Result content (often stringified JSON or plain text)
    is_error: bool = False
    tool_name: str = ""  # Keep track of which tool produced the result


@dataclass
class AgentResponse:
    """Represents the final output of the agent."""

    output: str  # The final textual response from the agent
    intermediate_steps: List[Any] = field(
        default_factory=list
    )  # History of tool calls/results etc.


class BaseToolCallingAgent(abc.ABC):
    """
    Abstract base class for an agent that interacts with an LLM and uses tools.
    """

    def __init__(
        self,
        llm_provider: ModelClient,
        model: str,
        tools: Dict[str, Callable],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        max_iterations: int = 3,
        max_tool_concurrency: int = 1,  # Default to sequential
        enable_tracing: bool = False,
        agent_name: str = "BaseToolCallingAgent",
    ):
        self.llm_provider = llm_provider
        self.tools = tools
        self.conversation_history = (
            conversation_history if conversation_history is not None else []
        )
        self.max_iterations = max_iterations
        self.max_tool_concurrency = max_tool_concurrency
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
        if hasattr(self.llm_provider, "model_name"):
             attributes[SpanAttributes.LLM_MODEL_NAME] = self.llm_provider.model_name
        elif hasattr(self.llm_provider, "model"): # Common attribute name
             attributes[SpanAttributes.LLM_MODEL_NAME] = self.llm_provider.model

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
                        value = str(value)  # Fallback to string representation
                span.set_attribute(key, value)

    def _set_success_span(self, span: Optional[Span], result: Optional[Any] = None):
        """Marks a span as successful (OK) if tracing is enabled."""
        if span and self.enable_tracing and span.is_recording():
            if result is not None:
                self._set_span_attributes(span, result=result)
            span.set_status(Status(StatusCode.OK))
            span.end()  # End the span on success

    def _set_error_span(self, span: Optional[Span], error: Exception):
        """Marks a span as failed (ERROR) if tracing is enabled."""
        if span and self.enable_tracing and span.is_recording():
            span.set_status(Status(StatusCode.ERROR, description=str(error)))
            span.record_exception(error)
            span.end()  # End the span on error

    def parse_tool_arguments(
        self, tool_name: str, tool_arguments_str: str
    ) -> Dict[str, Any]:
        """
        Parses the JSON string arguments for a tool.
        Handles potential JSON decoding errors.
        """
        span = self._create_span(f"parse_tool_arguments.{tool_name}")
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
            print(f"Warning: {error_msg}")  # Or use logger
            self._set_error_span(span, e)
            raise ValueError(error_msg) from e  # Re-raise for handling
        except ValueError as e:
            error_msg = f"Argument validation error for tool '{tool_name}': {e}. Input: '{tool_arguments_str}'"
            print(f"Warning: {error_msg}")  # Or use logger
            self._set_error_span(span, e)
            raise  # Re-raise for handling

    def handle_invalid_tool(self, tool_call: ToolCall) -> ToolResult:
        """Handles the case where the LLM requested a non-existent tool."""
        error_msg = f"Error: Tool '{tool_call.name}' not found."
        print(f"Warning: {error_msg}")  # Or use logger
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
            # Using TOOL_ARGUMENTS standard attribute
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
            print(f"Error: {error_msg}")  # Or use logger
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
            # Use return_exceptions=True to handle individual tool failures gracefully
            results_or_errors = await asyncio.gather(
                *concurrent_tasks, return_exceptions=True
            )

            # Process results, converting exceptions back to ToolResult errors
            final_results = []
            for i, res_or_err in enumerate(results_or_errors):
                original_call = tool_calls[i]
                if isinstance(res_or_err, Exception):
                    error_msg = f"Unhandled exception during concurrent execution of tool '{original_call.name}': {res_or_err}"
                    print(f"Error: {error_msg}")  # Or use logger
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

    @abc.abstractmethod
    async def _agent_loop(self, user_input: str) -> AgentResponse:
        """
        The core logic loop of the agent.
        Must be implemented by subclasses.
        Should handle:
        - Adding user input to history.
        - Calling the LLM provider.
        - Parsing LLM response (text, tool calls).
        - Processing tool calls (using process_tool_calls or process_tool_calls_concurrent).
        - Adding tool results to history.
        - Repeating until max_iterations or a final answer is reached.
        - Returning the final AgentResponse.
        """
        pass

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
            # --- Start Span ---
            main_span: Optional[Span] = None
            if self.enable_tracing and self._tracer:
                attributes = self._get_common_span_attributes(input_value=user_input)
                attributes[SpanAttributes.OPENINFERENCE_SPAN_KIND] = OpenInferenceSpanKindValues.AGENT
                # conversation_id is already added in _get_common_span_attributes
                main_span = self._tracer.start_span(f"{self.agent_name}.run", attributes=attributes)
            # --- End Span ---

            try:
                # Call the subclass's implementation of the agent loop
                response = await self._agent_loop(user_input)
                # Add final output using standard attribute
                self._set_success_span(main_span, **{SpanAttributes.OUTPUT_VALUE: response.output})
                return response

            except Exception as e:
                print(f"Error during agent run: {e}")  # Or use logger
                self._set_error_span(main_span, e)
                # Return a generic error response or re-raise
                return AgentResponse(
                    output=f"An error occurred: {e}", intermediate_steps=[]
                )
                # raise # Optionally re-raise the exception

    async def __call__(
        self, user_input: str, conversation_id: Optional[str] = None
    ) -> AgentResponse:
        """Allows calling the agent instance like a function."""
        return await self.run(user_input, conversation_id)


class MySpecificAgent(BaseToolCallingAgent):
    async def _agent_loop(self, user_input: str) -> AgentResponse:
        intermediate_steps = []
        self.conversation_history.append({"role": "user", "content": user_input})

        for _ in range(self.max_iterations):
            # --- Start Span ---
            loop_span: Optional[Span] = None
            if self.enable_tracing and self._tracer:
                attributes = self._get_common_span_attributes()
                # Maybe add iteration number?
                # attributes["iteration"] = _ + 1
                loop_span = self._tracer.start_span(f"{self.agent_name}.loop_iteration", attributes=attributes)
            # --- End Span ---

            # 1. Call LLM
            # --- Start Span --- (Assuming generate method handles its own span or we add one here)
            # If generate doesn't create a span, you might want to wrap it:
            # llm_span = self._tracer.start_span("llm_call", attributes=self._get_common_span_attributes())
            try:
                # Prepare tools in the format expected by your LLM provider (e.g., OpenAI format)
                # This needs to be adapted based on self.llm_provider
                formatted_tools = (
                    None  # Replace with actual tool formatting logic if needed
                )
                llm_response = await self.llm_provider.generate(
                    messages=self.conversation_history, tools=formatted_tools
                )
                # self._set_success_span(llm_span, result=llm_response) # If you created llm_span
            except Exception:
                # self._set_error_span(llm_span, e) # If you created llm_span
                raise  # Or handle more gracefully
            # --- End Span ---


            # 2. Parse LLM Response (Highly dependent on LLM provider output format)
            # Example structure assuming OpenAI-like response:
            message = llm_response.get("choices", [{}])[0].get("message", {})
            response_content = message.get("content")
            tool_calls_raw = message.get(
                "tool_calls"
            )  # List of tool call dicts from LLM

            # Add LLM response (assistant message) to history
            self.conversation_history.append(message)  # Add the whole message dict

            # 3. Check for Tool Calls
            if tool_calls_raw:
                # Convert raw LLM tool calls to our ToolCall dataclass
                tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments_str=tc["function"]["arguments"],
                    )
                    for tc in tool_calls_raw
                ]
                intermediate_steps.append(
                    {"type": "llm_tool_request", "data": tool_calls}
                )

                # 4. Process Tool Calls
                if self.max_tool_concurrency > 1 and len(tool_calls) > 1:
                    tool_results = await self.process_tool_calls_concurrent(tool_calls)
                else:
                    tool_results = await self.process_tool_calls(tool_calls)

                intermediate_steps.append(
                    {"type": "tool_results", "data": tool_results}
                )

                # 5. Add Tool Results to History (Format depends on LLM)
                # Example for OpenAI format:
                for result in tool_results:
                    self.conversation_history.append(
                        {
                            "role": "tool",
                            "tool_call_id": result.call_id,
                            "name": result.tool_name,  # Requires _run_tool to populate tool_name
                            "content": result.content,
                        }
                    )
                # Continue loop to let LLM process tool results
                self._set_success_span(
                    loop_span, **{"status": "Processed tools, continuing loop."}
                )

            else:
                # No tool calls, LLM provided final answer
                return AgentResponse(
                    # End loop_span here before returning
                    output=response_content or "No content received.",
                    intermediate_steps=intermediate_steps,
                )

        # Max iterations reached
        return AgentResponse(
            output="Agent reached maximum iterations.",
            intermediate_steps=intermediate_steps,
        )
