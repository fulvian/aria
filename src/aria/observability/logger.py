from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Any

from aria.config import get_config
from aria.utils.logging import get_trace_id

if TYPE_CHECKING:
    from collections.abc import MutableMapping

_STRUCTLOG_ENABLED = os.environ.get("ARIA_STRUCTLOG", "1").lower() not in (
    "0",
    "false",
    "no",
)

try:
    if _STRUCTLOG_ENABLED:
        import structlog as _structlog

        _STRUCTLOG_AVAILABLE = True
    else:
        _structlog = None  # type: ignore[assignment]
        _STRUCTLOG_AVAILABLE = False
except ImportError:
    _structlog = None  # type: ignore[assignment]
    _STRUCTLOG_AVAILABLE = False

structlog: Any = _structlog if _STRUCTLOG_AVAILABLE else None


def _ensure_log_dir() -> Path:
    config = get_config()
    log_dir = config.runtime / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _configure_file_handler() -> TimedRotatingFileHandler:
    log_dir = _ensure_log_dir()
    log_file = log_dir / "aria.jsonl"
    handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        interval=1,
        backupCount=90,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    return handler


def _setup_structlog() -> None:
    handler = _configure_file_handler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger("aria.structlog")
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    root.propagate = False

    def add_aria_context(
        _logger: Any,  # noqa: ANN401
        _method_name: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        if "ts" not in event_dict:
            event_dict["ts"] = datetime.now(UTC).isoformat()
        event_dict["trace_id"] = get_trace_id()
        return event_dict

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            add_aria_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _setup_stdlib() -> None:
    handler = _configure_file_handler()

    class _AriaJsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            entry: dict[str, Any] = {
                "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
                "level": record.levelname,
                "event": record.getMessage(),
                "trace_id": get_trace_id(),
            }
            context: dict[str, Any] = getattr(record, "_aria_context", {})
            if context:
                entry.update(context)
            metadata: dict[str, Any] | None = getattr(record, "_aria_metadata", None)
            if metadata is not None:
                entry["metadata"] = metadata
            return json.dumps(entry, ensure_ascii=True, default=str)

    handler.setFormatter(_AriaJsonFormatter())

    root = logging.getLogger("aria")
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    root.propagate = False


if _STRUCTLOG_AVAILABLE and _STRUCTLOG_ENABLED:
    _setup_structlog()
else:
    _setup_stdlib()


class AriaLogger:
    def __init__(self, name: str) -> None:
        self._name = name
        if _STRUCTLOG_AVAILABLE and _STRUCTLOG_ENABLED:
            self._impl = structlog.get_logger(name)
        else:
            self._impl = logging.getLogger(f"aria.{name}")

    @property
    def name(self) -> str:
        return self._name

    def bind(self, **kwargs: Any) -> AriaLogger:  # noqa: ANN401
        if _STRUCTLOG_AVAILABLE and _STRUCTLOG_ENABLED:
            bound = AriaLogger(self._name)
            bound._impl = self._impl.bind(**kwargs)
            return bound
        else:
            if not hasattr(self._impl, "_aria_context_storage"):
                self._impl._aria_context_storage = {}
            merged = {**getattr(self._impl, "_aria_context_storage", {}), **kwargs}
            bound = AriaLogger(self._name)
            bound._impl = self._impl
            bound._impl._aria_context_storage = merged
            return bound

    def debug(self, event: str, **kwargs: Any) -> None:  # noqa: ANN401
        self._log("debug", event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:  # noqa: ANN401
        self._log("info", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:  # noqa: ANN401
        self._log("warning", event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:  # noqa: ANN401
        self._log("error", event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:  # noqa: ANN401
        kwargs.setdefault("exc_info", True)
        self._log("error", event, **kwargs)

    def _log(self, level: str, event: str, **kwargs: Any) -> None:  # noqa: ANN401
        if _STRUCTLOG_AVAILABLE and _STRUCTLOG_ENABLED:
            getattr(self._impl, level)(event, **kwargs)
        else:
            log_method = getattr(self._impl, level, self._impl.info)
            context = getattr(self._impl, "_aria_context_storage", {})
            extra: dict[str, Any] = {"_aria_context": {**context}}
            metadata_val = kwargs.pop("metadata", None)
            if metadata_val is not None:
                extra["_aria_metadata"] = metadata_val
            for k, v in kwargs.items():
                if k not in ("exc_info", "stack_info", "extra"):
                    extra["_aria_context"][k] = v
            extra.update({k: v for k, v in kwargs.items() if k in ("exc_info", "stack_info")})
            log_method(event, extra=extra)


_ARIA_LOGGERS: dict[str, AriaLogger] = {}


def get_aria_logger(name: str) -> AriaLogger:
    if name not in _ARIA_LOGGERS:
        _ARIA_LOGGERS[name] = AriaLogger(name)
    return _ARIA_LOGGERS[name]
