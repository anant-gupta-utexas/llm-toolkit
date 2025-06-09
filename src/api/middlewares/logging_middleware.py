import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.observability.context import get_conversation_id
from src.observability.logger import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.time()

        conversation_id = get_conversation_id()

        log_extras_request = {
            "path": request.url.path,
            "method": request.method,
            "client_host": request.client.host,
            "user_agent": request.headers.get("user-agent", "N/A"),
            "conversation_id": conversation_id
            if conversation_id
            else "N/A_in_request_log",
        }
        logger.info(
            f"Incoming request: {request.method} {request.url.path}",
            extra=log_extras_request,
        )

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # conversation_id might have been set during the request processing by ConversationContextMiddleware
            # or other parts of the application if not available initially.
            # So, we try to get it again.
            conversation_id_after_request = get_conversation_id()

            log_extras_response = {
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "process_time_ms": int(process_time * 1000),
                "conversation_id": conversation_id_after_request
                if conversation_id_after_request
                else "N/A_in_response_log",
            }
            logger.info(
                f"Outgoing response: {response.status_code} for {request.method} {request.url.path}",
                extra=log_extras_response,
            )
        except Exception as e:
            process_time = time.time() - start_time
            # Attempt to get conversation_id even in case of an unhandled exception
            conversation_id_on_error = get_conversation_id()

            logger.error(
                f"Unhandled exception during request processing: {request.method} {request.url.path}",
                # This adds stack trace
                exc_info=True,
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "process_time_ms": int(process_time * 1000),
                    "conversation_id": conversation_id_on_error
                    if conversation_id_on_error
                    else "N/A_on_error",
                    "error_type": type(e).__name__,
                },
            )
            # Important: re-raise the exception so FastAPI's default error handling can take over
            # or it's handled by other exception middleware.
            # Not re-raising would mean the client gets a generic 500 Internal Server Error
            # without the actual error details if no other middleware handles it.
            # However, for a pure logging middleware, it's common practice to just log and let it propagate.
            # If we wanted to return a custom error response here, we would construct a Response object.
            raise e

        return response
