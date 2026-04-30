from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from yaml import safe_load

_DEFAULT_CONFIG_PATH = Path("/home/fulvio/coding/aria/.aria/config/llm_routing.yaml")

# ---------------------------------------------------------------------------
# Pydantic models — YAML config schema
# ---------------------------------------------------------------------------


class ModelDef(BaseModel):
    id: str
    cost_tier: Literal["high", "medium", "low"]
    capabilities: list[str]


class RouteDef(BaseModel):
    agent: str
    primary: str
    fallback: str
    cache_strategy: Literal["long", "medium", "short"]
    max_tokens: int


class IntentOverride(BaseModel):
    intent: str
    model: str


class BudgetGate(BaseModel):
    daily_token_cap_usd: float
    overflow_action: Literal["degrade"]


class Policy(BaseModel):
    budget_gate: BudgetGate
    fallback_chain_max: int = Field(default=2)


class RoutingConfig(BaseModel):
    models: dict[str, ModelDef]
    routing: list[RouteDef]
    intent_overrides: list[IntentOverride] = Field(default_factory=list)
    policy: Policy = Field(
        default_factory=lambda: Policy(
            budget_gate=BudgetGate(daily_token_cap_usd=5.0, overflow_action="degrade"),
            fallback_chain_max=2,
        )
    )


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ModelSpec:
    id: str
    cost_tier: str
    capabilities: list[str]
    cache_strategy: str
    max_tokens: int


@dataclass
class RoutingEntry:
    agent: str
    primary: ModelSpec
    fallback: ModelSpec | None


# ---------------------------------------------------------------------------
# Default specs (used when routing is disabled)
# ---------------------------------------------------------------------------

_DEFAULT_MODELS: dict[str, ModelSpec] = {
    "opus_4_7": ModelSpec(
        id="claude-opus-4-7",
        cost_tier="high",
        capabilities=["orchestration", "deep_reasoning", "planning"],
        cache_strategy="long",
        max_tokens=8192,
    ),
    "sonnet_4_6": ModelSpec(
        id="claude-sonnet-4-6",
        cost_tier="medium",
        capabilities=["research", "synthesis", "drafting", "tool_use"],
        cache_strategy="medium",
        max_tokens=4096,
    ),
    "haiku_4_5": ModelSpec(
        id="claude-haiku-4-5-20251001",
        cost_tier="low",
        capabilities=["classification", "triage", "formatting", "cheap_calls"],
        cache_strategy="medium",
        max_tokens=4096,
    ),
}

_DEFAULT_ROUTING: dict[str, RoutingEntry] = {
    "aria-conductor": RoutingEntry(
        agent="aria-conductor",
        primary=_DEFAULT_MODELS["opus_4_7"],
        fallback=_DEFAULT_MODELS["sonnet_4_6"],
    ),
    "search-agent": RoutingEntry(
        agent="search-agent",
        primary=_DEFAULT_MODELS["sonnet_4_6"],
        fallback=_DEFAULT_MODELS["haiku_4_5"],
    ),
    "workspace-agent": RoutingEntry(
        agent="workspace-agent",
        primary=_DEFAULT_MODELS["sonnet_4_6"],
        fallback=_DEFAULT_MODELS["haiku_4_5"],
    ),
    "productivity-agent": RoutingEntry(
        agent="productivity-agent",
        primary=_DEFAULT_MODELS["sonnet_4_6"],
        fallback=_DEFAULT_MODELS["haiku_4_5"],
    ),
}


# ---------------------------------------------------------------------------
# Cost-per-token estimates (fraction of $USD / 1K tokens)
# ---------------------------------------------------------------------------

_COST_PER_1K: dict[str, float] = {
    "high": 0.015,
    "medium": 0.003,
    "low": 0.0005,
}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class BudgetExceededError(RuntimeError):
    """Raised when the daily budget gate would be exceeded."""


class LlmRouter:
    """Model selection router with fallback and budget enforcement.

    Loads the routing matrix from a YAML config file and provides
    intent-aware model selection, automatic fallback on errors,
    and a configurable daily budget gate.

    Disable with the environment variable ``ARIA_LLM_ROUTING=0`` —
    when disabled, ``select_model`` returns a hard-coded default
    (sonnet_4_6) and all other operations become no-ops.
    """

    def __init__(self, config_path: str | Path = _DEFAULT_CONFIG_PATH) -> None:
        self._config_path = Path(config_path)
        self._disabled = os.environ.get("ARIA_LLM_ROUTING", "1") == "0"

        self._routing: dict[str, RoutingEntry] = {}
        self._intent_overrides: dict[str, str] = {}
        self._model_defs: dict[str, ModelSpec] = {}
        self._fallback_chain_max: int = 2

        self._daily_cap_usd: float = 5.0
        self._overflow_action: str = "degrade"

        # Budget tracking
        self._usage_usd: float = 0.0
        self._budget_reset_at: datetime = datetime.now(tz=UTC)
        self._lock = threading.Lock()

        if not self._disabled:
            self._load_config()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        raw = safe_load(self._config_path.read_text())
        config = RoutingConfig.model_validate(raw)

        self._model_defs = {
            key: ModelSpec(
                id=m.id,
                cost_tier=m.cost_tier,
                capabilities=list(m.capabilities),
                cache_strategy=m.cache_strategy if hasattr(m, "cache_strategy") else "medium",
                max_tokens=m.max_tokens if hasattr(m, "max_tokens") else 4096,
            )
            for key, m in config.models.items()
        }

        self._routing = {}
        for route in config.routing:
            primary = self._model_defs[route.primary]
            fallback = self._model_defs.get(route.fallback)
            self._routing[route.agent] = RoutingEntry(
                agent=route.agent,
                primary=ModelSpec(
                    id=primary.id,
                    cost_tier=primary.cost_tier,
                    capabilities=list(primary.capabilities),
                    cache_strategy=route.cache_strategy,
                    max_tokens=route.max_tokens,
                ),
                fallback=fallback,
            )

        self._intent_overrides = {o.intent: o.model for o in config.intent_overrides}

        policy = config.policy
        self._daily_cap_usd = policy.budget_gate.daily_token_cap_usd
        self._overflow_action = policy.budget_gate.overflow_action
        self._fallback_chain_max = policy.fallback_chain_max

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_model(self, agent: str, intent: str | None = None) -> ModelSpec:
        """Select the best model for *agent* given an optional *intent*.

        When routing is disabled this always returns the sonnet_4_6 default.
        """
        if self._disabled:
            return _DEFAULT_MODELS["sonnet_4_6"]

        # Intent override wins
        if intent and intent in self._intent_overrides:
            model_key = self._intent_overrides[intent]
            spec = self._model_defs.get(model_key)
            if spec is not None:
                return spec

        # Agent routing
        entry = self._routing.get(agent)
        if entry is not None:
            return entry.primary

        # Fallback to sonnet
        return _DEFAULT_MODELS["sonnet_4_6"]

    def get_model_for_agent(self, agent: str) -> ModelSpec:
        """Return the primary ModelSpec for *agent*.

        Unlike *select_model* this does **not** honour intent overrides;
        it is a pure lookup of the routing table.
        """
        if self._disabled:
            return _DEFAULT_MODELS["sonnet_4_6"]
        entry = self._routing.get(agent)
        if entry is not None:
            return entry.primary
        return _DEFAULT_MODELS["sonnet_4_6"]

    def apply_fallback(
        self, prev_model: ModelSpec, error: Exception | None = None
    ) -> ModelSpec | None:
        """Walk the fallback chain when *prev_model* failed.

        Returns ``None`` when no further fallback exists (or routing is
        disabled), allowing the caller to propagate the error.
        """
        if self._disabled:
            return None

        # Find the routing entry that owns this model as its primary
        fallback: ModelSpec | None = None
        for entry in self._routing.values():
            if entry.primary.id == prev_model.id:
                fallback = entry.fallback
                break

        return fallback

    def enforce_budget(self, estimated_tokens: int, model: ModelSpec) -> bool:
        """Check whether consuming *estimated_tokens* on *model* stays
        under the daily budget.

        Returns ``True`` if the request is within budget, ``False`` if
        it would exceed the cap and the overflow action is ``"degrade"``.

        Resets the usage counter when a new calendar day begins.
        """
        if self._disabled:
            return True

        with self._lock:
            now = datetime.now(tz=UTC)
            if now.date() > self._budget_reset_at.date():
                self._usage_usd = 0.0
                self._budget_reset_at = now

            cost_per_1k = _COST_PER_1K.get(model.cost_tier, 0.003)
            estimated_cost = (estimated_tokens / 1000.0) * cost_per_1k
            projected = self._usage_usd + estimated_cost

            if projected > self._daily_cap_usd:
                if self._overflow_action == "degrade":
                    return False
                return False

            self._usage_usd += estimated_cost
            return True

    @property
    def daily_usage_usd(self) -> float:
        """Accumulated USD cost for the current budget day."""
        with self._lock:
            return self._usage_usd

    @property
    def daily_cap_usd(self) -> float:
        """Configured daily budget cap in USD."""
        return self._daily_cap_usd

    @property
    def fallback_depth(self) -> int:
        """Maximum number of fallback hops allowed."""
        return self._fallback_chain_max
