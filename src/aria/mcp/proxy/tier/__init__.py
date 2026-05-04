"""Tier-based connection lifecycle for the MCP proxy.

This package implements the tier-based proxy architecture that replaces
the previous TimeoutProxyProvider. It distinguishes warm (always-on)
vs lazy (on-demand) backends, providing auto-recovery, idle TTL pool,
circuit breaker, concurrency semaphore, and persistent metadata cache.
"""

from __future__ import annotations

from aria.mcp.proxy.tier.tiered_provider import TieredProxyProvider

__all__ = [
    "TieredProxyProvider",
]
