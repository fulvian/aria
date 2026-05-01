from __future__ import annotations

from pathlib import Path

SEARCH_AGENT_FILE = Path(".aria/kilocode/agents/search-agent.md")


def test_search_agent_grounding_rules_are_explicit() -> None:
    agent_text = SEARCH_AGENT_FILE.read_text(encoding="utf-8")

    required_fragments = [
        "deve comparire esplicitamente nel tool output",
        "mancante o non verificato",
        "l'ultima ricerca grounded della sessione",
        "Non introdurre nuovi fatti non presenti",
    ]
    for fragment in required_fragments:
        assert fragment in agent_text
