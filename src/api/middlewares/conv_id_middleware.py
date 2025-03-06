import uuid
from typing import Callable

from opentelemetry import trace
from opentelemetry.context import Context, attach
from opentelemetry.trace import Span, get_current_span, set_span_in_context
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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
            is_new = True
        else:
            is_new = False
        request.scope[CONV_ID_ATTRIBUTE] = conv_id
        # Create context to make it available to other tracing components
        context = Context()
        context.update({CONV_ID_ATTRIBUTE: conv_id})
        token = attach(context)

        # # Add conv_id to the span
        span = get_current_span()
        span.set_attribute(CONV_ID_ATTRIBUTE, conv_id)

        # Proceed with the request
        response = await call_next(request)
        response.headers[CONV_ID_HEADER] = conv_id
        return response
