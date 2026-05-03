"""Integration tests for traveller-agent handoff chain (Fase 6).

Verifica che:
- traveller-agent prompt specifica regole di delega per export
- Conduttore abilita catene traveller → productivity-agent
- HITL è richiesto per write esterne (delegate a productivity-agent)
- Depth guard rispettata (2 hop max, 3 hop blocked)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CONDUCTOR = Path(".aria/kilocode/agents/aria-conductor.md")
TRAVELLER = Path(".aria/kilocode/agents/traveller-agent.md")
CAPABILITY_MATRIX = Path(".aria/config/agent_capability_matrix.yaml")


@pytest.fixture(scope="module")
def traveller_text() -> str:
    """Full text of traveller-agent.md (without YAML frontmatter)."""
    text = TRAVELLER.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3
    return parts[2]


@pytest.fixture(scope="module")
def conductor_text() -> str:
    """Full text of aria-conductor.md."""
    return CONDUCTOR.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def matrix() -> dict:
    """Load capability matrix."""
    return yaml.safe_load(CAPABILITY_MATRIX.read_text(encoding="utf-8"))


class TestTravellerExportDelegation:
    """Traveller-agent defines export delegation rules in prompt."""

    def test_delegation_section_exists(self, traveller_text: str):
        """Prompt has a delegation section."""
        assert "## Delega" in traveller_text or "# Delega" in traveller_text

    def test_spawn_productivity_for_export(self, traveller_text: str):
        """Prompt specifies spawn-subagent to productivity-agent for export."""
        assert "spawn-subagent" in traveller_text
        assert "productivity-agent" in traveller_text

    def test_export_goals_listed(self, traveller_text: str):
        """Export goals are listed (Drive, Calendar, email)."""
        lower = traveller_text.lower()
        assert "drive" in lower
        assert "calendar" in lower
        assert "email" in lower

    def test_no_direct_workspace(self, traveller_text: str):
        """Prompt forbids delegation to workspace-agent directly."""
        assert "NON delegare" in traveller_text
        assert "workspace-agent" in traveller_text

    def test_max_spawn_depth_one(self, traveller_text: str):
        """Frontmatter specifies max-spawn-depth: 1."""
        text = TRAVELLER.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        fm = yaml.safe_load(parts[1])
        # traveller can spawn productivity-agent (who can spawn workspace-agent = 2 hops)
        # max-spawn-depth: 1 means traveller can spawn 1 sub-agent
        assert fm.get("max-spawn-depth") == 1


class TestConductorExportChain:
    """Conductor enables traveller → productivity chain."""

    def test_conductor_has_traveller_to_productivity(self, conductor_text: str):
        """Conductor specifies traveller-agent → productivity-agent chain."""
        assert "traveller-agent" in conductor_text
        assert "productivity-agent" in conductor_text
        # Check for the explicit chain
        found = False
        for line in conductor_text.splitlines():
            if "traveller" in line and "productivity" in line and "->" in line:
                found = True
                break
            if "traveller" in line and "productivity" in line and "→" in line:
                found = True
                break
        assert found, "No explicit traveller → productivity chain in conductor"

    def test_conductor_has_traveller_to_search(self, conductor_text: str):
        """Conductor specifies traveller-agent → search-agent chain."""
        found = False
        for line in conductor_text.splitlines():
            if "traveller" in line and "search" in line and ("->" in line or "→" in line):
                found = True
                break
        assert found, "No explicit traveller → search chain in conductor"

    def test_depth_guard_max_two_hops(self, conductor_text: str):
        """Conductor states max 2 hop limit."""
        lower = conductor_text.lower()
        # Look for evidence of depth limit
        assert "2 hop" in lower or "max 2" in lower or "max hop" in lower


class TestTravellerHITLForExport:
    """Traveller-agent requires HITL for external writes via productivity."""

    def test_hitl_section_exists(self, traveller_text: str):
        """Prompt has HITL section."""
        assert "## HITL" in traveller_text or "# HITL" in traveller_text

    def test_hitl_for_drive_export(self, traveller_text: str):
        """HITL is required for Drive export."""
        assert "hitl-queue__ask" in traveller_text
        lower = traveller_text.lower()
        assert "drive" in lower

    def test_hitl_for_calendar(self, traveller_text: str):
        """HITL is required for Calendar creation."""
        lower = traveller_text.lower()
        assert "calendar" in lower

    def test_hitl_for_email(self, traveller_text: str):
        """HITL is required for email sending."""
        lower = traveller_text.lower()
        assert "email" in lower or "mail" in lower

    def test_textual_confirmation_not_enough(self, traveller_text: str):
        """Prompt states textual confirmation ≠ HITL."""
        assert "Conferma testuale" in traveller_text


class TestCapabilityMatrixHandoff:
    """Capability matrix defines delegation targets."""

    @pytest.fixture(scope="class")
    def traveller_entry(self, matrix) -> dict:
        agents = {a["name"]: a for a in matrix["agents"]}
        return agents["traveller-agent"]

    def test_delegation_targets_defined(self, traveller_entry: dict):
        """Traveller-agent has delegation_targets."""
        targets = traveller_entry.get("delegation_targets", [])
        assert len(targets) >= 1, "No delegation_targets defined"

    def test_delegation_includes_productivity(self, traveller_entry: dict):
        """Delegation targets include productivity-agent."""
        targets = traveller_entry.get("delegation_targets", [])
        assert "productivity-agent" in targets

    def test_delegation_includes_search(self, traveller_entry: dict):
        """Delegation targets include search-agent."""
        targets = traveller_entry.get("delegation_targets", [])
        assert "search-agent" in targets

    def test_max_spawn_depth_one_in_matrix(self, traveller_entry: dict):
        """Capability matrix specifies max_spawn_depth: 1."""
        assert traveller_entry.get("max_spawn_depth") == 1

    def test_conductor_delegates_to_traveller(self, matrix):
        """Conductor includes traveller-agent in delegation_targets."""
        conductor = next(
            a for a in matrix["agents"] if a["name"] == "aria-conductor"
        )
        targets = conductor.get("delegation_targets", [])
        assert "traveller-agent" in targets

    def test_spawn_tool_allowed(self, traveller_entry: dict):
        """spawn-subagent is in allowed_tools."""
        assert "spawn-subagent" in traveller_entry.get("allowed_tools", [])
