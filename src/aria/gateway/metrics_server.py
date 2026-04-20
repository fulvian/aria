"""Prometheus metrics server for the ARIA Gateway.

Exposes metrics on 127.0.0.1:9090/metrics using prometheus_client.
Metrics are NEVER exposed outside 127.0.0.1 — an assertion prevents 0.0.0.0 binding.
"""

from __future__ import annotations

import logging
import threading
from wsgiref.simple_server import WSGIServer, make_server

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    make_wsgi_app,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry and metrics definitions
# ---------------------------------------------------------------------------

REGISTRY = CollectorRegistry(auto_describe=True)

# Counters
TASKS_TOTAL = Counter(
    "aria_tasks_total",
    "Total number of tasks processed",
    ["category", "outcome"],
    registry=REGISTRY,
)
TASKS_ACTIVE = Counter(
    "aria_tasks_active",
    "Number of tasks currently being executed",
    registry=REGISTRY,
)
HITL_PENDING = Gauge(
    "aria_hitl_pending",
    "Number of HITL requests pending user response",
    registry=REGISTRY,
)

# Gauges
MEMORY_T0 = Gauge(
    "aria_memory_t0",
    "Number of Tier-0 (raw episodic) entries",
    registry=REGISTRY,
)
MEMORY_T1 = Gauge(
    "aria_memory_t1",
    "Number of Tier-1 (FTS5 semantic) entries",
    registry=REGISTRY,
)

# Histograms
TASK_DURATION = Histogram(
    "aria_task_duration_seconds",
    "Task execution duration in seconds",
    ["category"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    registry=REGISTRY,
)
HITL_RESPONSE_TIME = Histogram(
    "aria_hitl_response_time_seconds",
    "Time from HITL request to user response",
    buckets=(1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0, 900.0),
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

_metrics_server: WSGIServer | None = None
_server_thread: threading.Thread | None = None


def _validate_bind_host(host: str) -> str:
    """Validate that the bind host is 127.0.0.1 (loopback only)."""
    assert host in ("127.0.0.1", "localhost", "::1"), (
        f"SECURITY: metrics server MUST bind to 127.0.0.1, not {host}. "
        "Metrics endpoint must not be exposed outside localhost."
    )
    return "127.0.0.1"


def start_metrics_server(
    host: str = "127.0.0.1",
    port: int = 9090,
) -> None:
    """Start the Prometheus metrics HTTP server in a background thread.

    Args:
        host: Bind host (must be 127.0.0.1 — assertion enforced).
        port: TCP port for the metrics endpoint.

    Raises:
        AssertionError: if host is not 127.0.0.1.
        RuntimeError: if the server is already running.
    """
    global _metrics_server, _server_thread  # noqa: PLW0602, PLW0603

    if _metrics_server is not None or _server_thread is not None:
        raise RuntimeError("Metrics server is already running.")

    bind_host = _validate_bind_host(host)

    app = make_wsgi_app(REGISTRY)

    def run_server() -> None:
        global _metrics_server  # noqa: PLW0603
        _metrics_server = make_server(bind_host, port, app, WSGIServer)
        logger.info(
            "Prometheus metrics server started on %s:%d",
            bind_host,
            port,
        )
        _metrics_server.serve_forever()

    _server_thread = threading.Thread(target=run_server, daemon=True)
    _server_thread.start()


def stop_metrics_server() -> None:
    """Stop the background metrics server."""
    global _metrics_server, _server_thread  # noqa: PLW0602, PLW0603

    if _metrics_server is not None:
        logger.info("Stopping Prometheus metrics server.")
        _metrics_server.shutdown()
        _metrics_server = None

    if _server_thread is not None:
        _server_thread.join(timeout=5)
        _server_thread = None


def is_metrics_server_running() -> bool:
    """Return True if the metrics server thread is alive."""
    return _server_thread is not None and _server_thread.is_alive()


# ---------------------------------------------------------------------------
# Convenience helpers for recording metrics
# ---------------------------------------------------------------------------


def record_task_complete(category: str, outcome: str) -> None:
    """Record a task completion counter."""
    TASKS_TOTAL.labels(category=category, outcome=outcome).inc()


def record_task_start() -> None:
    """Increment the active tasks gauge."""
    TASKS_ACTIVE.inc()


def record_task_end() -> None:
    """Decrement the active tasks gauge."""
    TASKS_ACTIVE.dec()  # type: ignore[attr-defined]


def record_hitl_pending() -> None:
    """Increment the HITL pending counter."""
    HITL_PENDING.inc()


def record_hitl_resolved() -> None:
    """Decrement the HITL pending counter (when resolved or expired)."""
    HITL_PENDING.dec()


def set_memory_tier_counts(t0: int, t1: int) -> None:
    """Update the memory tier gauges."""
    MEMORY_T0.set(t0)
    MEMORY_T1.set(t1)


def observe_task_duration(category: str, duration_seconds: float) -> None:
    """Observe a task's execution duration."""
    TASK_DURATION.labels(category=category).observe(duration_seconds)


def observe_hitl_response_time(duration_seconds: float) -> None:
    """Observe the time from HITL request to user response."""
    HITL_RESPONSE_TIME.observe(duration_seconds)
