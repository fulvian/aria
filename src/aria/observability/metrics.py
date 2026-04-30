from __future__ import annotations

import os
from threading import Lock

from aria.config import get_config

_METRICS_ENABLED = os.environ.get("ARIA_METRICS_ENABLED", "1").lower() not in (
    "0",
    "false",
    "no",
)

try:
    if _METRICS_ENABLED:
        from prometheus_client import CollectorRegistry, Counter, Histogram, write_to_textfile

        _PROMETHEUS_AVAILABLE = True
    else:
        CollectorRegistry = None
        Counter = None
        Histogram = None
        write_to_textfile = None
        _PROMETHEUS_AVAILABLE = False
except ImportError:
    CollectorRegistry = None
    Counter = None
    Histogram = None
    write_to_textfile = None
    _PROMETHEUS_AVAILABLE = False

_DEFAULT_BUCKETS = (
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
    float("inf"),
)
_MCP_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float("inf"))


class MetricsCollector:
    def __init__(self) -> None:
        self._enabled = bool(_PROMETHEUS_AVAILABLE and _METRICS_ENABLED)
        if not self._enabled:
            return

        self._registry = CollectorRegistry()
        self._lock = Lock()

        self._agent_spawn = Counter(
            "aria_agent_spawn_total",
            "Total number of agent spawns",
            labelnames=["agent", "parent"],
            registry=self._registry,
        )
        self._agent_spawn_duration = Histogram(
            "aria_agent_spawn_duration_seconds",
            "Duration of agent spawn operations",
            labelnames=["agent"],
            buckets=_DEFAULT_BUCKETS,
            registry=self._registry,
        )
        self._tool_call = Counter(
            "aria_tool_call_total",
            "Total number of tool calls",
            labelnames=["agent", "tool", "outcome"],
            registry=self._registry,
        )
        self._hitl_request = Counter(
            "aria_hitl_request_total",
            "Total number of human-in-the-loop requests",
            labelnames=["agent", "action_type", "outcome"],
            registry=self._registry,
        )
        self._mcp_startup = Histogram(
            "aria_mcp_startup_seconds",
            "MCP server startup duration",
            labelnames=["server"],
            buckets=_MCP_BUCKETS,
            registry=self._registry,
        )
        self._llm_tokens = Counter(
            "aria_llm_tokens_total",
            "Total LLM tokens consumed",
            labelnames=["agent", "model", "kind"],
            registry=self._registry,
        )

    def inc_agent_spawn(self, agent: str, parent: str = "") -> None:
        if not self._enabled:
            return
        labels = {"agent": agent, "parent": parent or agent}
        self._agent_spawn.labels(**labels).inc()

    def observe_agent_spawn_duration(self, agent: str, duration_s: float) -> None:
        if not self._enabled:
            return
        self._agent_spawn_duration.labels(agent=agent).observe(duration_s)

    def inc_tool_call(self, agent: str, tool: str, outcome: str = "success") -> None:
        if not self._enabled:
            return
        labels = {"agent": agent, "tool": tool, "outcome": outcome}
        self._tool_call.labels(**labels).inc()

    def inc_hitl_request(self, agent: str, action_type: str, outcome: str = "requested") -> None:
        if not self._enabled:
            return
        labels = {"agent": agent, "action_type": action_type, "outcome": outcome}
        self._hitl_request.labels(**labels).inc()

    def observe_mcp_startup(self, server: str, duration_s: float) -> None:
        if not self._enabled:
            return
        self._mcp_startup.labels(server=server).observe(duration_s)

    def inc_llm_tokens(self, agent: str, model: str, kind: str, amount: int = 1) -> None:
        if not self._enabled:
            return
        labels = {"agent": agent, "model": model, "kind": kind}
        self._llm_tokens.labels(**labels).inc(amount)

    def flush(self) -> None:
        if not self._enabled:
            return
        config = get_config()
        metrics_dir = config.runtime / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        prom_file = metrics_dir / "aria.prom"
        with self._lock:
            write_to_textfile(str(prom_file), self._registry)


_COLLECTOR: MetricsCollector | None = None
_COLLECTOR_LOCK = Lock()


def get_metrics_collector() -> MetricsCollector:
    global _COLLECTOR  # noqa: PLW0603
    if _COLLECTOR is None:
        with _COLLECTOR_LOCK:
            if _COLLECTOR is None:
                _COLLECTOR = MetricsCollector()
    return _COLLECTOR


def observe_agent_spawn(agent: str, parent: str = "") -> None:
    get_metrics_collector().inc_agent_spawn(agent, parent)


def observe_agent_spawn_duration(agent: str, duration_s: float) -> None:
    get_metrics_collector().observe_agent_spawn_duration(agent, duration_s)


def observe_tool_call(agent: str, tool: str, outcome: str = "success") -> None:
    get_metrics_collector().inc_tool_call(agent, tool, outcome)


def observe_hitl_request(agent: str, action_type: str, outcome: str = "requested") -> None:
    get_metrics_collector().inc_hitl_request(agent, action_type, outcome)


def observe_mcp_startup(server: str, duration_s: float) -> None:
    get_metrics_collector().observe_mcp_startup(server, duration_s)


def observe_llm_tokens(agent: str, model: str, kind: str, amount: int = 1) -> None:
    get_metrics_collector().inc_llm_tokens(agent, model, kind, amount)


def flush_metrics() -> None:
    get_metrics_collector().flush()
