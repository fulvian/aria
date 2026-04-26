"""Static checks on the aria-conductor agent prompt to enforce memory persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

AGENT_FILE = Path(".aria/kilocode/agents/aria-conductor.md")


@pytest.fixture(scope="module")
def agent_text() -> str:
    return AGENT_FILE.read_text(encoding="utf-8")


def test_remember_tool_is_allowed(agent_text: str) -> None:
    assert "aria-memory/remember" in agent_text, (
        "aria-conductor must declare aria-memory/remember in allowed-tools"
    )


def test_remember_user_input_is_mandatory(agent_text: str) -> None:
    must_contain = [
        "PRIMA di rispondere",
        "aria-memory/remember",
        "actor=user_input",
    ]
    for fragment in must_contain:
        assert fragment in agent_text, f"missing required fragment: {fragment!r}"


def test_remember_assistant_output_is_mandatory(agent_text: str) -> None:
    assert "actor=agent_inference" in agent_text


def test_session_id_resolved_automatically(agent_text: str) -> None:
    assert "NON passare session_id" in agent_text or "risolto automaticamente" in agent_text


def test_mcp_dependency_declared(agent_text: str) -> None:
    assert "mcp-dependencies:" in agent_text
    after = agent_text.split("mcp-dependencies:", 1)[1]
    lines = after.splitlines()
    # aria-memory must appear in first 3 lines after the key
    found = any("aria-memory" in line for line in lines[:3])
    assert found, "aria-memory must be listed in mcp-dependencies"
