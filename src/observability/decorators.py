import functools
import json
import time
from typing import Any, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.context import attach, detach, set_value
from opentelemetry.trace import Span, get_current_span
from pydantic import BaseModel

from src.middleware.conv_id_middleware import CONV_ID_ATTRIBUTE
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
    """
    Decorator to trace external service calls using a new span.

    Args:
        name: The name of the external service being called.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            parent_span = get_current_span()
            conv_id = parent_span.attributes.get(CONV_ID_ATTRIBUTE)
            context = set_value(CONV_ID_ATTRIBUTE, conv_id)
            token = attach(context)
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
                    result = await func(*args, **kwargs)
                    end_time = time.time()
                    span.set_attribute("duration", end_time - start_time)

                    # Capture output
                    try:
                        span.set_attribute("output", serialize_pydantic_models(result))
                    except Exception as e:
                        logger.warning(f"Could not set output attribute: {e}")

                    return result
            except Exception as e:
                logger.error(f"Error during external call to {name}: {e}")
                raise
            finally:
                detach(token)

        return wrapper

    return decorator
