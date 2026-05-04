"""
Structured logging: JSON lines for production aggregators, human-readable text locally.
Call configure_logging() once at process startup (before other app imports log).
"""

from __future__ import annotations

import logging
import sys

import structlog

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    from app.config import settings

    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    if not isinstance(level, int):
        level = logging.INFO

    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(key="timestamp", fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if settings.LOG_FORMAT == "json":
        processors = shared + [structlog.processors.JSONRenderer()]
    else:
        processors = shared + [structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    _configured = True
