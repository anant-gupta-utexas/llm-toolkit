import os
import sys

from loguru import logger


def setup_logger():
    # Remove any existing handlers
    logger.remove()

    try:
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        logger.add(
            sys.stderr,
            level=log_level,  # Detailed traceback
            backtrace=True,  # Diagnostic information
            diagnose=True,  # Colorized output
            colorize=True,
        )
    except ValueError as V:
        logger.add(
            sys.stderr,
            level="INFO",  # Detailed traceback
            backtrace=True,  # Diagnostic information
            diagnose=True,  # Colorized output
            colorize=True,
        )
        logger.warning(f"Level defaulted to Info due to error {V}")


# Initialize the logger
setup_logger()

# Export the logger for use in other modules
__all__ = ["logger"]
