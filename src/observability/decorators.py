import asyncio
import functools
import json
import time
from typing import Any, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.context import attach, detach, set_value
from opentelemetry.trace import Span, get_current_span
from pydantic import BaseModel

from src.api.middlewares.conv_id_middleware import CONV_ID_ATTRIBUTE
from src.utils.logger import logger

F = TypeVar("F", bound=Callable[..., Any])


def serialize_pydantic_models(data: Any) -> str:
    """
    Serializes Pydantic models and other data structures to JSON strings.

    Args:
        data: The data to serialize.

    Returns:
        A JSON string representation of the data.
    """
    if isinstance(data, BaseModel):
        return data.model_dump_json()  # Use Pydantic's built-in method
    else:
        try:
            return json.dumps(data, default=str)  # handle non pydantic objects
        except Exception:
            logger.warning(f"could not serialize {data}")
            return str(data)


def trace_external_call(name: str):
    def decorator(func: F) -> F:
        # ----> Check if the original function is async <----
        is_async_func = asyncio.iscoroutinefunction(func)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):  # The wrapper itself is async
            tracer = trace.get_tracer(__name__)
            parent_span = get_current_span()

            # Handle NonRecordingSpan safely
            conv_id = None
            if hasattr(parent_span, "attributes") and parent_span.attributes:
                conv_id = parent_span.attributes.get(CONV_ID_ATTRIBUTE)
            elif isinstance(parent_span, trace.Span) and parent_span.is_recording():
                # Attempt to get context if it's a real span, though attributes might still be missing initially
                # This part might need adjustment based on how context is propagated
                pass  # Or try getting context differently if needed

            context = set_value(CONV_ID_ATTRIBUTE, conv_id) if conv_id else None
            token = attach(context) if context else None

            try:
                with tracer.start_as_current_span(name) as span:
                    span.set_attribute("external_call", name)

                    # Capture input
                    try:
                        span.set_attribute(
                            "input.args", serialize_pydantic_models(args)
                        )
                        span.set_attribute(
                            "input.kwargs", serialize_pydantic_models(kwargs)
                        )
                    except Exception as e:
                        logger.warning(f"Could not set input attributes: {e}")

                    start_time = time.time()

                    # ----> Conditionally await based on original function type <----
                    if is_async_func:
                        result = await func(*args, **kwargs)
                    else:
                        # Call the synchronous function directly
                        result = func(*args, **kwargs)

                    end_time = time.time()
                    span.set_attribute("duration", end_time - start_time)

                    # Capture output
                    try:
                        span.set_attribute("output", serialize_pydantic_models(result))
                    except Exception as e:
                        logger.warning(f"Could not set output attribute: {e}")

                    return result
            except Exception as e:
                # Log the specific error happening during the call
                logger.error(
                    f"Error during external call to {name}: {e}", exc_info=True
                )  # Add exc_info for full traceback
                if span:  # Ensure span exists before setting status
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, description=str(e))
                    )
                raise  # Re-raise the exception so FastAPI handles it
            finally:
                if token:
                    detach(token)

        # ----> Return the correct type (async wrapper) <----
        return wrapper  # The decorator always returns the async wrapper

    return decorator
