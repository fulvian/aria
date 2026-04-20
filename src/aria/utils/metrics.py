# ARIA Metrics Utilities (Stub)
#
# Placeholder for Sprint 1.2+ metrics collection.
# Per sprint plan, this is a stub that will be expanded later.
#
# Usage:
#   from aria.utils.metrics import incr, gauge, timing, get_stats
#
# TODO (Sprint 1.2):
# - Implement metrics backend (Prometheus? Statsd? In-memory for MVP)
# - Add counters for credential operations, memory operations
# - Add timing histograms for MCP tool calls
# - Add health check endpoint

from __future__ import annotations

from typing import Any


def incr(name: str, value: int = 1, **tags: str) -> None:
    """Increment a counter metric."""
    # Stub: no-op in Sprint 1.1
    pass


def gauge(name: str, value: float, **tags: str) -> None:
    """Set a gauge metric."""
    # Stub: no-op in Sprint 1.1
    pass


def timing(name: str, duration_ms: float, **tags: str) -> None:
    """Record a timing metric."""
    # Stub: no-op in Sprint 1.1
    pass


def get_stats() -> dict[str, Any]:
    """Get current metrics snapshot."""
    # Stub: returns empty dict in Sprint 1.1
    return {}


def reset() -> None:
    """Reset all metrics (for testing)."""
    # Stub: no-op in Sprint 1.1
    pass
