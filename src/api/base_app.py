import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import mcp_router, workflows_router
from src.api.middlewares.conv_id_middleware import ConvIdMiddleware
from src.api.middlewares.tracing_middleware import TracingMiddleware
from src.observability.instrument import setup_tracing
from src.utils.logger import logger


async def lifespan(app: FastAPI):
    """
    Async lifespan function to manage the application's startup and shutdown.
    Use this to perform any necessary setup or teardown tasks.

    Args:
        app: The FastAPI application instance.
    """
    logger.info("Starting up...")
    yield
    logger.info("Shutting down...")

app = FastAPI(lifespan=lifespan)
setup_tracing(app, enable_tracing=True)

# --- CORS Configuration ---
origins = [
    "http://localhost",
    "http://localhost:8080",
    "https://your-frontend-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Allow sending cookies (if needed)
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers.
)
app.add_middleware(ConvIdMiddleware)
app.add_middleware(
    TracingMiddleware,
    max_request_body_size=4096,  # Configure max body size for request
    max_response_body_size=4096,  # Configure max body size for response
)

app.include_router(workflows_router.router)
app.include_router(mcp_router.router)


@app.get("/api/health", tags=["admin"])
async def health():
    """
    A simple root route that returns a welcome message.
    """
    return {"message": "Jarvis says Hi"}
