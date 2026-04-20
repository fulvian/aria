# ARIA Budget Gate
#
# Per blueprint §6.3 and sprint plan W1.2.C.
#
# Responsibilities:
# - Estimate and account token/cost per task run
# - Abort runs that exceed per-run budget
# - Enforce per-category daily budget limits
#
# Usage:
#   from aria.scheduler.budget_gate import BudgetGate, BudgetDecision
#   gate = BudgetGate(store, config)
#   decision = await gate.pre_check(task)

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria.config import AriaConfig
    from aria.scheduler.schema import Task
    from aria.scheduler.store import TaskStore

logger = logging.getLogger(__name__)


# === Budget Decision ===


@dataclass
class BudgetDecision:
    """Result of a budget check."""

    allowed: bool
    reason: str | None = None
    remaining_tokens: int | None = None
    remaining_cost_eur: float | None = None


# === Daily Budget ===


@dataclass
class DailyBudget:
    """Per-category daily budget limit."""

    category: str
    tokens: int
    cost_eur: float


# === Budget Gate ===


class BudgetGate:
    """Budget enforcement gate for task execution.

    Enforces two levels of budget:
    1. Per-run: limits on individual task execution
    2. Per-category daily: aggregate limits across category

    Config loaded from budgets.yaml in runtime directory.
    """

    # Default budgets if config not found
    DEFAULT_BUDGETS = {
        "search": DailyBudget("search", tokens=500_000, cost_eur=2.00),
        "workspace": DailyBudget("workspace", tokens=100_000, cost_eur=0.50),
        "memory": DailyBudget("memory", tokens=50_000, cost_eur=0.10),
        "custom": DailyBudget("custom", tokens=100_000, cost_eur=0.50),
        "system": DailyBudget("system", tokens=200_000, cost_eur=1.00),
    }

    def __init__(self, store: TaskStore, config: AriaConfig) -> None:
        """Initialize BudgetGate.

        Args:
            store: TaskStore for state tracking
            config: ARIA configuration
        """
        self._store = store
        self._config = config
        self._budgets: dict[str, DailyBudget] = dict(self.DEFAULT_BUDGETS)
        self._daily_usage: dict[str, dict[str, int | float]] = {}
        self._logger = logging.getLogger(__name__)

        # Load budgets from config file
        self._load_budgets()

    def _load_budgets(self) -> None:
        """Load budgets from budgets.yaml config file."""
        budgets_path = self._config.runtime / "scheduler" / "budgets.yaml"

        if not budgets_path.exists():
            self._logger.info("No budgets.yaml found at %s, using defaults", budgets_path)
            return

        try:
            import yaml

            with open(budgets_path) as f:
                data = yaml.safe_load(f)

            if "daily_budgets" in data:
                for cat, spec in data["daily_budgets"].items():
                    self._budgets[cat] = DailyBudget(
                        category=cat,
                        tokens=spec.get("tokens", 100_000),
                        cost_eur=spec.get("cost_eur", 0.50),
                    )
                self._logger.info("Loaded budgets from %s", budgets_path)

        except Exception as e:
            self._logger.warning("Failed to load budgets.yaml: %s", e)

    async def pre_check(self, task: Task) -> BudgetDecision:
        """Check if task can proceed based on budget.

        Called before task execution starts.

        Args:
            task: Task to evaluate

        Returns:
            BudgetDecision with allowance and limits
        """
        # Check per-run budget
        if task.budget_tokens is not None:
            # Task has specific per-run limit
            # For now, we allow - actual tracking happens in tick()
            pass

        # Check per-category daily budget
        daily = self._budgets.get(task.category)
        if not daily:
            return BudgetDecision(allowed=True)

        today_key = self._get_daily_key()
        usage = self._daily_usage.setdefault(
            task.category, {"tokens": 0, "cost_eur": 0.0, "date": today_key}
        )

        # Reset if new day
        if usage.get("date") != today_key:
            usage["tokens"] = 0
            usage["cost_eur"] = 0.0
            usage["date"] = today_key

        remaining_tokens = daily.tokens - usage["tokens"]
        remaining_cost = daily.cost_eur - usage["cost_eur"]

        if remaining_tokens <= 0:
            return BudgetDecision(
                allowed=False,
                reason=f"Daily token budget exhausted for category {task.category}",
                remaining_tokens=0,
                remaining_cost_eur=max(0, remaining_cost),
            )

        if remaining_cost <= 0:
            return BudgetDecision(
                allowed=False,
                reason=f"Daily cost budget exhausted for category {task.category}",
                remaining_tokens=max(0, remaining_tokens),
                remaining_cost_eur=0,
            )

        return BudgetDecision(
            allowed=True,
            remaining_tokens=remaining_tokens,
            remaining_cost_eur=remaining_cost,
        )

    async def tick(
        self,
        run_id: str,
        tokens_consumed: int,
        cost_eur: float,
    ) -> BudgetDecision:
        """Mid-run budget check.

        Called periodically during task execution to check
        if running totals are still within budget.

        Args:
            run_id: Current run ID
            tokens_consumed: Total tokens used so far
            cost_eur: Total cost in EUR so far

        Returns:
            BudgetDecision - abort if over budget
        """
        # For now, tick doesn't cause abort - use pre_check and post_run
        # In a full implementation, this would compare against task-level limits
        return BudgetDecision(allowed=True)

    async def post_run(
        self,
        run_id: str,
        final_tokens: int,
        final_cost: float,
        category: str,
    ) -> None:
        """Record final budget usage.

        Called after task completion to update daily totals.

        Args:
            run_id: Completed run ID
            final_tokens: Final token count
            final_cost: Final cost in EUR
            category: Task category
        """
        today_key = self._get_daily_key()
        usage = self._daily_usage.setdefault(
            category, {"tokens": 0, "cost_eur": 0.0, "date": today_key}
        )

        # Reset if new day
        if usage.get("date") != today_key:
            usage["tokens"] = 0
            usage["cost_eur"] = 0.0
            usage["date"] = today_key

        usage["tokens"] += final_tokens
        usage["cost_eur"] += final_cost

        self._logger.info(
            "Updated daily usage for %s: tokens=%d, cost_eur=%.4f",
            category,
            usage["tokens"],
            usage["cost_eur"],
        )

    def _get_daily_key(self) -> str:
        """Get current date key for daily tracking."""
        return time.strftime("%Y-%m-%d")

    async def check_daily_pause(self, category: str) -> bool:
        """Check if category should be paused due to daily budget.

        Args:
            category: Task category to check

        Returns:
            True if category should be paused
        """
        daily = self._budgets.get(category)
        if not daily:
            return False

        today_key = self._get_daily_key()
        usage = self._daily_usage.get(category, {})
        date_key = usage.get("date", "")

        # Reset if new day
        if date_key != today_key:
            return False

        if usage.get("tokens", 0) >= daily.tokens:
            return True

        return usage.get("cost_eur", 0.0) >= daily.cost_eur


# === Import TaskStore for type checking ===
