# ARIA utilities module
#
# Shared utilities:
# - logging: structured JSON logging
# - metrics: Prometheus-ready metrics
#
# Usage:
#   from aria.utils import setup_logging, get_logger

from __future__ import annotations

__all__ = ["setup_logging", "get_logger"]


def setup_logging(level: str = "INFO") -> None:
    """Set up structured JSON logging."""
    pass


def get_logger(name: str) -> object:
    """Get a logger instance."""
    return object()
