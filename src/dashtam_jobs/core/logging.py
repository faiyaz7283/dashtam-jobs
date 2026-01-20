"""Structured logging configuration for dashtam-jobs.

Provides JSON-formatted structured logging consistent with dashtam-api patterns.
"""

import logging
import sys
from typing import Any

import structlog

from dashtam_jobs.core.settings import get_settings


def configure_logging() -> None:
    """Configure structured logging for the application.

    Sets up structlog with JSON output for production environments
    and pretty console output for development.
    """
    _settings = get_settings()

    # Determine if we're in development mode
    is_dev = _settings.log_level == "DEBUG"

    # Configure processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_dev:
        # Development: pretty console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    log_level: Any = logging.getLevelName(_settings.log_level)
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Get a configured logger instance.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        Configured structlog logger instance.
    """
    return structlog.get_logger(name)
