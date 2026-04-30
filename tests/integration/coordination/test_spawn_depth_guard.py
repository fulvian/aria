"""Integration tests: spawn depth guard — depth=3 rejected, depth=1 accepted."""

from __future__ import annotations

from aria.agents.coordination.handoff import HandoffRequest
from aria.agents.coordination.spawn import spawn_subagent_validated, validate_spawn_depth


def _make_handoff(*, spawn_depth: int) -> HandoffRequest:
    return HandoffRequest.model_construct(
        goal="Test goal",
        trace_id="trace-depth-guard",
        parent_agent="aria-conductor",
        spawn_depth=spawn_depth,
    )


class TestSpawnDepthGuard:
    """Spawn depth must be 1 or 2; depth=3 is rejected."""

    async def test_depth_3_rejected(self) -> None:
        result = await spawn_subagent_validated(
            target_agent="search-agent",
            handoff_request=_make_handoff(spawn_depth=3),
        )
        assert result.success is False
        assert result.spawn_depth == 3
        assert result.error is not None
        assert "depth" in result.error.lower()

    async def test_depth_1_accepted(self) -> None:
        result = await spawn_subagent_validated(
            target_agent="search-agent",
            handoff_request=_make_handoff(spawn_depth=1),
        )
        assert result.success is True
        assert result.spawn_depth == 1
        assert result.error is None

    async def test_depth_2_accepted(self) -> None:
        result = await spawn_subagent_validated(
            target_agent="search-agent",
            handoff_request=_make_handoff(spawn_depth=2),
        )
        assert result.success is True
        assert result.spawn_depth == 2

    def test_validate_spawn_depth_function(self) -> None:
        assert validate_spawn_depth(1) is True
        assert validate_spawn_depth(2) is True
        assert validate_spawn_depth(3) is False
        assert validate_spawn_depth(0) is False
