from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from aria.scheduler.runner import TaskRunner
from aria.scheduler.schema import make_task


@pytest.fixture
def mock_dependencies() -> tuple[
    MagicMock, MagicMock, MagicMock, MagicMock, MagicMock, SimpleNamespace
]:
    store = MagicMock()
    budget = MagicMock()
    policy = MagicMock()
    hitl = MagicMock()
    bus = MagicMock()
    config = SimpleNamespace(
        paths=SimpleNamespace(
            home=Path("/tmp/aria"),
            runtime=Path("/tmp/aria/.aria/runtime"),
            kilocode_config=Path("/tmp/aria/.aria/kilocode"),
            kilocode_state=Path("/tmp/aria/.aria/kilocode/sessions"),
        ),
        operational=SimpleNamespace(timezone="Europe/Rome", quiet_hours_end="07:00"),
    )
    return store, budget, policy, hitl, bus, config


@pytest.mark.asyncio
async def test_workspace_requires_skill(mock_dependencies: tuple) -> None:
    store, budget, policy, hitl, bus, config = mock_dependencies
    runner = TaskRunner(store, budget, policy, hitl, bus, config)

    task = make_task(name="no-skill", category="workspace", trigger_type="manual", payload={})
    result = await runner._exec_workspace_task(task)

    assert result.outcome == "failed"
    assert result.result_summary == "Missing skill in task payload"


@pytest.mark.asyncio
async def test_write_skill_enforces_hitl_policy(mock_dependencies: tuple) -> None:
    store, budget, policy, hitl, bus, config = mock_dependencies
    executor = AsyncMock(
        return_value={
            "success": True,
            "summary": "should not run",
        }
    )
    runner = TaskRunner(store, budget, policy, hitl, bus, config, workspace_executor=executor)

    task = make_task(
        name="write-without-ask",
        category="workspace",
        trigger_type="manual",
        policy="allow",
        payload={"skill": "gmail-composer-pro", "sub_agent": "workspace-mail-write"},
    )

    result = await runner._exec_workspace_task(task)

    assert result.outcome == "blocked_policy"
    assert "requires policy=ask or explicit user write intent" in (result.result_summary or "")
    executor.assert_not_called()


@pytest.mark.asyncio
async def test_write_skill_allows_explicit_user_request_without_ask(
    mock_dependencies: tuple,
) -> None:
    store, budget, policy, hitl, bus, config = mock_dependencies
    executor = AsyncMock(
        return_value={
            "success": True,
            "summary": "executed",
        }
    )
    runner = TaskRunner(store, budget, policy, hitl, bus, config, workspace_executor=executor)

    task = make_task(
        name="explicit-write",
        category="workspace",
        trigger_type="manual",
        policy="allow",
        payload={
            "skill": "gmail-composer-pro",
            "sub_agent": "workspace-mail-write",
            "user_explicit_request": True,
        },
    )

    result = await runner._exec_workspace_task(task)

    assert result.outcome == "success"
    executor.assert_called_once()


@pytest.mark.asyncio
async def test_workspace_profile_selection_overrides_payload_subagent(
    mock_dependencies: tuple,
) -> None:
    store, budget, policy, hitl, bus, config = mock_dependencies
    captured: dict[str, object] = {}

    async def executor(request: dict[str, object]) -> dict[str, object]:
        captured.update(request)
        return {"success": True, "summary": "ok"}

    runner = TaskRunner(store, budget, policy, hitl, bus, config, workspace_executor=executor)

    task = make_task(
        name="docs-read",
        category="workspace",
        trigger_type="manual",
        payload={"skill": "docs-structure-reader", "sub_agent": "workspace-agent"},
    )

    result = await runner._exec_workspace_task(task)

    assert result.outcome == "success"
    assert captured["sub_agent"] == "workspace-docs-read"


@pytest.mark.asyncio
async def test_workspace_executor_propagates_usage_fields(mock_dependencies: tuple) -> None:
    store, budget, policy, hitl, bus, config = mock_dependencies
    executor = AsyncMock(
        return_value={
            "success": True,
            "summary": "executed",
            "tokens_used": 123,
            "cost_eur": 0.42,
        }
    )
    runner = TaskRunner(store, budget, policy, hitl, bus, config, workspace_executor=executor)

    task = make_task(
        name="sheets-write",
        category="workspace",
        trigger_type="manual",
        policy="ask",
        payload={"skill": "sheets-editor-pro", "sub_agent": "workspace-sheets-write"},
    )

    result = await runner._exec_workspace_task(task)

    assert result.outcome == "success"
    assert result.tokens_used == 123
    assert result.cost_eur == 0.42


def test_workspace_error_classification(mock_dependencies: tuple) -> None:
    store, budget, policy, hitl, bus, config = mock_dependencies
    runner = TaskRunner(store, budget, policy, hitl, bus, config)

    assert runner._classify_workspace_error("401 Unauthorized") == "auth"
    assert runner._classify_workspace_error("429 Quota exceeded") == "quota"
    assert runner._classify_workspace_error("Connection timeout") == "network"
    assert runner._classify_workspace_error("HITL required") == "policy"
    assert runner._classify_workspace_error("unexpected server error") == "tool_error"
