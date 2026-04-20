"""Structured JSON logging configuration for Sentinel."""
import logging
from typing import Any

try:
    import structlog
except ImportError:  # pragma: no cover - local env may not have optional dependency yet.
    structlog = None

from core.tracing import get_trace_id


class _FallbackLogger:
    """Small adapter that tolerates structlog-style keyword logging."""

    def __init__(self, logger: logging.Logger, bound: dict[str, Any] | None = None):
        self._logger = logger
        self._bound = bound or {}

    def bind(self, **kwargs: Any):
        merged = dict(self._bound)
        merged.update(kwargs)
        return _FallbackLogger(self._logger, merged)

    def debug(self, event: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.DEBUG, event, *args, **kwargs)

    def info(self, event: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.INFO, event, *args, **kwargs)

    def warning(self, event: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.WARNING, event, *args, **kwargs)

    def error(self, event: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, *args, **kwargs)

    def exception(self, event: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, *args, exc_info=True, **kwargs)

    def _log(self, level: int, event: str, *args: Any, **kwargs: Any) -> None:
        payload = dict(self._bound)
        payload.update(kwargs)
        if "trace_id" not in payload:
            payload["trace_id"] = get_trace_id()
        parts = [str(event)]
        if args:
            parts.extend(str(arg) for arg in args)
        if payload:
            detail = " ".join(f"{key}={value}" for key, value in payload.items())
            parts.append(detail)
        self._logger.log(level, " ".join(parts))

def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level)
    if structlog is None:
        logging.getLogger(__name__).warning("structlog_missing_falling_back_to_stdlib_logging")
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),  # → JSON output
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

def get_logger(name: str | None = None):
    if structlog is None:
        return _FallbackLogger(logging.getLogger(name)).bind(trace_id=get_trace_id())
    return structlog.get_logger(name).bind(trace_id=get_trace_id())
