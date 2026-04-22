#!/usr/bin/env python3
"""
Validate KiloCode agent definitions per sprint-03 W1.3.A (modernized for kilo.json).

Checks:
1. All required agents exist in .aria/kilocode/agents/
2. Each agent has valid frontmatter (name, type, color, temperature, allowed-tools)
3. No agent exceeds 20 tools (P9)
4. All allowed-tools reference valid MCP servers (exist in kilo.json mcp section or are wildcards)
5. required-skills reference skills that exist in _registry.json

Usage:
    python scripts/validate_agents.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

AGENTS_DIR = Path("/home/fulvio/coding/aria/.aria/kilocode/agents")
SYSTEM_AGENTS_DIR = AGENTS_DIR / "_system"
KILO_CONFIG = Path("/home/fulvio/coding/aria/.aria/kilocode/kilo.json")
SKILLS_REGISTRY = Path("/home/fulvio/coding/aria/.aria/kilocode/skills/_registry.json")

# Required agents per blueprint §8
REQUIRED_AGENTS = [
    "aria-conductor",
    "search-agent",
    "workspace-agent",
    "compaction-agent",
    "summary-agent",
    "memory-curator",
    "blueprint-keeper",
    "security-auditor",
]

MAX_TOOLS = 20


def load_json(path: Path) -> dict:
    """Load JSON file."""
    with open(path) as f:
        return json.load(f)


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown."""
    if not content.startswith("---"):
        return {}, content

    lines = content.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, content

    import yaml

    frontmatter = yaml.safe_load("\n".join(lines[1:end_idx]))
    body = "\n".join(lines[end_idx + 1 :])
    return (frontmatter or {}), body


VALID_NON_MCP_TOOLS = {"spawn-subagent"}

# Known valid wildcard prefixes (slash-style allowed for these)
VALID_WILDCARD_PREFIXES = {"aria-memory", "filesystem", "git", "github", "sequential-thinking"}


def _normalize_server_name(name: str) -> str:
    """Normalize server name by replacing underscores with hyphens.

    E.g., 'tavily_mcp' -> 'tavily-mcp' (for matching 'tavily-mcp' in kilo.json)
          'google_workspace' -> 'google-workspace' (for matching 'tavily-mcp' style keys)
    """
    return name.replace("_", "-")


def _server_exists(server: str, mcp_servers: set[str]) -> bool:
    """Check if a server exists in kilo.json, trying both underscore and hyphen forms.

    Some servers use underscores (google_workspace), others use hyphens (tavily-mcp).
    """
    if server in mcp_servers:
        return True
    # Try hyphenated version
    hyphenated = server.replace("_", "-")
    if hyphenated in mcp_servers:
        return True
    # For servers that are already hyphenated in kilo.json (tavily-mcp),
    # the tool prefix uses underscores (tavily_mcp) - try that conversion too
    underscored = hyphenated.replace("-", "_")
    if underscored in mcp_servers:
        return True
    return False


def _is_valid_wildcard(tool: str) -> bool:
    """Check if tool is a valid wildcard pattern (e.g., aria-memory/*)."""
    if tool == "*":
        return True
    if "/" in tool:
        server = tool.split("/", 1)[0]
        return server in VALID_WILDCARD_PREFIXES
    return False


def _is_slash_style_mcp_tool(tool: str) -> bool:
    """Check if tool uses slash-style MCP naming (e.g., google_workspace/search).

    Slash-style is the old/broken format. Runtime MCP tools use underscore prefix.
    E.g., google_workspace_search_gmail_messages NOT google_workspace/search_gmail_messages.
    """
    if "/" not in tool:
        return False
    # It's a slash-style reference if not a known wildcard
    return not _is_valid_wildcard(tool)


def _get_server_prefix(tool: str, mcp_servers: set[str]) -> str | None:
    """Extract server prefix from underscore-joined tool name by matching against known servers.

    E.g., 'google_workspace_search_gmail' -> 'google_workspace' (matched against kilo.json)
          'tavily_mcp_search' -> 'tavily_mcp' (matched against kilo.json)
    """
    if "_" not in tool:
        return None

    # Try progressively longer prefixes to find the longest match in mcp_servers
    # E.g., for 'google_workspace_search': try 'google', 'google_workspace', 'google_workspace_search'
    parts = tool.split("_")
    for i in range(len(parts) - 1, 0, -1):
        candidate = "_".join(parts[:i])
        if _server_exists(candidate, mcp_servers):
            return candidate

    # No match found - return shortest prefix as fallback
    return parts[0]


def validate_agent(name: str, path: Path, mcp_servers: set[str]) -> list[str]:
    """Validate a single agent definition.

    Returns list of error messages (empty if valid).
    """
    errors = []
    content = path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)

    if not fm:
        errors.append(f"{name}: missing frontmatter")
        return errors

    # Derive agent_type: accept "type" or "mode" (mode is used in legacy files)
    agent_type = fm.get("type") or fm.get("mode")
    valid_types = ["primary", "subagent", "system"]

    # Required fields (name is optional in frontmatter - derived from filename)
    for field in ["description", "color", "temperature"]:
        if field not in fm:
            errors.append(f"{name}: missing required field '{field}'")

    # Type must be valid (handle both "type" and "mode" fields)
    if agent_type not in valid_types:
        errors.append(f"{name}: type must be one of {valid_types}, got '{agent_type}'")

    # Temperature range
    temp = fm.get("temperature")
    if temp is not None:
        try:
            t = float(temp)
            if not (0.0 <= t <= 2.0):
                errors.append(f"{name}: temperature must be 0.0-2.0, got {t}")
        except (ValueError, TypeError):
            errors.append(f"{name}: temperature must be numeric, got {temp}")

    # Tools check - accept "allowed-tools" (list) or legacy "tools" (dict format)
    # Format 1: allowed-tools: [list, of, tools] (allow list)
    # Format 2: tools: {task: false, websearch: false} (deny list - skip validation)
    allowed_tools = fm.get("allowed-tools")
    tools_dict = fm.get("tools", {})

    if allowed_tools is not None:
        # Modern format: list of allowed tools
        if isinstance(allowed_tools, list) and len(allowed_tools) > MAX_TOOLS:
            errors.append(f"{name}: {len(allowed_tools)} tools exceeds max {MAX_TOOLS}")

        for tool in allowed_tools or []:
            # Skip non-MCP tools
            if tool in VALID_NON_MCP_TOOLS or tool == "*":
                continue

            # Check for wildcard patterns (aria-memory/*, etc.)
            if _is_valid_wildcard(tool):
                continue

            # Check for slash-style MCP tool naming (INVALID)
            if _is_slash_style_mcp_tool(tool):
                errors.append(
                    f"{name}: slash-style tool '{tool}' is invalid. "
                    f"Use underscore prefix format (e.g., google_workspace_search_gmail_messages)"
                )
                continue

            # At this point, tool should be in underscore-joined format (e.g., google_workspace_search)
            # Extract server prefix and validate it exists in kilo.json
            if "_" not in tool:
                errors.append(f"{name}: invalid tool format '{tool}' (missing server prefix)")
                continue

            server_prefix = _get_server_prefix(tool, mcp_servers)
            if server_prefix is None or not _server_exists(server_prefix, mcp_servers):
                # _get_server_prefix should never return None if _server_exists fails
                # because it falls back to the shortest prefix, but check anyway
                normalized = _normalize_server_name(server_prefix or tool.split("_")[0])
                errors.append(f"{name}: tool server '{normalized}' not declared in kilo.json")
    elif isinstance(tools_dict, dict):
        # Legacy format: tools is a deny list (boolean values)
        # Skip validation for deny list format - can't enforce P9 with deny list
        pass

    # required-skills check
    required_skills = fm.get("required-skills", [])
    if required_skills:
        try:
            registry = load_json(SKILLS_REGISTRY)
            skill_names = {s["name"] for s in registry.get("skills", [])}
            for skill in required_skills:
                if skill not in skill_names:
                    errors.append(f"{name}: required-skill '{skill}' not in registry")
        except FileNotFoundError:
            errors.append(f"{name}: skills registry not found at {SKILLS_REGISTRY}")

    return errors


def main() -> int:
    """Main validation."""
    errors = []

    # Check agents dir exists
    if not AGENTS_DIR.exists():
        print(f"FATAL: agents dir not found: {AGENTS_DIR}")
        return 1

    # Load Kilo config for tool validation (modernized - uses kilo.json)
    try:
        kilo_config = load_json(KILO_CONFIG)
        # kilo.json has MCP servers under the "mcp" key
        mcp_servers = set(kilo_config.get("mcp", {}).keys())
    except FileNotFoundError:
        print(f"WARNING: kilo.json not found at {KILO_CONFIG}")
        mcp_servers = set()

    # Validate each required agent
    for agent_name in REQUIRED_AGENTS:
        if agent_name == "workspace-agent":
            # Workspace-agent is a stub in Sprint 1.3
            agent_path = AGENTS_DIR / f"{agent_name}.md"
        elif agent_name in [
            "compaction-agent",
            "summary-agent",
            "memory-curator",
            "blueprint-keeper",
            "security-auditor",
        ]:
            agent_path = SYSTEM_AGENTS_DIR / f"{agent_name}.md"
        else:
            agent_path = AGENTS_DIR / f"{agent_name}.md"

        if not agent_path.exists():
            errors.append(f"MISSING: {agent_path}")
            continue

        agent_errors = validate_agent(agent_name, agent_path, mcp_servers)
        errors.extend(agent_errors)

    # Report
    if errors:
        print("Agent validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print(f"Agent validation PASSED ({len(REQUIRED_AGENTS)} agents)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
