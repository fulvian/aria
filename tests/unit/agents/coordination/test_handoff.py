from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from aria.agents.coordination import (
    HandoffRequest,
    HandoffResult,
    HandoffValidationError,
    validate_handoff,
)


class TestHandoffRequestCreation:
    def test_valid_fields(self) -> None:
        req = HandoffRequest(
            goal="Research the latest AI trends",
            trace_id="trace-001",
            parent_agent="conductor",
        )
        assert req.goal == "Research the latest AI trends"
        assert req.trace_id == "trace-001"
        assert req.parent_agent == "conductor"
        assert req.timeout_seconds == 120
        assert req.spawn_depth == 1
        assert req.constraints is None
        assert req.required_output is None
        assert req.envelope_ref is None

    def test_goal_max_length_enforced(self) -> None:
        with pytest.raises(ValidationError):
            HandoffRequest(
                goal="x" * 501,
                trace_id="trace-001",
                parent_agent="conductor",
            )

    def test_goal_boundary_allowed(self) -> None:
        req = HandoffRequest(
            goal="x" * 500,
            trace_id="trace-001",
            parent_agent="conductor",
        )
        assert len(req.goal) == 500

    def test_timeout_range_low(self) -> None:
        with pytest.raises(ValidationError):
            HandoffRequest(
                goal="test",
                trace_id="trace-001",
                parent_agent="conductor",
                timeout_seconds=9,
            )

    def test_timeout_range_high(self) -> None:
        with pytest.raises(ValidationError):
            HandoffRequest(
                goal="test",
                trace_id="trace-001",
                parent_agent="conductor",
                timeout_seconds=301,
            )

    def test_timeout_boundaries(self) -> None:
        req = HandoffRequest(
            goal="test",
            trace_id="trace-001",
            parent_agent="conductor",
            timeout_seconds=10,
        )
        assert req.timeout_seconds == 10
        req2 = HandoffRequest(
            goal="test",
            trace_id="trace-001",
            parent_agent="conductor",
            timeout_seconds=300,
        )
        assert req2.timeout_seconds == 300

    def test_spawn_depth_range(self) -> None:
        req = HandoffRequest(
            goal="test",
            trace_id="trace-001",
            parent_agent="conductor",
            spawn_depth=1,
        )
        assert req.spawn_depth == 1
        req2 = HandoffRequest(
            goal="test",
            trace_id="trace-001",
            parent_agent="conductor",
            spawn_depth=2,
        )
        assert req2.spawn_depth == 2

    def test_spawn_depth_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            HandoffRequest(
                goal="test",
                trace_id="trace-001",
                parent_agent="conductor",
                spawn_depth=0,
            )
        with pytest.raises(ValidationError):
            HandoffRequest(
                goal="test",
                trace_id="trace-001",
                parent_agent="conductor",
                spawn_depth=3,
            )

    def test_optional_fields_none(self) -> None:
        req = HandoffRequest(
            goal="test",
            trace_id="trace-001",
            parent_agent="conductor",
        )
        assert req.constraints is None
        assert req.required_output is None
        assert req.envelope_ref is None

    def test_optional_fields_set(self) -> None:
        req = HandoffRequest(
            goal="test",
            trace_id="trace-001",
            parent_agent="conductor",
            constraints="Only use web search",
            required_output="A markdown report",
            envelope_ref="env-123",
        )
        assert req.constraints == "Only use web search"
        assert req.required_output == "A markdown report"
        assert req.envelope_ref == "env-123"

    def test_model_dump_roundtrip(self) -> None:
        req = HandoffRequest(
            goal="Draft an email",
            constraints="Formal tone",
            required_output="Email body",
            timeout_seconds=60,
            trace_id="trace-002",
            parent_agent="productivity_agent",
            spawn_depth=2,
            envelope_ref="env-456",
        )
        data = req.model_dump()
        restored = HandoffRequest.model_validate(data)
        assert restored.goal == req.goal
        assert restored.constraints == req.constraints
        assert restored.required_output == req.required_output
        assert restored.timeout_seconds == req.timeout_seconds
        assert restored.trace_id == req.trace_id
        assert restored.parent_agent == req.parent_agent
        assert restored.spawn_depth == req.spawn_depth
        assert restored.envelope_ref == req.envelope_ref

    def test_serialization_to_json(self) -> None:
        req = HandoffRequest(
            goal="Summarize the document",
            trace_id="trace-003",
            parent_agent="conductor",
        )
        json_str = req.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["goal"] == "Summarize the document"
        assert parsed["trace_id"] == "trace-003"
        assert parsed["parent_agent"] == "conductor"
        assert parsed["timeout_seconds"] == 120
        assert parsed["spawn_depth"] == 1

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            HandoffRequest(
                goal="test",
                trace_id="trace-001",
                parent_agent="conductor",
                unknown_field="should not be allowed",
            )

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            HandoffRequest(goal="test")


class TestValidateHandoff:
    def test_valid_dict(self) -> None:
        payload = {
            "goal": "Search for papers",
            "trace_id": "trace-010",
            "parent_agent": "conductor",
        }
        result = validate_handoff(payload)
        assert isinstance(result, HandoffRequest)
        assert result.goal == "Search for papers"

    def test_missing_required_fields_raises(self) -> None:
        payload = {"goal": "test"}
        with pytest.raises(HandoffValidationError):
            validate_handoff(payload)

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(HandoffValidationError):
            validate_handoff("not a dict")

    def test_with_all_fields(self) -> None:
        payload = {
            "goal": "Calculate revenue",
            "constraints": "Use 2024 data",
            "required_output": "CSV file",
            "timeout_seconds": 90,
            "trace_id": "trace-011",
            "parent_agent": "analytics_agent",
            "spawn_depth": 2,
            "envelope_ref": "env-789",
        }
        result = validate_handoff(payload)
        assert result.goal == "Calculate revenue"
        assert result.constraints == "Use 2024 data"
        assert result.timeout_seconds == 90
        assert result.spawn_depth == 2


class TestHandoffResult:
    def test_creation_with_minimal_fields(self) -> None:
        result = HandoffResult(success=True)
        assert result.success is True
        assert result.output is None
        assert result.failure_reason is None
        assert result.duration_ms == 0
        assert result.trace_id == ""
        assert result.child_agent == ""

    def test_creation_with_all_fields(self) -> None:
        result = HandoffResult(
            success=False,
            output=None,
            failure_reason="Timeout exceeded",
            duration_ms=15000,
            trace_id="trace-020",
            child_agent="search_agent",
        )
        assert result.success is False
        assert result.failure_reason == "Timeout exceeded"
        assert result.duration_ms == 15000
        assert result.trace_id == "trace-020"
        assert result.child_agent == "search_agent"

    def test_dataclass_mutation(self) -> None:
        result = HandoffResult(success=True, output="partial result")
        result.success = False
        result.failure_reason = "Error during execution"
        assert result.success is False
        assert result.failure_reason == "Error during execution"
