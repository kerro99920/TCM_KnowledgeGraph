"""Structured logging configuration using loguru."""

import sys
from typing import Literal

from loguru import logger


def setup_logging(
    level: str = "INFO",
    format_type: Literal["json", "text"] = "text",
    log_file: str | None = None,
) -> None:
    """
    Configure application logging with loguru.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Output format ('json' for structured, 'text' for human-readable)
        log_file: Optional file path to write logs to
    """
    # Remove default handler
    logger.remove()

    # Define formats
    text_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    json_format = (
        '{{"timestamp": "{time:YYYY-MM-DDTHH:mm:ss.SSSZ}", '
        '"level": "{level}", '
        '"logger": "{name}", '
        '"function": "{function}", '
        '"line": {line}, '
        '"message": "{message}", '
        '"extra": {extra}}}'
    )

    # Select format
    log_format = json_format if format_type == "json" else text_format
    serialize = format_type == "json"

    # Add console handler
    logger.add(
        sys.stderr,
        format=log_format if not serialize else "{message}",
        level=level,
        colorize=format_type == "text",
        serialize=serialize,
    )

    # Add file handler if specified
    if log_file:
        logger.add(
            log_file,
            format=log_format if not serialize else "{message}",
            level=level,
            rotation="10 MB",
            retention="7 days",
            compression="gz",
            serialize=serialize,
        )

    logger.info(f"Logging configured: level={level}, format={format_type}")


def get_logger(name: str) -> "logger":
    """
    Get a logger instance with context binding.

    Args:
        name: Logger name (typically module name)

    Returns:
        Logger instance bound with the given name
    """
    return logger.bind(name=name)
