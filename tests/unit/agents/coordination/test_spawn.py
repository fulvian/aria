from __future__ import annotations

import json

import pytest

from aria.agents.coordination import (
    ContextEnvelope,
    HandoffRequest,
    SpawnRequest,
    SpawnResult,
    spawn_subagent_validated,
    validate_spawn_depth,
)


@pytest.fixture
def valid_handoff() -> HandoffRequest:
    return HandoffRequest(
        goal="Search for AI papers",
        trace_id="trace-spawn-001",
        parent_agent="conductor",
        spawn_depth=1,
    )


@pytest.fixture
def deep_handoff() -> HandoffRequest:
    return HandoffRequest(
        goal="Deep research on transformers",
        trace_id="trace-spawn-002",
        parent_agent="search_agent",
        spawn_depth=2,
    )


@pytest.fixture
def envelope() -> ContextEnvelope:
    return ContextEnvelope(
        trace_id="trace-spawn-001",
        session_id="session-spawn",
    )


class TestSpawnRequestCreation:
    def test_with_required_fields(self, valid_handoff: HandoffRequest) -> None:
        req = SpawnRequest(
            target_agent="search_agent",
            handoff=valid_handoff,
        )
        assert req.target_agent == "search_agent"
        assert req.handoff.goal == "Search for AI papers"
        assert req.envelope is None

    def test_with_envelope(self, valid_handoff: HandoffRequest, envelope: ContextEnvelope) -> None:
        req = SpawnRequest(
            target_agent="search_agent",
            handoff=valid_handoff,
            envelope=envelope,
        )
        assert req.envelope is not None
        assert req.envelope.trace_id == "trace-spawn-001"

    def test_empty_target_agent_rejected(self, valid_handoff: HandoffRequest) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SpawnRequest(
                target_agent="",
                handoff=valid_handoff,
            )

    def test_extra_fields_forbidden(self, valid_handoff: HandoffRequest) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SpawnRequest(
                target_agent="search_agent",
                handoff=valid_handoff,
                unknown_field="not allowed",
            )

    def test_serialization(self, valid_handoff: HandoffRequest) -> None:
        req = SpawnRequest(
            target_agent="search_agent",
            handoff=valid_handoff,
        )
        json_str = req.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["target_agent"] == "search_agent"
        assert parsed["handoff"]["goal"] == "Search for AI papers"


class TestSpawnResultCreation:
    def test_success_result(self) -> None:
        result = SpawnResult(
            success=True,
            target_agent="search_agent",
            spawn_depth=1,
            trace_id="trace-300",
        )
        assert result.success is True
        assert result.target_agent == "search_agent"
        assert result.spawn_depth == 1
        assert result.trace_id == "trace-300"
        assert result.error is None

    def test_failure_result(self) -> None:
        result = SpawnResult(
            success=False,
            target_agent="search_agent",
            spawn_depth=2,
            trace_id="trace-301",
            error="Delegation denied",
        )
        assert result.success is False
        assert result.error == "Delegation denied"

    def test_dataclass_mutation(self) -> None:
        result = SpawnResult(
            success=False,
            target_agent="search_agent",
            spawn_depth=1,
            trace_id="trace-302",
            error="Timeout",
        )
        result.success = True
        result.error = None
        assert result.success is True
        assert result.error is None


class TestValidateSpawnDepth:
    def test_depth_1_returns_true(self) -> None:
        assert validate_spawn_depth(1) is True

    def test_depth_2_returns_true(self) -> None:
        assert validate_spawn_depth(2) is True

    def test_depth_3_returns_false(self) -> None:
        assert validate_spawn_depth(3) is False

    def test_depth_0_returns_false(self) -> None:
        assert validate_spawn_depth(0) is False

    def test_negative_depth_returns_false(self) -> None:
        assert validate_spawn_depth(-1) is False


class FakeRegistry:
    def __init__(self, allowed: bool = True) -> None:
        self._allowed = allowed

    def validate_delegation(self, parent_agent: str, target_agent: str) -> bool:
        return self._allowed


class TestSpawnSubAgentValidated:
    @pytest.mark.asyncio
    async def test_valid_spawn_returns_success(self, valid_handoff: HandoffRequest) -> None:
        result = await spawn_subagent_validated(
            target_agent="search_agent",
            handoff_request=valid_handoff,
        )
        assert result.success is True
        assert result.target_agent == "search_agent"
        assert result.spawn_depth == 1
        assert result.trace_id == "trace-spawn-001"

    @pytest.mark.asyncio
    async def test_valid_spawn_with_envelope(
        self, valid_handoff: HandoffRequest, envelope: ContextEnvelope
    ) -> None:
        result = await spawn_subagent_validated(
            target_agent="search_agent",
            handoff_request=valid_handoff,
            envelope=envelope,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_delegation_allowed_by_registry(self, valid_handoff: HandoffRequest) -> None:
        registry = FakeRegistry(allowed=True)
        result = await spawn_subagent_validated(
            target_agent="search_agent",
            handoff_request=valid_handoff,
            registry=registry,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_delegation_denied_by_registry(self, valid_handoff: HandoffRequest) -> None:
        registry = FakeRegistry(allowed=False)
        result = await spawn_subagent_validated(
            target_agent="search_agent",
            handoff_request=valid_handoff,
            registry=registry,
        )
        assert result.success is False
        assert "not allowed by registry" in (result.error or "")

    @pytest.mark.asyncio
    async def test_depth_exceeded_returns_failure(self) -> None:
        handoff = HandoffRequest.model_construct(
            goal="Too deep",
            trace_id="trace-deep",
            parent_agent="conductor",
            spawn_depth=3,
        )
        result = await spawn_subagent_validated(
            target_agent="search_agent",
            handoff_request=handoff,
        )
        assert result.success is False
        assert "exceeds maximum" in (result.error or "")

    @pytest.mark.asyncio
    async def test_missing_required_fields_handoff(self) -> None:
        handoff = HandoffRequest.model_construct(
            goal=None,
            trace_id=None,
            parent_agent=None,
        )
        result = await spawn_subagent_validated(
            target_agent="search_agent",
            handoff_request=handoff,
        )
        assert result.success is False
        assert "missing required fields" in (result.error or "")
