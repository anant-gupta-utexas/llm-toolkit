import uuid
from typing import Callable

from opentelemetry import trace
from opentelemetry.baggage import set_baggage
from opentelemetry.context import attach, detach
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.observability.context import set_conversation_id
from src.utils.logger import logger

CONV_ID_HEADER = "X-Conversation-ID"
CONV_ID_ATTRIBUTE = "conv_id"


class ConvIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate conv_id
        conv_id = request.headers.get(CONV_ID_HEADER)
        if not conv_id:
            conv_id = str(uuid.uuid4())
            logger.info(f"Generated new conversation ID: {conv_id}")
        else:
            logger.info(f"Using existing conversation ID: {conv_id}")

        # Store in scope for Starlette-level components
        request.scope[CONV_ID_ATTRIBUTE] = conv_id

        # Get the current span and set attribute
        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute(CONV_ID_ATTRIBUTE, conv_id)

        # Create context with baggage
        ctx = set_baggage(CONV_ID_ATTRIBUTE, conv_id)
        token = None
        try:
            # Attach the context
            token = attach(ctx)

            # Use the conversation ID context manager
            with set_conversation_id(conv_id):
                response = await call_next(request)

            # Add conversation ID to response headers
            response.headers[CONV_ID_HEADER] = conv_id
            return response
        except Exception as e:
            logger.error(
                f"Error processing request with conversation ID {conv_id}: {str(e)}"
            )
            raise
        finally:
            # Always detach the context
            if token:
                detach(token)
