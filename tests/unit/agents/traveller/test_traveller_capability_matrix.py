"""Static checks on traveller-agent entry in agent_capability_matrix.yaml.

Verifica che:
- entry traveller-agent esiste in capability matrix
- allowed_tools include proxy, memory, hitl, sequential, spawn
- mcp_dependencies = [aria-mcp-proxy, aria-memory]
- delegation_targets include productivity-agent, search-agent
- intent_categories include keys travel.*
- hitl_triggers includono destructive, costly
- max_tools: 20, max_spawn_depth: 1
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

YAML_PATH = Path(".aria/config/agent_capability_matrix.yaml")


@pytest.fixture(scope="module")
def matrix() -> list[dict]:
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))["agents"]


@pytest.fixture(scope="module")
def trav(matrix) -> dict:
    by_name = {a["name"]: a for a in matrix}
    assert "traveller-agent" in by_name, "traveller-agent missing from matrix"
    return by_name["traveller-agent"]


def test_type(trav: dict):
    assert trav["type"] == "worker"


def test_description(trav: dict):
    desc = trav.get("description", "")
    assert "viaggi" in desc.lower() or "travel" in desc.lower()
    assert "NON" in desc


def test_proxy_tools(trav: dict):
    tools = trav["allowed_tools"]
    assert "aria-mcp-proxy__search_tools" in tools
    assert "aria-mcp-proxy__call_tool" in tools


def test_memory_tools(trav: dict):
    tools = trav["allowed_tools"]
    for t in ("wiki_update_tool", "wiki_recall_tool", "wiki_show_tool", "wiki_list_tool"):
        assert f"aria-memory__{t}" in tools


def test_hitl(trav: dict):
    assert "hitl-queue__ask" in trav["allowed_tools"]


def test_sequential(trav: dict):
    assert "sequential-thinking__*" in trav["allowed_tools"]


def test_spawn(trav: dict):
    assert "spawn-subagent" in trav["allowed_tools"]


def test_mcp_deps(trav: dict):
    deps = set(trav["mcp_dependencies"])
    assert {"aria-mcp-proxy", "aria-memory"}.issubset(deps)


def test_delegation_targets(trav: dict):
    targets = set(trav["delegation_targets"])
    assert "productivity-agent" in targets
    assert "search-agent" in targets


def test_hitl_triggers(trav: dict):
    triggers = set(trav["hitl_triggers"])
    assert "destructive" in triggers
    assert "costly" in triggers


def test_intent_categories(trav: dict):
    intents = set(trav["intent_categories"])
    expected = {
        "travel.destination",
        "travel.transport",
        "travel.accommodation",
        "travel.activity",
        "travel.itinerary",
        "travel.budget",
        "travel.brief",
    }
    assert expected.issubset(intents)


def test_max_tools(trav: dict):
    assert trav["max_tools"] == 20


def test_max_spawn_depth(trav: dict):
    assert trav["max_spawn_depth"] == 1


def test_conductor_delegation_includes_traveller(matrix):
    conductor = next(a for a in matrix if a["name"] == "aria-conductor")
    assert "traveller-agent" in conductor["delegation_targets"]
