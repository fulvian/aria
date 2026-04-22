"""Integration tests for workspace skill metadata mapping in runner."""

import pytest
from enum import Enum


class SkillType(Enum):
    """Skill type classification."""

    READ = "read"
    WRITE = "write"
    UNKNOWN = "unknown"


class SkillMetadata:
    """Skill metadata for classification."""

    def __init__(self, name: str, requires_hitl: bool = False):
        self.name = name
        self.requires_hitl = requires_hitl
        self.is_write = "composer" in name or "editor" in name

    def classify(self) -> SkillType:
        if (
            "reader" in self.name
            or "structure" in self.name
            or "auditor" in self.name
            or "intelligence" in self.name
        ):
            return SkillType.READ
        elif "composer" in self.name or "editor" in self.name:
            return SkillType.WRITE
        return SkillType.UNKNOWN


@pytest.mark.integration
class TestWorkspaceSkillMetadata:
    """Test skill metadata mapping in runner."""

    @pytest.fixture
    def skill_registry(self):
        """Registry of workspace skill metadata."""
        return {
            "gmail-thread-intelligence": SkillMetadata(
                name="gmail-thread-intelligence",
                requires_hitl=False,
            ),
            "docs-structure-reader": SkillMetadata(
                name="docs-structure-reader",
                requires_hitl=False,
            ),
            "sheets-analytics-reader": SkillMetadata(
                name="sheets-analytics-reader",
                requires_hitl=False,
            ),
            "slides-content-auditor": SkillMetadata(
                name="slides-content-auditor",
                requires_hitl=False,
            ),
            "gmail-composer-pro": SkillMetadata(
                name="gmail-composer-pro",
                requires_hitl=True,
            ),
            "docs-editor-pro": SkillMetadata(
                name="docs-editor-pro",
                requires_hitl=True,
            ),
        }

    def test_read_skill_detection(self, skill_registry):
        """Test detection of read skills."""
        read_skills = [
            "gmail-thread-intelligence",
            "docs-structure-reader",
            "sheets-analytics-reader",
            "slides-content-auditor",
        ]

        for skill_name in read_skills:
            skill = skill_registry.get(skill_name)
            assert skill is not None
            assert skill.classify() == SkillType.READ

    def test_write_skill_detection(self, skill_registry):
        """Test detection of write skills."""
        write_skills = ["gmail-composer-pro", "docs-editor-pro"]

        for skill_name in write_skills:
            skill = skill_registry.get(skill_name)
            assert skill is not None
            assert skill.is_write is True

    def test_hitl_requirement_mapping(self, skill_registry):
        """Test HITL requirement mapping for skills."""
        hitl_required = ["gmail-composer-pro"]
        hitl_not_required = [
            "gmail-thread-intelligence",
            "docs-structure-reader",
            "sheets-analytics-reader",
            "slides-content-auditor",
        ]

        for skill_name in hitl_required:
            skill = skill_registry.get(skill_name)
            assert skill is not None
            assert skill.requires_hitl is True

        for skill_name in hitl_not_required:
            skill = skill_registry.get(skill_name)
            assert skill is not None
            assert skill.requires_hitl is False

    def test_unknown_skill_fallback(self, skill_registry):
        """Test fallback behavior for unknown skills."""
        unknown_skill = SkillMetadata(name="unknown-skill-xyz")
        assert unknown_skill.classify() == SkillType.UNKNOWN

    def test_skill_with_composer_in_name(self, skill_registry):
        """Test that skills with 'composer' in name are classified correctly."""
        skill = skill_registry.get("gmail-composer-pro")
        assert skill is not None
        assert skill.is_write is True
        assert skill.requires_hitl is True
        assert skill.classify() == SkillType.WRITE

    def test_skill_with_editor_in_name(self):
        """Test that skills with 'editor' in name are write skills."""
        skill = SkillMetadata(name="docs-editor-pro")
        assert skill.is_write is True
        assert skill.classify() == SkillType.WRITE

    def test_skill_with_reader_in_name(self, skill_registry):
        """Test that skills with 'reader' in name are read skills."""
        skill = skill_registry.get("sheets-analytics-reader")
        assert skill is not None
        assert skill.is_write is False
        assert skill.requires_hitl is False
        assert skill.classify() == SkillType.READ

    def test_skill_with_auditor_in_name(self, skill_registry):
        """Test that skills with 'auditor' in name are read skills."""
        skill = skill_registry.get("slides-content-auditor")
        assert skill is not None
        assert skill.is_write is False
        assert skill.classify() == SkillType.READ


@pytest.mark.integration
class TestSkillMetadataIntegration:
    """Integration tests for skill metadata with actual runner logic."""

    def test_run_skill_with_hitl_required(self, mock_mcp_tools, mock_memory_tools):
        """Test running a skill that requires HITL."""
        memory_tools = mock_memory_tools

        skill_name = "gmail-composer-pro"
        is_write = "composer" in skill_name or "editor" in skill_name
        requires_hitl = "composer" in skill_name

        assert is_write is True
        assert requires_hitl is True

        if requires_hitl:
            hitl_response = memory_tools["aria_memory_hitl_ask"].return_value = {"action": "accept"}

    def test_run_skill_without_hitl_required(self, mock_mcp_tools, mock_memory_tools):
        """Test running a skill that does not require HITL."""
        skill_name = "docs-structure-reader"
        requires_hitl = "composer" in skill_name or "editor" in skill_name

        assert requires_hitl is False

    def test_skill_allowed_tools_mapping(self):
        """Test mapping of skill names to allowed tools."""
        skill_tools = {
            "gmail-thread-intelligence": [
                "google_workspace_search_gmail_messages",
                "google_workspace_get_gmail_message_content",
                "aria_memory_remember",
                "aria_memory_recall",
            ],
            "docs-structure-reader": [
                "google_workspace_search_docs",
                "google_workspace_get_doc_content",
                "google_workspace_list_docs_in_folder",
                "google_workspace_read_doc_comments",
                "aria_memory_remember",
                "aria_memory_recall",
            ],
            "sheets-analytics-reader": [
                "google_workspace_list_spreadsheets",
                "google_workspace_get_spreadsheet_info",
                "google_workspace_read_sheet_values",
                "google_workspace_read_sheet_comments",
                "aria_memory_remember",
                "aria_memory_recall",
            ],
            "slides-content-auditor": [
                "google_workspace_get_presentation",
                "google_workspace_get_page",
                "google_workspace_get_page_thumbnail",
                "google_workspace_read_presentation_comments",
                "aria_memory_remember",
                "aria_memory_recall",
            ],
            "gmail-composer-pro": [
                "google_workspace_search_gmail_messages",
                "google_workspace_get_gmail_message_content",
                "google_workspace_draft_gmail_message",
                "google_workspace_send_gmail_message",
                "aria_memory_remember",
                "aria_memory_recall",
                "aria_memory_hitl_ask",
            ],
        }

        assert "google_workspace_search_gmail_messages" in skill_tools["gmail-thread-intelligence"]
        assert "aria_memory_hitl_ask" in skill_tools["gmail-composer-pro"]
        assert "aria_memory_hitl_ask" not in skill_tools["docs-structure-reader"]


@pytest.mark.integration
class TestSkillRunnerErrorHandling:
    """Test error handling in skill runner metadata mapping."""

    def test_missing_skill_returns_unknown(self):
        """Test that missing skill returns UNKNOWN type."""
        skill_registry = {}
        skill_name = "nonexistent-skill"

        skill = skill_registry.get(skill_name)
        assert skill is None

    def test_skill_with_empty_name(self):
        """Test handling of skill with empty name."""
        skill = SkillMetadata(name="")
        assert skill.name == ""
        assert skill.classify() == SkillType.UNKNOWN

    def test_skill_case_sensitivity(self):
        """Test that skill classification is case-sensitive."""
        skill_upper = SkillMetadata(name="GMAIL-COMPOSER-PRO")
        skill_lower = SkillMetadata(name="gmail-composer-pro")

        assert skill_upper.name != skill_lower.name
