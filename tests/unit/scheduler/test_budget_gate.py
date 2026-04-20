# Tests for ARIA Budget Gate
#
# Per sprint plan W1.2.C.
#
# Tests:
# - pre_check: allow/deny based on budget
# - tick: mid-run budget monitoring
# - post_run: record final usage

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from aria.scheduler.budget_gate import BudgetDecision, BudgetGate, DailyBudget
from aria.scheduler.schema import make_task


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self, runtime_path: Path | None = None) -> None:
        self._runtime = runtime_path or Path("/tmp/test_runtime")

    @property
    def runtime(self) -> Path:
        return self._runtime


@pytest.fixture
def mock_config(tmp_path: Path) -> MockConfig:
    """Create mock configuration."""
    runtime = tmp_path / ".aria" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    return MockConfig(runtime_path=runtime)


@pytest.fixture
def mock_store() -> MagicMock:
    """Create mock TaskStore."""
    store = MagicMock()
    return store


@pytest.fixture
def budget_gate(mock_store: MagicMock, mock_config: MockConfig) -> BudgetGate:
    """Create BudgetGate instance."""
    return BudgetGate(mock_store, mock_config)


# === Pre-check Tests ===


@pytest.mark.asyncio
async def test_budget_gate_pre_check_allow_within_budget(
    budget_gate: BudgetGate,
) -> None:
    """Test pre_check allows task when within budget."""
    task = make_task(
        name="Within Budget Task",
        category="search",
        trigger_type="cron",
        budget_tokens=1000,
        budget_cost_eur=0.01,
    )

    decision = await budget_gate.pre_check(task)

    assert decision.allowed is True
    assert decision.reason is None
    assert decision.remaining_tokens is not None
    assert decision.remaining_tokens > 0


@pytest.mark.asyncio
async def test_budget_gate_pre_check_deny_exceeds_daily_budget(
    mock_store: MagicMock,
    mock_config: MockConfig,
) -> None:
    """Test pre_check denies task when daily budget exhausted."""
    # Create gate with pre-populated usage
    gate = BudgetGate(mock_store, mock_config)

    # Exhaust the daily budget by directly manipulating internal state
    from datetime import datetime

    today_key = datetime.now().strftime("%Y-%m-%d")
    gate._daily_usage["search"] = {
        "tokens": 500_000,  # Exhaust all tokens
        "cost_eur": 2.00,
        "date": today_key,
    }

    task = make_task(
        name="Exhausted Budget Task",
        category="search",
        trigger_type="cron",
        budget_tokens=1000,
    )

    decision = await gate.pre_check(task)

    assert decision.allowed is False
    assert "exhausted" in decision.reason.lower()
    assert decision.remaining_tokens == 0


@pytest.mark.asyncio
async def test_budget_gate_pre_check_deny_exceeds_cost_budget(
    mock_store: MagicMock,
    mock_config: MockConfig,
) -> None:
    """Test pre_check denies task when cost budget exhausted."""
    gate = BudgetGate(mock_store, mock_config)

    # Exhaust cost budget
    today_key = datetime.now().strftime("%Y-%m-%d")
    gate._daily_usage["search"] = {
        "tokens": 0,
        "cost_eur": 2.00,  # Exhaust all cost
        "date": today_key,
    }

    task = make_task(
        name="Cost Exhausted Task",
        category="search",
        trigger_type="cron",
    )

    decision = await gate.pre_check(task)

    assert decision.allowed is False
    assert "cost" in decision.reason.lower()
    assert decision.remaining_cost_eur == 0


@pytest.mark.asyncio
async def test_budget_gate_pre_check_unknown_category(
    budget_gate: BudgetGate,
) -> None:
    """Test pre_check allows unknown category (no budget configured)."""
    task = make_task(
        name="Unknown Category Task",
        category="custom",
        trigger_type="cron",
    )

    decision = await budget_gate.pre_check(task)

    # Unknown categories should be allowed (no budget configured)
    assert decision.allowed is True


# === Tick Tests ===


@pytest.mark.asyncio
async def test_budget_gate_tick_returns_allow(
    budget_gate: BudgetGate,
) -> None:
    """Test tick returns allow (current implementation is pass-through)."""
    decision = await budget_gate.tick(
        run_id="test-run",
        tokens_consumed=500,
        cost_eur=0.005,
    )

    # Current implementation always allows
    assert decision.allowed is True


@pytest.mark.asyncio
async def test_budget_gate_tick_early_warning() -> None:
    """Test tick mid-run with high consumption."""
    # This tests the tick interface even though current implementation
    # doesn't abort mid-run
    gate = BudgetGate(MagicMock(), MockConfig())

    decision = await gate.tick(
        run_id="high-consumption-run",
        tokens_consumed=999_000,  # Almost max
        cost_eur=1.99,  # Almost max
    )

    # Currently still allows - in full impl would check per-run limits
    assert decision.allowed is True


# === Post-run Tests ===


@pytest.mark.asyncio
async def test_budget_gate_post_run_records_usage(
    mock_store: MagicMock,
    mock_config: MockConfig,
) -> None:
    """Test post_run records final budget usage."""
    gate = BudgetGate(mock_store, mock_config)

    # Record a run
    await gate.post_run(
        run_id="completed-run",
        final_tokens=1500,
        final_cost=0.015,
        category="search",
    )

    # Verify usage was recorded
    today_key = datetime.now().strftime("%Y-%m-%d")
    usage = gate._daily_usage.get("search")
    assert usage is not None
    assert usage["tokens"] == 1500
    assert usage["cost_eur"] == 0.015
    assert usage["date"] == today_key


@pytest.mark.asyncio
async def test_budget_gate_post_run_accumulates(
    mock_store: MagicMock,
    mock_config: MockConfig,
) -> None:
    """Test post_run accumulates usage across runs."""
    gate = BudgetGate(mock_store, mock_config)

    # First run
    await gate.post_run(
        run_id="run-1",
        final_tokens=100,
        final_cost=0.001,
        category="memory",
    )

    # Second run
    await gate.post_run(
        run_id="run-2",
        final_tokens=200,
        final_cost=0.002,
        category="memory",
    )

    # Verify accumulated
    usage = gate._daily_usage.get("memory")
    assert usage is not None
    assert usage["tokens"] == 300
    assert usage["cost_eur"] == 0.003


@pytest.mark.asyncio
async def test_budget_gate_post_run_resets_new_day(
    mock_store: MagicMock,
    mock_config: MockConfig,
) -> None:
    """Test post_run resets usage for new day."""
    gate = BudgetGate(mock_store, mock_config)

    # Set usage for yesterday
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    gate._daily_usage["workspace"] = {
        "tokens": 99_000,
        "cost_eur": 0.49,
        "date": yesterday,
    }

    # Record new run today
    await gate.post_run(
        run_id="new-day-run",
        final_tokens=1000,
        final_cost=0.01,
        category="workspace",
    )

    # Verify reset happened
    usage = gate._daily_usage.get("workspace")
    assert usage is not None
    assert usage["tokens"] == 1000  # Reset, not accumulated
    assert usage["date"] == datetime.now().strftime("%Y-%m-%d")


# === Daily Budget Pause Tests ===


@pytest.mark.asyncio
async def test_budget_gate_check_daily_pause_false(
    budget_gate: BudgetGate,
) -> None:
    """Test check_daily_pause returns False when not exhausted."""
    result = await budget_gate.check_daily_pause("search")

    # Should be False since we haven't exhausted anything
    assert result is False


@pytest.mark.asyncio
async def test_budget_gate_check_daily_pause_true_tokens(
    mock_store: MagicMock,
    mock_config: MockConfig,
) -> None:
    """Test check_daily_pause returns True when tokens exhausted."""
    gate = BudgetGate(mock_store, mock_config)

    # Exhaust tokens
    today_key = datetime.now().strftime("%Y-%m-%d")
    gate._daily_usage["search"] = {
        "tokens": 500_000,
        "cost_eur": 0.0,
        "date": today_key,
    }

    result = await gate.check_daily_pause("search")
    assert result is True


@pytest.mark.asyncio
async def test_budget_gate_check_daily_pause_true_cost(
    mock_store: MagicMock,
    mock_config: MockConfig,
) -> None:
    """Test check_daily_pause returns True when cost exhausted."""
    gate = BudgetGate(mock_store, mock_config)

    # Exhaust cost
    today_key = datetime.now().strftime("%Y-%m-%d")
    gate._daily_usage["search"] = {
        "tokens": 0,
        "cost_eur": 2.00,
        "date": today_key,
    }

    result = await gate.check_daily_pause("search")
    assert result is True


# === Default Budgets Tests ===


def test_budget_gate_default_budgets() -> None:
    """Test BudgetGate has sensible default budgets."""
    gate = BudgetGate(MagicMock(), MockConfig())

    assert "search" in gate._budgets
    assert "workspace" in gate._budgets
    assert "memory" in gate._budgets

    assert gate._budgets["search"].tokens == 500_000
    assert gate._budgets["memory"].tokens == 50_000


# === BudgetDecision Tests ===


def test_budget_decision_allowed() -> None:
    """Test BudgetDecision for allowed case."""
    decision = BudgetDecision(
        allowed=True,
        remaining_tokens=400_000,
        remaining_cost_eur=1.50,
    )

    assert decision.allowed is True
    assert decision.remaining_tokens == 400_000
    assert decision.remaining_cost_eur == 1.50


def test_budget_decision_denied() -> None:
    """Test BudgetDecision for denied case."""
    decision = BudgetDecision(
        allowed=False,
        reason="Daily budget exhausted",
        remaining_tokens=0,
        remaining_cost_eur=0.0,
    )

    assert decision.allowed is False
    assert decision.reason == "Daily budget exhausted"
