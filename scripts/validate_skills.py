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

# Known valid wildcard patterns
VALID_WILDCARDS = {
    "*",
    "aria-memory/*",
    "filesystem/*",
    "git/*",
    "github/*",
    "sequential-thinking/*",
}


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
    for tool in allowed_tools:
        # Check if it's a known wildcard or valid MCP server reference
        if tool not in VALID_WILDCARDS:
            # It's a specific tool reference - should match server/tool format
            if "/" in tool:
                parts = tool.split("/", 1)
                server, _ = parts[0], parts[1] if len(parts) > 1 else ""
                if server not in mcp_servers and server + "-mcp" not in mcp_servers:
                    errors.append(f"{name}: tool server '{server}' not declared in mcp.json")
            else:
                errors.append(f"{name}: invalid tool format '{tool}'")

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
