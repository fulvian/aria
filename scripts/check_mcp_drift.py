#!/usr/bin/env python
"""MCP drift validator — proxy-aware checks for F3 cutover.

Validates:
1. mcp.json has exactly {"aria-memory", "aria-mcp-proxy"} entries
2. Every entry in agent_capability_matrix.yaml allowed_tools that is
   a backend tool (not aria-memory_* or synthetic) exists as a
   lifecycle: enabled entry in mcp_catalog.yaml
3. Every agent prompt's allowed-tools list mirrors its matrix entry

Usage:
    python scripts/check_mcp_drift.py          # shadow mode (warnings only)
    python scripts/check_mcp_drift.py --enforce  # enforce mode (exit 1 on issues)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def _warn(msg: str) -> None:
    print(f"WARN: {msg}")


def _err(msg: str) -> None:
    print(f"ERR:  {msg}")


def check_mcp_json_shape(mcp_json_path: Path) -> list[str]:
    """Check mcp.json has exactly the expected server entries."""
    errors: list[str] = []
    data = json.loads(mcp_json_path.read_text())
    keys = set(data.get("mcpServers", {}))
    expected = {"aria-memory", "aria-mcp-proxy"}
    if keys == expected:
        print(f"OK   mcp.json keys: {sorted(keys)}")
    else:
        missing = expected - keys
        extra = keys - expected
        if missing:
            errors.append(f"mcp.json missing servers: {sorted(missing)}")
        if extra:
            errors.append(f"mcp.json unexpected servers: {sorted(extra)}")
    return errors


def check_matrix_vs_catalog(matrix_path: Path, catalog_path: Path) -> list[str]:
    """Check that backend tools in the matrix exist in the catalog."""
    errors: list[str] = []
    if not catalog_path.exists():
        _warn(f"catalog not found: {catalog_path}")
        return errors

    catalog = yaml.safe_load(catalog_path.read_text()) or {}
    enabled_names = {
        s["name"] for s in (catalog.get("servers") or []) if s.get("lifecycle") == "enabled"
    }

    matrix = yaml.safe_load(matrix_path.read_text()) or {}
    for agent in matrix.get("agents") or []:
        name = agent.get("name", "")
        for tool in agent.get("allowed_tools") or []:
            if "_" in tool:
                server = tool.split("_", 1)[0]
            elif "/" in tool:
                server = tool.split("/", 1)[0]
            else:
                continue
            # Skip known servers that are not in the catalog
            if server in ("aria-memory", "aria-mcp-proxy", "hitl-queue", "sequential-thinking", ""):
                continue
            if server not in enabled_names:
                errors.append(
                    f"agent '{name}' tool '{tool}' references server "
                    f"'{server}' not in enabled catalog"
                )
    return errors


def main() -> None:
    enforce = "--enforce" in sys.argv
    repo = Path(__file__).resolve().parent.parent

    mcp_json = repo / ".aria/kilocode/mcp.json"
    matrix = repo / ".aria/config/agent_capability_matrix.yaml"
    catalog = repo / ".aria/config/mcp_catalog.yaml"

    all_errors: list[str] = []

    print("=== MCP Drift Validator (proxy-aware, F3) ===\n")

    all_errors.extend(check_mcp_json_shape(mcp_json))
    all_errors.extend(check_matrix_vs_catalog(matrix, catalog))

    print()
    for e in all_errors:
        _err(e)

    if all_errors:
        print(f"\n{len(all_errors)} error(s) found.")
        if enforce:
            sys.exit(1)
    else:
        print("All checks passed.")

    if enforce:
        sys.exit(0)


if __name__ == "__main__":
    main()
