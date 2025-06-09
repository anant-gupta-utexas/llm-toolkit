from typing import Callable, List, Optional

from fastapi import FastAPI

# For PROJECT_NAME
from openinference.semconv.resource import ResourceAttributes
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPHttpSpanExporter,
)

# Instrumentors
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider

# ConsoleSpanExporter removed
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NoOpTracerProvider

# Added
from src.config import settings
from src.observability.logger import get_logger

logger = get_logger(__name__)

# Store the tracer provider globally
_TRACER_PROVIDER: Optional[TracerProvider] = None


# Custom semantic attribute for project name if not using openinference one directly
# For consistency with provided example, let's assume ResourceAttributes.PROJECT_NAME is available and works
# PROJECT_NAME_KEY = "project.name" # If ResourceAttributes.PROJECT_NAME was not suitable


def setup_otel_tracer(
    app: Optional[FastAPI] = None,
    additional_instrumentors: Optional[List[Callable[[], None]]] = None,
) -> trace.Tracer:
    """
    Configures and sets up the OpenTelemetry tracer based on AppConfig.

    Args:
        additional_instrumentors: A list of functions, each of which will apply an
                                  OpenTelemetry instrumentation.

    Returns:
        An OpenTelemetry Tracer instance.
    """
    global _TRACER_PROVIDER

    trace_config = settings.tracing

    # Use service_name from config for tracer, or a default if not set
    # The TracerProvider resource uses trace_config.service_name
    # trace.get_tracer will use its own logic for name, usually module name.
    # Let's use trace_config.service_name for the get_tracer call for consistency.
    tracer_name = trace_config.service_name or "default_otel_service"

    if not trace_config.enable_tracing:
        logger.info(
            "Tracing is disabled via configuration. Setting up NoOpTracerProvider."
        )
        # Setup NoOp only once
        if not isinstance(_TRACER_PROVIDER, NoOpTracerProvider):
            noop_provider = NoOpTracerProvider()
            trace.set_tracer_provider(noop_provider)
            _TRACER_PROVIDER = noop_provider
        # Return a NoOpTracer
        return trace.get_tracer(tracer_name, "0.1.0")

    if _TRACER_PROVIDER and not isinstance(_TRACER_PROVIDER, NoOpTracerProvider):
        logger.warning("Tracer provider already configured. Skipping reconfiguration.")
        return trace.get_tracer(tracer_name)

    resource = Resource(
        attributes={
            ResourceAttributes.PROJECT_NAME: trace_config.project_name,
            SERVICE_NAME: trace_config.service_name,
        }
    )

    provider = TracerProvider(resource=resource)
    _TRACER_PROVIDER = provider

    span_processors = []
    http_headers = {"api_key": settings.phoenix_api_key}

    if trace_config.otlp_endpoint:
        otlp_exporter = OTLPHttpSpanExporter(
            endpoint=trace_config.otlp_endpoint,
            headers=http_headers
        )
        span_processors.append(BatchSpanProcessor(otlp_exporter))
        logger.info(
            f"OTLP span exporter enabled for endpoint: {trace_config.otlp_endpoint}"
        )
    else:
        logger.info("No OTLP endpoint configured. OTLP export disabled.")

    if not span_processors:
        logger.warning(
            "No span exporters configured (and tracing.enable is True). Telemetry will not be sent."
        )

    for sp in span_processors:
        provider.add_span_processor(sp)

    trace.set_tracer_provider(provider)

    # --- Standard Instrumentors ---
    try:
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        logger.info("HttpxInstrumentor enabled.")
    except Exception as e:
        logger.error(f"Failed to instrument httpx: {e}")

    try:
        RequestsInstrumentor().instrument(tracer_provider=provider)
        logger.info("RequestsInstrumentor enabled.")
    except Exception as e:
        logger.error(f"Failed to instrument requests: {e}")

    # --- Custom Instrumentors ---
    if additional_instrumentors:
        for instrument_func in additional_instrumentors:
            try:
                instrument_func()
                logger.info(
                    f"Successfully applied custom instrumentor: {instrument_func.__name__}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to apply custom instrumentor {instrument_func.__name__}: {e}"
                )

    # # Add FastAPI instrumentation
    # if app:
    #     try:
    #         FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    #         logger.info("FastAPIInstrumentor enabled.")
    #     except Exception as e:
    #         logger.error(f"Failed to instrument FastAPI: {e}")

    return trace.get_tracer(tracer_name, "0.1.0")


def get_tracer(
    instrumenting_module_name: str, instrumenting_library_version: str = "0.1.0"
) -> trace.Tracer:
    """
    Convenience function to get a tracer.
    Ensures that a tracer provider is set (could be NoOp).
    """
    # If setup_otel_tracer hasn't been called, _TRACER_PROVIDER might be None.
    # trace.get_tracer handles this by returning a ProxyTracer that becomes NoOp if no provider is set.
    # This is generally fine.
    if _TRACER_PROVIDER is None:
        logger.warning(
            "OpenTelemetry provider has not been explicitly configured via setup_otel_tracer(). "
            "Calls to trace.get_tracer() will use a default ProxyTracer."
        )
    return trace.get_tracer(instrumenting_module_name, instrumenting_library_version)


def shutdown_otel_tracer():
    global _TRACER_PROVIDER
    # Check if it's a real provider
    if _TRACER_PROVIDER and hasattr(_TRACER_PROVIDER, "shutdown"):
        _TRACER_PROVIDER.shutdown()
        logger.info("OpenTelemetry tracer provider shut down.")
    # Reset regardless
    _TRACER_PROVIDER = None
    # After shutdown, subsequent calls to trace.get_tracer_provider()
    # will return a new ProxyTracerProvider.
    # To ensure NoOp behavior after explicit shutdown, reset to NoOpTracerProvider:
    trace.set_tracer_provider(NoOpTracerProvider())
