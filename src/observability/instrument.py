import base64
import os

from dotenv import load_dotenv
from openinference.semconv.resource import ResourceAttributes
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from phoenix.otel import register

from src.api.middlewares.conv_id_middleware import CONV_ID_ATTRIBUTE, CONV_ID_HEADER
from src.utils.logger import logger

# Configuration is picked up from your environment variables

# tracer_provider = register()


load_dotenv(override=True)

# LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
# LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
# LANGFUSE_OTEL_API = os.getenv("LANGFUSE_OTEL_API")

# LANGFUSE_AUTH = base64.b64encode(
#     f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()
# ).decode()

# os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {LANGFUSE_AUTH}"
# os.environ["OTEL_EXPORTER_OTLP_TRACES_HEADERS"] = (
#     f"Authorization=Basic {LANGFUSE_AUTH}"
# )

PHOENIX_API_KEY = os.getenv("PHOENIX_API_KEY")
OTEL_EXPORTER_OTLP_HEADERS = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
PHOENIX_COLLECTOR_ENDPOINT = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")


def setup_tracing(app, service_name: str = "llm-toolkit", enable_tracing: bool = True, tracing_name: str = __name__):
    """Sets up OpenTelemetry tracing for the application.

    Args:
        app: The FastAPI application instance to instrument.
        service_name: The name of the service, used for identifying the service in traces.
        enable_tracing: A boolean flag to enable or disable tracing. Defaults to True.
        tracing_name: The name of the tracer, typically the module name. Defaults to __name__.

    Returns:
        None
    """
    try:
        if not enable_tracing:
            logger.info("OpenTelemetry tracing is disabled.")
            return

        # Configure the resource
        # resource = Resource(attributes={"service.name": service_name})
        resource = Resource(attributes={ResourceAttributes.PROJECT_NAME: service_name})

        # Configure the tracer provider
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)
        tracer = trace.get_tracer(tracing_name)


        # Configure the exporter
        # otlp_exporter = OTLPSpanExporter(
        #     endpoint=f"{LANGFUSE_OTEL_API}/v1/traces",
        #     # headers={"Authorization": f"Basic {LANGFUSE_AUTH}"},
        # )
        endpoint = f"http://{PHOENIX_COLLECTOR_ENDPOINT}/v1/traces"
        otlp_exporter = OTLPSpanExporter(
            endpoint=endpoint,
            # insecure=True,
            # headers={"authorization": f"{PHOENIX_API_KEY}"},
        )

        # Configure the span processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        # tracer_provider.add_span_processor(span_processor)
        # tracer = trace.get_tracer(__name__)

        trace.get_tracer_provider().add_span_processor(span_processor)

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)
        # FastAPIInstrumentor.instrument_app(app, http_capture_headers_server_request=["x-conversation-id"])

        logger.info("OpenTelemetry tracing initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing OpenTelemetry tracing: {e}")
