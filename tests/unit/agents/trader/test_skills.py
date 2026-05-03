"""Static checks on trading skills directories and their SKILL.md frontmatter.

Verifies that all 7 trading skills exist, have valid frontmatter, and declare
the correct proxy tools.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

SKILLS_ROOT = Path(".aria/kilocode/skills")

TRADING_SKILLS = [
    "trading-analysis",
    "fundamental-analysis",
    "technical-analysis",
    "macro-intelligence",
    "sentiment-analysis",
    "options-analysis",
    "crypto-analysis",
]

SKILL_FRONTYIELD_TEMPLATE = {
    "trading-analysis": {
        "name": "trading-analysis",
        "version": "1.0.0",
        "allowed-tools": [
            "aria-mcp-proxy_search_tools",
            "aria-mcp-proxy_call_tool",
            "aria-memory_wiki_update_tool",
            "aria-memory_wiki_recall_tool",
            "hitl-queue_ask",
            "sequential-thinking_*",
        ],
    },
    "fundamental-analysis": {
        "name": "fundamental-analysis",
        "version": "1.0.0",
        "allowed-tools": [
            "aria-mcp-proxy_search_tools",
            "aria-mcp-proxy_call_tool",
            "aria-memory_wiki_update_tool",
            "aria-memory_wiki_recall_tool",
            "sequential-thinking_*",
        ],
    },
    "technical-analysis": {
        "name": "technical-analysis",
        "version": "1.0.0",
        "allowed-tools": [
            "aria-mcp-proxy_search_tools",
            "aria-mcp-proxy_call_tool",
            "aria-memory_wiki_update_tool",
            "aria-memory_wiki_recall_tool",
            "sequential-thinking_*",
        ],
    },
    "macro-intelligence": {
        "name": "macro-intelligence",
        "version": "1.0.0",
        "allowed-tools": [
            "aria-mcp-proxy_search_tools",
            "aria-mcp-proxy_call_tool",
            "aria-memory_wiki_update_tool",
            "aria-memory_wiki_recall_tool",
            "sequential-thinking_*",
        ],
    },
    "sentiment-analysis": {
        "name": "sentiment-analysis",
        "version": "1.0.0",
        "allowed-tools": [
            "aria-mcp-proxy_search_tools",
            "aria-mcp-proxy_call_tool",
            "aria-memory_wiki_update_tool",
            "aria-memory_wiki_recall_tool",
            "sequential-thinking_*",
        ],
    },
    "options-analysis": {
        "name": "options-analysis",
        "version": "1.0.0",
        "allowed-tools": [
            "aria-mcp-proxy_search_tools",
            "aria-mcp-proxy_call_tool",
            "aria-memory_wiki_update_tool",
            "aria-memory_wiki_recall_tool",
            "sequential-thinking_*",
        ],
    },
    "crypto-analysis": {
        "name": "crypto-analysis",
        "version": "1.0.0",
        "allowed-tools": [
            "aria-mcp-proxy_search_tools",
            "aria-mcp-proxy_call_tool",
            "aria-memory_wiki_update_tool",
            "aria-memory_wiki_recall_tool",
            "sequential-thinking_*",
        ],
    },
}


@pytest.fixture(params=TRADING_SKILLS)
def skill_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def skill_yaml(skill_name: str) -> dict:
    """Parse YAML frontmatter from skill's SKILL.md."""
    skill_file = SKILLS_ROOT / skill_name / "SKILL.md"
    assert skill_file.exists(), f"SKILL.md not found for {skill_name}"
    content = skill_file.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    assert len(parts) >= 3, f"{skill_file}: YAML frontmatter not found"
    return yaml.safe_load(parts[1])


@pytest.fixture
def skill_text(skill_name: str) -> str:
    """Full text content of skill's SKILL.md (without YAML frontmatter)."""
    skill_file = SKILLS_ROOT / skill_name / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    assert len(parts) >= 3
    return parts[2]


class TestTradingSkillsExist:
    """All 7 trading skills must exist as directories with SKILL.md."""

    def test_skill_directory_exists(self, skill_name: str) -> None:
        """Skill directory must exist."""
        skill_dir = SKILLS_ROOT / skill_name
        assert skill_dir.is_dir()

    def test_skill_file_exists(self, skill_name: str) -> None:
        """SKILL.md file must exist inside skill directory."""
        skill_file = SKILLS_ROOT / skill_name / "SKILL.md"
        assert skill_file.is_file()


class TestTradingSkillsFrontmatter:
    """SKILL.md frontmatter must be well-formed for each trading skill."""

    def test_has_name(self, skill_yaml: dict, skill_name: str) -> None:
        """Frontmatter must have name matching directory."""
        assert skill_yaml.get("name") == skill_name

    def test_has_version(self, skill_yaml: dict) -> None:
        """Frontmatter must have version."""
        assert skill_yaml.get("version") is not None

    def test_version_is_1_0_0(self, skill_yaml: dict) -> None:
        """Version must be 1.0.0 for all new trading skills."""
        assert skill_yaml.get("version") == "1.0.0"

    def test_has_description(self, skill_yaml: dict) -> None:
        """Frontmatter must have description."""
        assert skill_yaml.get("description") is not None

    def test_has_user_invocable(self, skill_yaml: dict) -> None:
        """user-invocable must be True for all trading skills."""
        assert skill_yaml.get("user-invocable") is True

    def test_has_trigger_keywords(self, skill_yaml: dict) -> None:
        """trigger-keywords must be declared."""
        keywords = skill_yaml.get("trigger-keywords", [])
        assert len(keywords) > 0

    def test_allowed_tools_not_empty(self, skill_yaml: dict) -> None:
        """allowed-tools must not be empty."""
        tools = skill_yaml.get("allowed-tools", [])
        assert len(tools) > 0

    def test_allowed_tools_use_proxy(self, skill_yaml: dict) -> None:
        """allowed-tools must include aria-mcp-proxy tools."""
        tools = skill_yaml.get("allowed-tools", [])
        has_proxy = "aria-mcp-proxy_search_tools" in tools or "aria-mcp-proxy_call_tool" in tools
        assert has_proxy

    def test_max_tokens_declared(self, skill_yaml: dict) -> None:
        """max-tokens must be declared."""
        assert "max-tokens" in skill_yaml

    def test_estimated_cost_declared(self, skill_yaml: dict) -> None:
        """estimated-cost-eur should be declared."""
        assert "estimated-cost-eur" in skill_yaml


class TestTradingSkillsBody:
    """SKILL.md body must contain operational content and proxy rules."""

    def test_has_objective_section(self, skill_text: str) -> None:
        """SKILL.md body must have an Obiettivo / Objective section."""
        has_obj = any(
            marker in skill_text.lower()
            for marker in ["# obiettivo", "## objective", "# goal", "## obiettivo"]
        )
        assert has_obj

    def test_describes_proxy_usage(self, skill_text: str) -> None:
        """SKILL.md body must describe proxy invocation pattern."""
        assert "_caller_id" in skill_text or "proxy" in skill_text.lower()

    def test_has_disclaimer_reminder(self, skill_text: str) -> None:
        """SKILL.md body must mention the mandatory disclaimer."""
        assert "disclaimer" in skill_text.lower()

    def test_has_output_format(self, skill_text: str) -> None:
        """SKILL.md body should describe expected output format."""
        lines = skill_text.split("\n")
        header_lines = [ln for ln in lines if ln.startswith(("#", "##"))]
        assert len(header_lines) > 0


class TestTradingSkillsProxyExamples:
    """Proxy examples in skills must use canonical patterns.

    Regression test: catches invalid call_tool("search_tools", ...) and
    legacy server/tool naming with single slash.
    """

    def test_no_call_tool_with_search_tools_arg(self, skill_text: str) -> None:
        """Example code must NOT use call_tool('search_tools', ...) pattern.

        Discovery should use aria-mcp-proxy_search_tools directly, not
        aria-mcp-proxy_call_tool("search_tools", ...).
        """
        # This anti-pattern was in the original recovery commit
        assert 'call_tool("search_tools"' not in skill_text
        assert "call_tool('search_tools'" not in skill_text

    def test_no_legacy_slash_tool_names(self, skill_text: str) -> None:
        """Example code must NOT use server/tool slash naming.

        Canonical form is server_tool (single underscore).
        """
        import re

        # Find proxy call examples and check they don't use slash
        # Match patterns like "server-name/tool_name" inside proxy call blocks
        proxy_blocks = re.findall(
            r'aria-mcp-proxy_call_tool\([^)]*"name":\s*"([^"]+)"',
            skill_text,
        )
        for tool_name in proxy_blocks:
            assert "/" not in tool_name, (
                f"Tool name '{tool_name}' uses legacy slash separator. "
                f"Use single underscore: '{tool_name.replace('/', '_')}'"
            )

    def test_examples_use_caller_id(self, skill_text: str) -> None:
        """All proxy examples must include _caller_id."""
        if "aria-mcp-proxy_" in skill_text:
            assert '"_caller_id": "trader-agent"' in skill_text or (
                '"_caller_id":"trader-agent"' in skill_text
            )
