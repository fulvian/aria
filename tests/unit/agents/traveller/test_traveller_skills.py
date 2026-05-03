"""Static tests for traveller-agent skill files.

Verifica che ogni skill dichiarata in traveller-agent prompt:
- Esista come file SKILL.md in .aria/kilocode/skills/<name>/
- Frontmatter YAML valido
- Sia registrata in _registry.json
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

SKILLS_DIR = Path(".aria/kilocode/skills")
REGISTRY_PATH = SKILLS_DIR / "_registry.json"
TRAVELLER_PROMPT = Path(".aria/kilocode/agents/traveller-agent.md")


def _required_travel_skills() -> list[str]:
    """Extract required-skills list from traveller-agent frontmatter."""
    if not TRAVELLER_PROMPT.exists():
        pytest.skip("traveller-agent prompt not found")
    text = TRAVELLER_PROMPT.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3
    fm = yaml.safe_load(parts[1])
    return fm.get("required-skills", [])


@pytest.fixture(scope="module")
def registry() -> dict:
    """Load skill registry."""
    if not REGISTRY_PATH.exists():
        pytest.skip("_registry.json not found")
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


class TestTravellerSkillRegistration:
    """Every required skill exists, has SKILL.md, and is registered."""

    def test_traveller_agent_declares_skills(self):
        """Traveller-agent declares required-skills in frontmatter."""
        skills = _required_travel_skills()
        assert len(skills) >= 6, (
            f"Expected >=6 skills, got {len(skills)}: {skills}"
        )
        expected = [
            "destination-research",
            "accommodation-comparison",
            "transport-planning",
            "activity-planning",
            "itinerary-building",
            "budget-analysis",
        ]
        for s in expected:
            assert s in skills, f"Missing required skill: {s}"

    def test_implemented_skills_in_registry(self, registry):
        """Every travel skill with a SKILL.md is registered in _registry.json."""
        skills = _required_travel_skills()
        # Only check skills that have a SKILL.md file (implemented ones)
        implemented = [
            s for s in skills if (SKILLS_DIR / s / "SKILL.md").exists()
        ]
        registered = {s["name"] for s in registry["skills"]}
        missing = set(implemented) - registered
        assert not missing, f"Implemented skills not in registry: {missing}"

    @pytest.mark.parametrize("skill_name", [
        "destination-research",
        "accommodation-comparison",
        "transport-planning",
    ])
    def test_skill_has_skill_file(self, skill_name: str):
        """Each implemented skill has a SKILL.md file."""
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_file.exists(), f"Missing SKILL.md for {skill_name}"

    @pytest.mark.parametrize("skill_name", [
        "destination-research",
        "accommodation-comparison",
        "transport-planning",
    ])
    def test_skill_frontmatter_valid(self, skill_name: str):
        """Each SKILL.md has valid YAML frontmatter."""
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        text = skill_file.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        assert len(parts) >= 3, f"No frontmatter in {skill_name}/SKILL.md"
        fm = yaml.safe_load(parts[1])
        assert fm["name"] == skill_name
        assert any("proxy" in t for t in fm.get("allowed-tools", [])), (
            f"Skill {skill_name} must allow proxy tools"
        )
        assert "description" in fm
        assert "version" in fm

    @pytest.mark.parametrize("skill_name", [
        "destination-research",
        "accommodation-comparison",
        "transport-planning",
    ])
    def test_skill_in_registry(self, registry, skill_name: str):
        """Each skill is registered in _registry.json."""
        registered = {s["name"]: s for s in registry["skills"]}
        assert skill_name in registered, f"Skill {skill_name} not registered"
        entry = registered[skill_name]
        assert entry["category"] == "travel"
        assert "SKILL.md" in entry["path"]

    def test_registry_entry_format(self, registry):
        """Registry entries have required fields."""
        travel_skills = [
            s for s in registry["skills"] if s["category"] == "travel"
        ]
        for s in travel_skills:
            assert "name" in s
            assert "path" in s
            assert "version" in s
            assert "category" in s
