"""Logging configuration for the application."""

import sys
from pathlib import Path

from loguru import logger

# Remove any pre-configured handlers
logger.remove()

# Add stdout handler with INFO level
logger.add(
    sys.stdout, level="INFO", format="{time} {level} {message}", backtrace=True, diagnose=True
)

# Optionally, you can add more handlers for file logging, etc.
logger.add(
    "app.log",
    rotation="1 week",
    retention="1 month",
    level="INFO",
    format="{time} {level} {message}",
)

# Add file handler with DEBUG level for detailed logging
log_path = Path("logs/debug.log")
log_path.parent.mkdir(exist_ok=True)

logger.add(
    log_path,
    level="DEBUG",
    format="{time} {level} {message}",
    rotation="1 day",
    retention="1 week",
    backtrace=True,
    diagnose=True,
)


# Function to configure logging (if needed to do additional setup)
def configure_logging():
    """Configure logging for the application."""
    logger.debug("Logging configured successfully")


# After logger configuration
logger.debug("Testing debug logging")
logger.info("Testing info logging")

print(f"Log file path: {log_path.absolute()}")
print(f"Log directory exists: {log_path.parent.exists()}")
