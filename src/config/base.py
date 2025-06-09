from typing import Literal, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    host: str
    port: int = 5432
    name: str
    pool_size: int = 10


class FileLoggingConfig(BaseModel):
    enable_file_logging: bool = False
    file_path: str = "logs/app.log"
    max_size: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5
    encoding: str = "utf-8"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    file_logging: FileLoggingConfig = Field(default_factory=FileLoggingConfig)


class TracingConfig(BaseModel):
    enable_tracing: bool = True
    project_name: str = "llm-toolkit-project"
    service_name: str = "llm-toolkit-service"
    otlp_endpoint: str = "http://localhost:6006/v1/traces"
    api_key: Optional[str] = None
    headers: Optional[dict] = Field(default_factory=dict, description="Custom headers for OTLP exporter")


class Settings(BaseSettings):
    # Environment
    environment: Literal["dev", "stage", "prod"] = "dev"
    debug: bool = False

    # Application
    app_name: str = "LLMToolkit"
    api_prefix: str = "/api/v1"

    # API keys from .env or vault
    google_api_key: Optional[str] = None
    phoenix_api_key: Optional[str] = None

    # Database
    database: DatabaseConfig

    # Logging configuration
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Tracing configuration
    tracing: TracingConfig = Field(default_factory=TracingConfig)

    # LLM config file path
    llm_config_path: str = "src/config/llm_providers.yaml"

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False
        extra = "ignore"

    @classmethod
    def load_config(cls) -> "Settings":
        """Factory method to load appropriate config"""
        return cls()

    @property
    def llm_config(self):
        """Load LLM configuration - import here to avoid circular imports"""
        from .llm_config import LLMSettings
        return LLMSettings.from_yaml(self.llm_config_path)
