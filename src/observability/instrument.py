import logging
import os
from urllib.parse import urljoin, urlparse  # Import urljoin

from dotenv import load_dotenv

# OpenTelemetry Imports
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.api.middlewares.conv_id_middleware import CONV_ID_ATTRIBUTE, CONV_ID_HEADER
from src.utils.logger import logger

# Load environment variables - use override=True to ensure .env takes precedence
load_dotenv(override=True)

# Get relevant environment variables
PHOENIX_API_KEY = os.getenv("PHOENIX_API_KEY")
OTEL_EXPORTER_OTLP_HEADERS_STR = os.getenv(
    "OTEL_EXPORTER_OTLP_HEADERS"
)
PHOENIX_COLLECTOR_ENDPOINT_URL = os.getenv(
    "PHOENIX_COLLECTOR_ENDPOINT"
)

def setup_tracing(
    app,
    service_name: str = "llm-toolkit",
    enable_tracing: bool = True,
    tracing_name: str = __name__,
):
    """Sets up OpenTelemetry tracing for the application."""
    try:
        if not enable_tracing:
            logger.info("OpenTelemetry tracing is disabled.")
            return

        if not PHOENIX_COLLECTOR_ENDPOINT_URL:
            logger.error("PHOENIX_COLLECTOR_ENDPOINT environment variable is not set!")
            return

        # Standard path for OTLP HTTP traces is /v1/traces
        http_endpoint = urljoin(PHOENIX_COLLECTOR_ENDPOINT_URL, "v1/traces")

        logger.info("Configuring OTLP HTTP exporter:")
        logger.info(f"  HTTP Target URL: {http_endpoint}")

        # The HTTP exporter expects headers as a dictionary {key: value}.
        http_headers = {}
        if OTEL_EXPORTER_OTLP_HEADERS_STR:
            try:
                for item in OTEL_EXPORTER_OTLP_HEADERS_STR.split(","):
                    if "=" in item:
                        key, value = item.strip().split("=", 1)
                        http_headers[key.strip()] = value.strip()
                if http_headers:
                    logger.info(f"  Using Headers: {http_headers}")
                else:
                    logger.warning(
                        "Could not parse OTEL_EXPORTER_OTLP_HEADERS into key-value pairs."
                    )
            except Exception as e:
                logger.warning(f"Error parsing OTEL_EXPORTER_OTLP_HEADERS: {e}")
        elif PHOENIX_API_KEY:
            # Fallback or alternative: If only API key is provided, assume a standard header.
            # Check Phoenix docs for the correct header name (e.g., 'x-api-key', 'authorization')
            http_headers["api_key"] = PHOENIX_API_KEY
            logger.info(f"  Using Headers from PHOENIX_API_KEY: {http_headers}")
        else:
            logger.info("  No headers configured for OTLP exporter.")

        # --- Configure the OTLP HTTP Exporter ---
        resource = Resource(attributes={"service.name": service_name})
        tracer_provider = TracerProvider(resource=resource)
        otlp_exporter = OTLPSpanExporter(
            endpoint=http_endpoint,
            headers=http_headers,  # Pass the headers dictionary
        )
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(tracer_provider)

        # Instrument FastAPI
        # FastAPIInstrumentor.instrument_app(
        #     app, http_capture_headers_server_request=["x-conversation-id"]
        # )

        logger.info("OpenTelemetry tracing initialized successfully.")

    except Exception as e:
        logger.error(f"Error initializing OpenTelemetry tracing: {e}", exc_info=True)
