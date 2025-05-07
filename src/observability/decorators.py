import asyncio
import functools
import json
import time
from typing import Any, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.baggage import get_baggage
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
        is_async_func = asyncio.iscoroutinefunction(func)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            # parent_span = get_current_span() # Not needed for getting conv_id anymore

            # Get conv_id from Baggage
            conv_id = get_baggage(CONV_ID_ATTRIBUTE)
            span = None  # Initialize span variable
            try:
                # Start a new span as a child of the current span (which includes baggage)
                with tracer.start_as_current_span(name) as span:
                    span.set_attribute("external_call", name)

                    if conv_id:
                        span.set_attribute(CONV_ID_ATTRIBUTE, conv_id)

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

                    if is_async_func:
                        result = await func(*args, **kwargs)
                    else:
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
                logger.error(
                    f"Error during external call to {name}: {e}", exc_info=True
                )
                if (
                    span and span.is_recording()
                ):  # Check if span exists and is recording
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, description=str(e))
                    )
                raise

        return wrapper

    return decorator