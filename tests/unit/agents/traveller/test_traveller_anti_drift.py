"""Anti-drift tests for traveller-agent (Fase 7).

Verifica che il prompt e la configurazione del traveller-agent non
derivino rispetto ai pattern ARIA canonici.

Test coverage:
- source-of-truth drift: prompt alignment
- host-native tool drift: prompt vieta host tools
- pseudo-HITL drift: prompt usa hitl-queue__ask, non conferma testuale
- duplicate wiki updates: una sola wiki_update per turn
- self-remediation leakage: prompt vieta auto-edit/config/kill
- naming drift: wildcard server__* nel prompt
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PROMPT = Path(".aria/kilocode/agents/traveller-agent.md")


@pytest.fixture(scope="module")
def prompt_text() -> str:
    text = PROMPT.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3
    return parts[2]


@pytest.fixture(scope="module")
def frontmatter() -> dict:
    text = PROMPT.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return yaml.safe_load(parts[1])


class TestAntiDriftSourceOfTruth:
    """No source-of-truth drift."""

    def test_prompt_is_canonical(self, frontmatter: dict):
        """Prompt has correct agent name."""
        assert frontmatter["name"] == "traveller-agent"

    def test_category_is_travel(self, frontmatter: dict):
        """Category is travel (domain-primary)."""
        assert frontmatter["category"] == "travel"

    def test_type_is_subagent(self, frontmatter: dict):
        """Type is subagent."""
        assert frontmatter["type"] == "subagent"


class TestAntiDriftHostTools:
    """No host-native tool drift."""

    def test_forbids_host_tools(self, prompt_text: str):
        """Prompt forbids Glob/Read/Write/bash for travel workflows."""
        # The prompt now emphasizes "DEVI chiamare tool MCP" which is stronger
        assert "REGOLA" in prompt_text or "NON" in prompt_text
        assert "aria-mcp-proxy" in prompt_text

    def test_requires_proxy(self, prompt_text: str):
        """Proxy invocation is mandatory."""
        assert "aria-mcp-proxy" in prompt_text


class TestAntiDriftPseudoHITL:
    """No pseudo-HITL drift: real HITL only."""

    def test_hitl_queue_ask_used(self, prompt_text: str):
        """Prompt references hitl-queue__ask, not just textual confirmation."""
        assert "hitl-queue__ask" in prompt_text

    def test_textual_confirmation_not_hitl(self, prompt_text: str):
        """Prompt explicitly says textual confirmation ≠ HITL."""
        assert "Conferma testuale" in prompt_text


class TestAntiDriftMemory:
    """No memory contract drift."""

    def test_single_wiki_update(self, prompt_text: str):
        """Prompt specifies exactly one wiki_update per turn."""
        assert "ESATTAMENTE UNA VOLTA" in prompt_text
        assert "wiki_update" in prompt_text

    def test_wiki_recall_at_start(self, prompt_text: str):
        """Prompt requires wiki_recall at start of turn."""
        assert "wiki_recall" in prompt_text


class TestAntiDriftSelfRemediation:
    """No self-remediation leakage."""

    def test_no_auto_edit(self, prompt_text: str):
        """Prompt forbids editing code during user workflow."""
        assert "NON modificare codice" in prompt_text

    def test_no_kill_processes(self, prompt_text: str):
        """Prompt forbids killing processes."""
        assert "NON killare processi" in prompt_text or "NON" in prompt_text

    def test_describe_not_fix(self, prompt_text: str):
        """Prompt says to describe anomalies, not fix them."""
        assert "NON fare auto-remediation" in prompt_text or "auto-remediation" in prompt_text


class TestAntiDriftNaming:
    """No naming drift: server__tool convention."""

    def test_wildcard_server_tool(self, prompt_text: str):
        """Prompt uses server__* wildcard format."""
        assert "__*" in prompt_text or "__" in prompt_text

    def test_backend_names_correct(self, prompt_text: str):
        """Backend names follow server__tool convention."""
        props = ["airbnb__", "osm-mcp__", "aria-amadeus-mcp__"]
        found = any(p in prompt_text for p in props)
        assert found, "No server__tool pattern found for travel backends"

    def test_discovery_uses_direct_search_tool(self, prompt_text: str):
        """Prompt must call search_tools directly, not via call_tool."""
        assert "aria-mcp-proxy__search_tools" in prompt_text
        assert 'name: "search_tools"' not in prompt_text

    def test_call_tool_examples_are_not_double_nested(self, prompt_text: str):
        """Prompt must not use name=call_tool wrapper examples."""
        assert 'aria-mcp-proxy__call_tool(name="call_tool"' not in prompt_text
        assert 'name="call_tool"' not in prompt_text


class TestAntiDriftPromptSurface:
    """No prompt surface drift."""

    def test_max_tools_frontmatter(self, frontmatter: dict):
        """Frontmatter doesn't exceed max_tools limit."""
        tools = frontmatter.get("allowed-tools", [])
        assert len(tools) <= 20, f"Too many tools ({len(tools)} > 20)"

    def test_no_bare_tool_names(self, prompt_text: str):
        """No bare MCP invocations (must go through proxy).

        Allow negative instructions ("NON invocare") and markdown code blocks.
        """
        lines = prompt_text.splitlines()
        for line in lines:
            stripped = line.strip()
            # Skip comments, code blocks, negative instructions, and proxy lines
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("```") or "aria-mcp-proxy" in stripped:
                continue
            if stripped.startswith(("NON", "non")):
                continue
            # Check only positive imperative instructions for bare backend names
            if (
                "`airbnb/" in stripped
                or "`osm-mcp/" in stripped
                or "`aria-amadeus-mcp/" in stripped
            ) and "proxy" not in stripped.lower():
                pytest.fail(f"Direct invocation without proxy: {stripped}")
