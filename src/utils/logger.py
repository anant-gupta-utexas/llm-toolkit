import sys

from loguru import logger

from src.config import Settings
from src.config.base import LoggingConfig


def setup_logger(config: LoggingConfig):
    # Remove any existing handlers
    logger.remove()

    # Determine if debug features like backtrace/diagnose should be enabled
    debug_features_enabled = config.level == "DEBUG"

    logger.add(
        sys.stderr,
        level=config.level,
        backtrace=debug_features_enabled,
        diagnose=debug_features_enabled,
        colorize=True,
    )

    if config.file_logging.enable_file_logging:
        logger.add(
            config.file_logging.file_path,
            level=config.level,
            rotation=f"{config.file_logging.max_size}B",
            retention=config.file_logging.backup_count,
            encoding=config.file_logging.encoding,
            format=config.file_logging.format,
            backtrace=debug_features_enabled,
            diagnose=debug_features_enabled,
        )

def initialize_logger_with_settings():
    """Initialize logger with settings loaded from config."""
    settings = Settings.load_config()
    setup_logger(config=settings.logging)

initialize_logger_with_settings()

# Export the logger for use in other modules
__all__ = ["logger"]
