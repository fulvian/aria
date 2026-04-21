# ARIA Logging Utilities
#
# Structured JSON logging with trace_id propagation, secret redaction,
# and daily rotation with gzip compression.
#
# Per blueprint §14.1:
# - Output: JSON line con campi ts (ISO8601 UTC), level, logger, event, trace_id, context
# - File handler: .aria/runtime/logs/<logger_root>-%Y-%m-%d.log, rotazione giornaliera gzip
# - Stdout handler only if sys.stdout.isatty()
# - redact_secret(None) → "<none>", redact_secret("sk-abc1234567") → "***4567"
#
# Usage:
#   from aria.utils.logging import get_logger, set_trace_id, new_trace_id, redact_secret, log_event
#
#   logger = get_logger(__name__)
#   set_trace_id(new_trace_id())
#   log_event(logger, logging.INFO, "my_event", key="value")

from __future__ import annotations

import gzip
import json
import logging
import os
import re
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

# === Trace ID Context Variable ===

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    """Get current trace_id from context."""
    return trace_id_var.get()


def set_trace_id(trace_id: str) -> None:
    """Set trace_id in current context."""
    trace_id_var.set(trace_id)


def new_trace_id() -> str:
    """Generate new trace_id (uuid4 hex[:12])."""
    return uuid.uuid4().hex[:12]


# === Secret Redaction ===

SECRET_PATTERNS = (
    r"sk-[A-Za-z0-9]{20,}",
    r"api[_-]?key[A-Za-z0-9_-]*",
    r"token[A-Za-z0-9_-]*",
    r"password[A-Za-z0-9_-]*",
    r"Bearer\s+[A-Za-z0-9._-]+",
    r"ghp_[A-Za-z0-9]{36}",
    r"gho_[A-Za-z0-9]{36}",
    r"glpat-[A-Za-z0-9_-]{20,}",
)


def redact_secret(value: str | None, keep_last: int = 4) -> str:
    """Redact secret, keeping last N characters.

    Rules per blueprint:
    - redact_secret(None) → "<none>"
    - redact_secret("sk-abc1234567") → "***4567"
    """
    if value is None:
        return "<none>"

    if len(value) <= keep_last:
        return "*" * len(value)

    return f"***{value[-keep_last:]}"


# === JSON Line Formatter ===


class JsonLineFormatter(logging.Formatter):
    """Formatter that outputs JSON lines per log record."""

    def format(self, record: logging.LogRecord) -> str:
        # Build context dict from extra fields
        context: dict[str, Any] = {}

        # Copy standard extra fields that are dicts/lists
        for attr in dir(record):
            if attr.startswith("_"):
                continue
            val = getattr(record, attr, None)
            if (
                val is not None
                and attr
                not in (
                    "name",
                    "levelname",
                    "levelno",
                    "pathname",
                    "lineno",
                    "module",
                    "funcName",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "processName",
                    "process",
                    "filename",
                    "exc_text",
                    "stack_info",
                    "message",
                    "args",
                    "msg",
                    "taskName",
                    "marker",
                )
                and isinstance(val, (dict, list, str, int, float, bool, type(None)))
            ):
                context[attr] = val

        # Special handling for marker field
        marker = getattr(record, "marker", None)
        if marker:
            context["marker"] = marker

        # Build log entry
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "trace_id": get_trace_id(),
            "context": context,
        }

        # Redact any value that looks like a secret in context
        for key, val in list(context.items()):
            if isinstance(val, str) and _looks_like_secret(val):
                context[key] = redact_secret(val)

        return json.dumps(entry, ensure_ascii=True)


# === Gzip Rotating File Handler ===


def _looks_like_secret(value: str) -> bool:
    """Check if a string value looks like a secret."""
    import re

    return any(re.match(pattern, value, re.IGNORECASE) for pattern in SECRET_PATTERNS)


class GzipRotatingFileHandler(TimedRotatingFileHandler):
    """Daily rotating file handler with gzip compression of old logs."""

    def __init__(
        self,
        filename: str | Path,
        when: str = "midnight",
        interval: int = 1,
        backupCount: int = 90,
        encoding: str = "utf-8",
    ) -> None:
        super().__init__(
            filename=str(filename),
            when=when,
            interval=interval,
            backupCount=backupCount,
            encoding=encoding,
        )
        # Override suffix to include date
        self.suffix = "%Y-%m-%d"
        # Override extMatch to match the suffix format
        self.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}$")  # type: ignore[assignment]

    def rotation_filename(self, default_name: str) -> str:
        """Add .gz to rotated files."""
        return f"{default_name}.gz"

    def rotate(self, source: str, dest: str) -> None:
        """Compress source file to dest with gzip."""
        with open(source, "rb") as f_in, gzip.open(dest, "wb") as f_out:
            # Copy in chunks
            while True:
                chunk = f_in.read(8192)
                if not chunk:
                    break
                f_out.write(chunk)


# === Logger Factory ===

_loggers: dict[str, logging.Logger] = {}
_loggers_lock = None  # Will use simple dict locking


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with ARIA standard configuration.

    Logger configuration:
    - JSON line format to file (daily gzip rotation)
    - Console output only if stdout is a tty
    - All loggers propagate to root for unified handling
    """
    global _loggers, _loggers_lock

    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()  # Clear any default handlers

    # Determine log directory
    aria_home = Path(os.environ.get("ARIA_HOME", "/home/fulvio/coding/aria"))
    log_dir = aria_home / ".aria" / "runtime" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Determine logger root name for filename
    # Use first component of logger name for the file prefix
    root_name = name.split(".")[0] if "." in name else name
    log_file = log_dir / f"{root_name}-%Y-%m-%d.log"

    # File handler with gzip rotation
    try:
        file_handler = GzipRotatingFileHandler(
            filename=str(log_file),
            when="midnight",
            backupCount=90,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JsonLineFormatter())
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # If we can't create the file handler, continue with console only
        import warnings

        warnings.warn(f"Could not create log file handler: {e}", stacklevel=2)

    # Console handler (only if stdout is a tty)
    if sys.stdout.isatty():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(JsonLineFormatter())
        logger.addHandler(console_handler)

    # Prevent propagation to root (we handle formatting at handler level)
    logger.propagate = False

    _loggers[name] = logger
    return logger


# === Structured Event Logging ===


def log_event(logger: logging.Logger, level: int, event: str, **context: Any) -> None:
    """Log a structured event with context.

    Args:
        logger: Logger instance
        level: Log level (e.g., logging.INFO)
        event: Event name/identifier
        **context: Additional context fields (will be merged with extra)
    """
    extra = {"event": event}
    extra.update(context)

    # Create a LogRecord with the extra context
    # We use the logger's internal _log method to pass extra
    logger.log(level, event, extra=extra)
