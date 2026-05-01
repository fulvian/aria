"""Static checks on productivity-agent prompt and core work-domain skills.

Ensures the unified work-domain agent is constrained to the canonical proxy path,
uses real HITL gating, and avoids native host helpers for ordinary file workflows.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PRODUCTIVITY_FILE = Path(".aria/kilocode/agents/productivity-agent.md")
EMAIL_DRAFT_SKILL = Path(".aria/kilocode/skills/email-draft/SKILL.md")
MEETING_PREP_SKILL = Path(".aria/kilocode/skills/meeting-prep/SKILL.md")
OFFICE_INGEST_SKILL = Path(".aria/kilocode/skills/office-ingest/SKILL.md")
CONSULTANCY_BRIEF_SKILL = Path(".aria/kilocode/skills/consultancy-brief/SKILL.md")


def _split_frontmatter(path: Path) -> tuple[dict, str]:
    content = path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    assert len(parts) >= 3, f"{path}: YAML frontmatter not found"
    return yaml.safe_load(parts[1]), parts[2]


@pytest.fixture(scope="module")
def productivity_yaml() -> dict:
    data, _ = _split_frontmatter(PRODUCTIVITY_FILE)
    return data


@pytest.fixture(scope="module")
def productivity_text() -> str:
    _, text = _split_frontmatter(PRODUCTIVITY_FILE)
    return text


class TestProductivityAgentProxyContract:
    def test_allowed_tools_expose_proxy_surface(self, productivity_yaml: dict) -> None:
        allowed = set(productivity_yaml.get("allowed-tools", []))
        assert "aria-mcp-proxy__search_tools" in allowed
        assert "aria-mcp-proxy__call_tool" in allowed
        assert "hitl-queue__ask" in allowed

    def test_proxy_caller_id_rule_explicit(self, productivity_text: str) -> None:
        assert '_caller_id: "productivity-agent"' in productivity_text

    def test_forbids_native_host_helpers_for_ordinary_workflows(
        self, productivity_text: str
    ) -> None:
        for fragment in ["Glob", "Read", "Write", "TodoWrite"]:
            assert fragment in productivity_text
        assert "NON usare tool nativi Kilo/host" in productivity_text

    def test_requires_proxy_for_filesystem_and_docs(self, productivity_text: str) -> None:
        required = [
            "filesystem__list_directory",
            "filesystem__read",
            "markitdown-mcp__convert_to_markdown",
            "Google Workspace",
        ]
        for fragment in required:
            assert fragment in productivity_text

    def test_forbids_runtime_self_remediation_during_user_workflows(
        self, productivity_text: str
    ) -> None:
        assert "NON modificare codice" in productivity_text
        assert "NON editare file di" in productivity_text
        assert "configurazione" in productivity_text
        assert "NON killare processi" in productivity_text
        assert "NON fare auto-remediation runtime" in productivity_text

    def test_hitl_must_be_real_tool_gate(self, productivity_text: str) -> None:
        required = [
            "Non basta una richiesta testuale di conferma",
            "hitl-queue__ask",
            "non è pronta per esecuzione operativa",
        ]
        for fragment in required:
            assert fragment in productivity_text

    def test_wiki_update_must_be_single_and_valid(self, productivity_text: str) -> None:
        required = [
            "esattamente una sola volta",
            "payload valido",
            "non memorializzarlo come successo canonico",
        ]
        for fragment in required:
            assert fragment in productivity_text


class TestWorkDomainSkillsContract:
    @pytest.mark.parametrize(
        ("path", "required_fragments"),
        [
            (
                OFFICE_INGEST_SKILL,
                [
                    "backend filesystem via proxy",
                    "filesystem__read",
                    "markitdown-mcp__convert_to_markdown",
                ],
            ),
            (
                CONSULTANCY_BRIEF_SKILL,
                [
                    "non con tool host tipo `Glob`",
                    "backend filesystem",
                ],
            ),
            (
                EMAIL_DRAFT_SKILL,
                [
                    "Una semplice richiesta testuale di conferma nella risposta NON è sufficiente",
                    "hitl-queue/ask",
                    "`wiki_update_tool` al massimo una volta per turno",
                ],
            ),
            (
                MEETING_PREP_SKILL,
                [
                    "hitl-queue__ask",
                    "non sostituirlo con una semplice domanda testuale finale",
                ],
            ),
        ],
    )
    def test_skill_contains_required_contract_fragments(
        self, path: Path, required_fragments: list[str]
    ) -> None:
        text = path.read_text(encoding="utf-8")
        for fragment in required_fragments:
            assert fragment in text, f"{path}: missing {fragment!r}"
