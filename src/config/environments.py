from .base import (
    DatabaseConfig,
    FileLoggingConfig,
    LoggingConfig,
    Settings,
    TracingConfig,
)


class DevSettings(Settings):
    debug: bool = True
    database: DatabaseConfig = DatabaseConfig(host="localhost", name="myapp_dev")
    llm_config_path: str = "src/config/llm_providers.yaml"
    logging: LoggingConfig = LoggingConfig(
        level="DEBUG",
        file_logging=FileLoggingConfig(enable_file_logging=False)
    )
    tracing: TracingConfig = TracingConfig(
        enable_tracing=True,
        otlp_endpoint="https://app.phoenix.arize.com/v1/traces",
        service_name="llm-toolkit-dev"
    )


class StageSettings(Settings):
    debug: bool = False
    database: DatabaseConfig = DatabaseConfig(
        host="stage-db.example.com", name="myapp_stage"
    )
    llm_config_path: str = "src/config/llm_providers.stg.yaml"
    logging: LoggingConfig = LoggingConfig(
        level="INFO",
        file_logging=FileLoggingConfig(
            enable_file_logging=True,
            file_path="logs/stage_app.log"
        )
    )
    tracing: TracingConfig = TracingConfig(
        enable_tracing=True,
        otlp_endpoint="http://localhost:6006/v1/traces",
        service_name="llm-toolkit-stage"
        # api_key might be set via environment for staging/prod
    )


class ProdSettings(Settings):
    debug: bool = False
    database: DatabaseConfig = DatabaseConfig(
        host="prod-db.example.com", name="myapp_prod", pool_size=20
    )
    llm_config_path: str = "src/config/llm_providers.prod.yaml"
    logging: LoggingConfig = LoggingConfig(
        level="INFO",
        file_logging=FileLoggingConfig(
            enable_file_logging=True,
            file_path="/var/log/llm-toolkit/app.log",
            max_size=50 * 1024 * 1024,
            backup_count=10
        )
    )
    tracing: TracingConfig = TracingConfig(
        enable_tracing=True,
        otlp_endpoint="https://otel-collector.prod.example.com/v1/traces",
        service_name="llm-toolkit-prod"
        # api_key should definitely be set via environment variables for production
        # e.g., by PHOENIX_API_KEY which TracingConfig might pick up if aliased
        # or by setting tracing.api_key directly if not using env var for it.
    )
