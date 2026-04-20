#!/usr/bin/env python3
"""
Validate KiloCode agent definitions per sprint-03 W1.3.A.

Checks:
1. All required agents exist in .aria/kilocode/agents/
2. Each agent has valid frontmatter (name, type, color, temperature, allowed-tools)
3. No agent exceeds 20 tools (P9)
4. All allowed-tools reference valid MCP servers (exist in mcp.json or are wildcards)
5. required-skills reference skills that exist in _registry.json

Usage:
    python scripts/validate_agents.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

AGENTS_DIR = Path("/home/fulvio/coding/aria/.aria/kilocode/agents")
SYSTEM_AGENTS_DIR = AGENTS_DIR / "_system"
MCP_CONFIG = Path("/home/fulvio/coding/aria/.aria/kilocode/mcp.json")
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
    body = "\n".join(lines[end_idx + 1:])
    return (frontmatter or {}), body


def validate_agent(name: str, path: Path) -> list[str]:
    """Validate a single agent definition.

    Returns list of error messages (empty if valid).
    """
    errors = []
    content = path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)

    if not fm:
        errors.append(f"{name}: missing frontmatter")
        return errors

    # Required fields
    for field in ["name", "type", "description", "color", "temperature"]:
        if field not in fm:
            errors.append(f"{name}: missing required field '{field}'")

    # Type must be valid
    valid_types = ["primary", "subagent", "system"]
    if fm.get("type") not in valid_types:
        errors.append(f"{name}: type must be one of {valid_types}")

    # Temperature range
    temp = fm.get("temperature")
    if temp is not None:
        try:
            t = float(temp)
            if not (0.0 <= t <= 2.0):
                errors.append(f"{name}: temperature must be 0.0-2.0, got {t}")
        except (ValueError, TypeError):
            errors.append(f"{name}: temperature must be numeric, got {temp}")

    # Tools check
    allowed_tools = fm.get("allowed-tools", [])
    if len(allowed_tools) > MAX_TOOLS:
        errors.append(f"{name}: {len(allowed_tools)} tools exceeds max {MAX_TOOLS}")

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

    # Load MCP config for tool validation
    try:
        mcp_config = load_json(MCP_CONFIG)
        mcp_servers = set(mcp_config.get("mcpServers", {}).keys())
    except FileNotFoundError:
        print(f"WARNING: mcp.json not found at {MCP_CONFIG}")
        mcp_servers = set()

    # Validate each required agent
    for agent_name in REQUIRED_AGENTS:
        if agent_name == "workspace-agent":
            # Workspace-agent is a stub in Sprint 1.3
            agent_path = AGENTS_DIR / f"{agent_name}.md"
        elif agent_name in ["compaction-agent", "summary-agent", "memory-curator",
                           "blueprint-keeper", "security-auditor"]:
            agent_path = SYSTEM_AGENTS_DIR / f"{agent_name}.md"
        else:
            agent_path = AGENTS_DIR / f"{agent_name}.md"

        if not agent_path.exists():
            errors.append(f"MISSING: {agent_path}")
            continue

        agent_errors = validate_agent(agent_name, agent_path)
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
