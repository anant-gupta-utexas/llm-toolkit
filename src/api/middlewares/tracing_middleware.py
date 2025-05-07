import json
import time
from typing import Callable, Optional

from opentelemetry import trace
from opentelemetry.semconv.trace import SpanAttributes as OTELSpanAttributes
from opentelemetry.trace import SpanKind, StatusCode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.types import ASGIApp

from src.observability.context import get_conversation_id
from src.utils.logger import logger  # Assuming you have a logger at this path

# Attribute for conversation_id (can be aligned with existing conventions)
CONVERSATION_ID_ATTR = "context.conversation_id"
# Attribute for session.id as requested
SESSION_ID_ATTR = "session.id"

# Custom attributes for request/response bodies for more clarity
HTTP_REQUEST_BODY_ATTR = "http.request.body.content"
HTTP_RESPONSE_BODY_ATTR = "http.response.body.content"


class TracingMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        tracer_provider: Optional[trace.TracerProvider] = None,
        max_request_body_size: int = 4096,  # Max bytes of request body to log (0 to disable)
        max_response_body_size: int = 4096, # Max bytes of response body to log (0 to disable)
    ):
        super().__init__(app)
        self.tracer = trace.get_tracer(
            "llm_toolkit.api_tracing_middleware", # Conventional tracer name
            tracer_provider=tracer_provider
        )
        self.max_request_body_size = max_request_body_size
        self.max_response_body_size = max_response_body_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Optionally skip tracing for certain paths like /docs, /openapi.json
        # if request.url.path in ("/docs", "/openapi.json", "/favicon.ico", "/redoc"):
        #     return await call_next(request)

        conversation_id = get_conversation_id() # Relies on ConvIdMiddleware running first

        initial_attributes = self._extract_initial_request_attributes(request, conversation_id)
        span_name = self._generate_span_name(request, initial_attributes.get(OTELSpanAttributes.HTTP_ROUTE))

        start_time = time.perf_counter()

        with self.tracer.start_as_current_span(
            span_name, kind=SpanKind.SERVER, attributes=initial_attributes
        ) as span:
            response: Optional[Response] = None
            try:
                # Set request body attribute on the span
                await self._set_request_body_attribute(request, span)

                # Proceed with the request processing
                response = await call_next(request)

            except Exception as e:
                # If an exception occurs during request processing (call_next or our code before)
                if span.is_recording():
                    span.set_status(StatusCode.ERROR, description=str(e))
                    span.record_exception(e)
                raise # Re-raise to be handled by FastAPI's error handling
            finally:
                # This block executes whether call_next succeeded or raised an exception
                # that was caught and re-raised by the above 'except' block.
                # Ensure duration is recorded if possible.
                # Note: if an error occurred in call_next, 'response' might not be set here.
                # The span status for errors is set in the 'except' block.
                # If no error, status and response attributes are set after this block.
                pass # Span context manager handles ending the span.

            # This part executes only if call_next(request) completed without raising an exception
            # or if an exception was caught and handled locally (which is not the case here).
            duration_ms = (time.perf_counter() - start_time) * 1000

            if span.is_recording(): # Check if span is still active and recording
                # TODO: Figure out the right attribute for duration, this is throwing an error
                # span.set_attribute(OTELSpanAttributes.HTTP_SERVER_DURATION, duration_ms)

                if response: # Should always be true if no exception from call_next
                    self._set_response_attributes(response, span)
                    await self._set_response_body_attribute(response, span)

                    if response.status_code >= 400:
                        span.set_status(StatusCode.ERROR, description=f"HTTP Error: {response.status_code}")
                    else:
                        span.set_status(StatusCode.OK)

            if response is None:
                # This case should ideally not be reached if call_next behaves as expected
                # (either returns a Response or raises an Exception).
                # If it is, create a generic error response.
                logger.error("APITracingMiddleware: Response object is None after call_next without exception.")
                # Fallback, though Starlette's BaseHTTPMiddleware usually handles this.
                return Response("Internal Server Error", status_code=500)

            return response

    def _generate_span_name(self, request: Request, http_route: Optional[str]) -> str:
        """Generates a descriptive span name, preferring route if available."""
        if http_route:
            return f"{request.method} {http_route}"
        return f"{request.method} {request.url.path}"

    def _extract_initial_request_attributes(self, request: Request, conv_id: Optional[str]) -> dict:
        """Extracts initial attributes from the request for the span."""
        attributes = {
            OTELSpanAttributes.HTTP_REQUEST_METHOD: request.method,
            OTELSpanAttributes.URL_FULL: str(request.url),
            OTELSpanAttributes.URL_PATH: request.url.path,
            OTELSpanAttributes.CLIENT_ADDRESS: request.client.host if request.client else None,
            OTELSpanAttributes.SERVER_ADDRESS: request.url.hostname, # Host requested by client
            OTELSpanAttributes.SERVER_PORT: request.url.port,
            OTELSpanAttributes.NETWORK_PROTOCOL_VERSION: request.scope.get("http_version"),
        }
        if request.url.query:
            attributes[OTELSpanAttributes.URL_QUERY] = request.url.query

        route_info = request.scope.get("route")
        if route_info and hasattr(route_info, "path_format"): # FastAPI/Starlette specific
            attributes[OTELSpanAttributes.HTTP_ROUTE] = route_info.path_format

        if conv_id:
            attributes[CONVERSATION_ID_ATTR] = conv_id
            attributes[SESSION_ID_ATTR] = conv_id # As per user request

        user_agent = request.headers.get("user-agent")
        if user_agent:
            attributes[OTELSpanAttributes.USER_AGENT_ORIGINAL] = user_agent

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                attributes[OTELSpanAttributes.HTTP_REQUEST_BODY_SIZE] = int(content_length)
            except ValueError:
                logger.debug(f"Could not parse request content-length: {content_length}")

        # Remove None values to keep attributes clean
        return {k: v for k, v in attributes.items() if v is not None}

    async def _set_request_body_attribute(self, request: Request, span: trace.Span):
        """Reads request body (if appropriate) and sets it as a span attribute."""
        if not span.is_recording() or self.max_request_body_size <= 0:
            return

        content_type = request.headers.get("content-type", "").lower()
        # Log body for common text-based content types
        if "application/json" in content_type or \
           "text/" in content_type or \
           "application/x-www-form-urlencoded" in content_type:
            try:
                # Starlette's request.body() caches the body, so it's safe to call here.
                # Subsequent reads by the route handler will get the cached version.
                body_bytes = await request.body()
                if body_bytes:
                    truncated_body = self._truncate_and_format_body(body_bytes, self.max_request_body_size)
                    span.set_attribute(HTTP_REQUEST_BODY_ATTR, truncated_body)
            except Exception as e:
                logger.warning(f"Could not read or set request body attribute: {e}", exc_info=True)
                if span.is_recording(): # Check again as exception handling might be async
                    span.set_attribute(HTTP_REQUEST_BODY_ATTR, "[Error reading request body]")

    def _set_response_attributes(self, response: Response, span: trace.Span):
        """Sets common response attributes on the span."""
        if not span.is_recording():
            return
        span.set_attribute(OTELSpanAttributes.HTTP_RESPONSE_STATUS_CODE, response.status_code)

        content_length = response.headers.get("content-length")
        if content_length:
            try:
                span.set_attribute(OTELSpanAttributes.HTTP_RESPONSE_BODY_SIZE, int(content_length))
            except ValueError:
                logger.debug(f"Could not parse response content-length: {content_length}")

    async def _set_response_body_attribute(self, response: Response, span: trace.Span):
        """Reads response body (if appropriate) and sets it as a span attribute."""
        if not span.is_recording() or self.max_response_body_size <= 0:
            return

        # Handling StreamingResponse body is complex and can interfere with streaming.
        # For now, we'll skip capturing body for StreamingResponse.
        if isinstance(response, StreamingResponse):
            if span.is_recording():
                span.set_attribute(HTTP_RESPONSE_BODY_ATTR, "[StreamingResponse - body not captured]")
            return

        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type or "text/" in content_type:
            try:
                # For starlette.responses.Response, response.body should be available.
                if hasattr(response, "body") and response.body:
                    truncated_body = self._truncate_and_format_body(response.body, self.max_response_body_size)
                    span.set_attribute(HTTP_RESPONSE_BODY_ATTR, truncated_body)
            except Exception as e:
                logger.warning(f"Could not read or set response body attribute: {e}", exc_info=True)
                if span.is_recording():
                    span.set_attribute(HTTP_RESPONSE_BODY_ATTR, "[Error reading response body]")

    def _truncate_and_format_body(self, body_bytes: bytes, max_size: int) -> str:
        """Truncates body if too large and attempts to decode as UTF-8."""
        if not body_bytes:
            return ""

        text_representation: str
        try:
            text_representation = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # If not UTF-8, provide a safe representation of the (truncated) bytes
            if len(body_bytes) > max_size:
                return f"[Binary data, {len(body_bytes)} bytes, truncated to {max_size}] {body_bytes[:max_size]!r}..."
            return f"[Binary data, {len(body_bytes)} bytes] {body_bytes!r}"

        if len(text_representation) > max_size:
            return text_representation[:max_size] + "..."
        return text_representation

