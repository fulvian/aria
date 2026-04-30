"""Integration tests: handoff payload validation — free-form rejected, valid accepted."""

from __future__ import annotations

import pytest

from aria.agents.coordination.handoff import (
    HandoffRequest,
    HandoffValidationError,
    validate_handoff,
)


class TestHandoffValidation:
    """Validate_handoff must reject free-form dicts and accept well-formed payloads."""

    def test_payload_free_form_rejected(self) -> None:
        """A dict with extra/unknown fields raises HandoffValidationError."""
        payload = {
            "goal": "Find documentation for the API",
            "trace_id": "trace-abc",
            "parent_agent": "aria-conductor",
            "spawn_depth": 1,
            "bogus_field": "this should be forbidden",
        }
        with pytest.raises(HandoffValidationError):
            validate_handoff(payload)

    def test_payload_valid_accepted(self) -> None:
        """A minimal valid payload returns a HandoffRequest instance."""
        payload = {
            "goal": "Find documentation for the API",
            "trace_id": "trace-abc",
            "parent_agent": "aria-conductor",
            "spawn_depth": 1,
        }
        request = validate_handoff(payload)
        assert isinstance(request, HandoffRequest)
        assert request.goal == "Find documentation for the API"
        assert request.trace_id == "trace-abc"
        assert request.parent_agent == "aria-conductor"
        assert request.spawn_depth == 1
        assert request.timeout_seconds == 120

    def test_payload_missing_required_field_rejected(self) -> None:
        """A dict missing 'goal' raises HandoffValidationError."""
        payload = {
            "trace_id": "trace-abc",
            "parent_agent": "aria-conductor",
        }
        with pytest.raises(HandoffValidationError):
            validate_handoff(payload)

    def test_payload_not_a_dict_rejected(self) -> None:
        """Passing a non-dict raises HandoffValidationError."""
        with pytest.raises(HandoffValidationError):
            validate_handoff("not a dict")  # type: ignore[arg-type]
