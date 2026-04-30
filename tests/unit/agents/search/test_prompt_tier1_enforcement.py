from __future__ import annotations

from pathlib import Path

SEARCH_AGENT_PROMPT = Path(".aria/kilocode/agents/search-agent.md")
DEEP_RESEARCH_SKILL = Path(".aria/kilocode/skills/deep-research/SKILL.md")
CONDUCTOR_PROMPT = Path(".aria/kilocode/agents/aria-conductor.md")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_search_agent_has_anti_bypass_gate() -> None:
    text = _read(SEARCH_AGENT_PROMPT)

    assert "GATE DI ESECUZIONE OBBLIGATORIO" in text
    assert "searxng-script/search" in text
    assert "reddit-search/search" in text
    assert "Tier-1 evidence:" in text


def test_deep_research_skill_has_anti_bypass_gate() -> None:
    text = _read(DEEP_RESEARCH_SKILL)

    assert "Gate anti-bypass provider a pagamento" in text
    assert "searxng-script/search" in text
    assert "reddit-search/search" in text
    assert "Tier-1 evidence:" in text


def test_conductor_constraints_include_tier1_first() -> None:
    text = _read(CONDUCTOR_PROMPT)

    assert "tier1-first obbligatorio" in text
    assert "searxng poi reddit" in text
