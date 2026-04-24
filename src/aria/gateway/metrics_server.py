# Metrics Server — Prometheus metrics server for gateway
#
# Stub implementation for metrics.
#
# Usage:
#   from aria.gateway.metrics_server import start_metrics_server, stop_metrics_server
#
#   start_metrics_server(host="127.0.0.1", port=9090)

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_running = False


def start_metrics_server(host: str = "127.0.0.1", port: int = 9090) -> None:
    """Start the metrics server."""
    global _running
    _running = True
    logger.info("Metrics server would start on %s:%d (stub)", host, port)


def stop_metrics_server() -> None:
    """Stop the metrics server."""
    global _running
    _running = False
    logger.info("Metrics server stopped")


def is_metrics_server_running() -> bool:
    """Check if metrics server is running."""
    return _running
