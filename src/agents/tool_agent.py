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

from src.agents.base_agent import BaseAgent
from src.agents.models import AgentResponse, ToolCall, ToolResult
from src.observability.context import get_conversation_id, set_conversation_id


class ToolAgent(BaseAgent):
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
                # formatted_tools = None
                llm_response = await self._get_llm_response(
                    messages=self.conversation_history
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
            )

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
