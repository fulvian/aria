#!/usr/bin/env python3
"""
Validate KiloCode skill definitions per sprint-03 W1.3.B.

Checks:
1. All skills in _registry.json exist as directories with SKILL.md
2. Each SKILL.md has valid frontmatter (name, version, description, allowed-tools)
3. All allowed-tools reference valid MCP servers or wildcards
4. max-tokens is defined for each skill

Usage:
    python scripts/validate_skills.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILLS_DIR = Path("/home/fulvio/coding/aria/.aria/kilocode/skills")
REGISTRY_PATH = SKILLS_DIR / "_registry.json"
KILO_CONFIG = Path("/home/fulvio/coding/aria/.aria/kilocode/kilo.json")

# Known valid wildcard patterns (slash-style allowed for these)
VALID_WILDCARD_PREFIXES = {
    "aria-memory",
    "filesystem",
    "git",
    "github",
    "sequential-thinking",
}

MAX_TOOLS = 20


def _normalize_server_name(name: str) -> str:
    """Normalize server name by replacing underscores with hyphens."""
    return name.replace("_", "-")


def _server_exists(server: str, mcp_servers: set[str]) -> bool:
    """Check if a server exists in kilo.json, trying both underscore and hyphen forms."""
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


def validate_skill(name: str, skill_dir: Path) -> list[str]:
    """Validate a single skill.

    Returns list of error messages (empty if valid).
    """
    errors = []
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        errors.append(f"{name}: SKILL.md not found in {skill_dir}")
        return errors

    content = skill_md.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)

    if not fm:
        errors.append(f"{name}: missing frontmatter")
        return errors

    # Required fields
    for field in ["name", "version", "description"]:
        if field not in fm:
            errors.append(f"{name}: missing required field '{field}'")

    # max-tokens required per blueprint §9.1
    if "max-tokens" not in fm:
        errors.append(f"{name}: missing 'max-tokens' field")

    # allowed-tools validation
    allowed_tools = fm.get("allowed-tools", [])
    if isinstance(allowed_tools, list) and len(allowed_tools) > MAX_TOOLS:
        errors.append(f"{name}: {len(allowed_tools)} tools exceeds max {MAX_TOOLS}")

    for tool in allowed_tools:
        # Check for slash-style MCP tool naming (invalid - should use underscore prefix)
        if _is_slash_style_mcp_tool(tool):
            errors.append(
                f"{name}: slash-style tool '{tool}' is invalid. "
                f"Use underscore prefix format (e.g., google_workspace_search_gmail_messages)"
            )
            continue
        # Check if it's a known wildcard
        if _is_valid_wildcard(tool):
            continue

        # At this point, tool should be in underscore-joined format (e.g., google_workspace_search)
        # Extract server prefix and validate it exists in kilo.json
        if "_" not in tool:
            errors.append(f"{name}: invalid tool format '{tool}' (missing server prefix)")
            continue

        server_prefix = _get_server_prefix(tool, mcp_servers)
        if server_prefix is None or not _server_exists(server_prefix, mcp_servers):
            normalized = _normalize_server_name(server_prefix or tool.split("_")[0])
            errors.append(f"{name}: tool server '{normalized}' not declared in kilo.json")

    return errors


def main() -> int:
    """Main validation."""
    global mcp_servers
    errors = []

    # Load Kilo config (modernized - uses kilo.json instead of mcp.json)
    try:
        kilo_config = load_json(KILO_CONFIG)
        # kilo.json has MCP servers under the "mcp" key
        mcp_servers = set(kilo_config.get("mcp", {}).keys())
    except FileNotFoundError:
        print(f"WARNING: kilo.json not found at {KILO_CONFIG}, skipping server validation")
        mcp_servers = set()

    # Load registry
    if not REGISTRY_PATH.exists():
        print(f"FATAL: skills registry not found: {REGISTRY_PATH}")
        return 1

    registry = load_json(REGISTRY_PATH)
    registered_skills = registry.get("skills", [])

    if not registered_skills:
        print("WARNING: no skills in registry")
        return 0

    print(f"Validating {len(registered_skills)} skills...")

    for skill_entry in registered_skills:
        skill_name = skill_entry.get("name")
        skill_path_str = skill_entry.get("path", "")

        if not skill_name or not skill_path_str:
            errors.append(f"Invalid registry entry: {skill_entry}")
            continue

        # skill path is relative to skills dir
        skill_dir = SKILLS_DIR / skill_path_str.split("/")[0]

        skill_errors = validate_skill(skill_name, skill_dir)
        errors.extend(skill_errors)

    # Report
    if errors:
        print("Skill validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print(f"Skill validation PASSED ({len(registered_skills)} skills)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
