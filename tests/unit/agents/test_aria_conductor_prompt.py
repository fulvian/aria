"""Static checks on the aria-conductor agent prompt to enforce memory persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

AGENT_FILE = Path(".aria/kilocode/agents/aria-conductor.md")


@pytest.fixture(scope="module")
def agent_text() -> str:
    return AGENT_FILE.read_text(encoding="utf-8")


def test_remember_tool_is_allowed(agent_text: str) -> None:
    assert "aria-memory/wiki_update_tool" in agent_text or "aria-memory/remember" in agent_text, (
        "aria-conductor must declare wiki_update_tool or remember in allowed-tools"
    )


def test_complete_turn_tool_is_allowed(agent_text: str) -> None:
    assert (
        "aria-memory/wiki_update_tool" in agent_text or "aria-memory/complete_turn" in agent_text
    ), "aria-conductor must declare wiki_update_tool or complete_turn in allowed-tools"


def test_remember_user_input_is_mandatory(agent_text: str) -> None:
    must_contain = [
        "PRIMA di rispondere",
        "wiki_recall",
    ]
    for fragment in must_contain:
        assert fragment in agent_text, f"missing required fragment: {fragment!r}"


def test_complete_turn_is_mandatory(agent_text: str) -> None:
    assert "wiki_update_tool" in agent_text or "complete_turn" in agent_text
    assert "patches" in agent_text or "response_text" in agent_text


def test_session_id_resolved_automatically(agent_text: str) -> None:
    assert (
        "NON passare session_id" in agent_text
        or "risolto automaticamente" in agent_text
        or "lasciati vuoti" in agent_text
    )


def test_mcp_dependency_declared(agent_text: str) -> None:
    assert "mcp-dependencies:" in agent_text
    after = agent_text.split("mcp-dependencies:", 1)[1]
    lines = after.splitlines()
    found = any("aria-memory" in line for line in lines[:3])
    assert found, "aria-memory must be listed in mcp-dependencies"


def test_search_grounding_rules_are_explicit(agent_text: str) -> None:
    required_fragments = [
        "film, orari, sale, indirizzi o liste",
        "dichiaralo come",
        "mancante invece di inferirlo",
        "stessa sessione",
    ]
    for fragment in required_fragments:
        assert fragment in agent_text
