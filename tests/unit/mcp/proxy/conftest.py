"""Shared fixtures for proxy unit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def minimal_catalog(tmp_path: Path) -> Path:
    """A YAML catalog with two servers (filesystem + a stub stdio)."""
    yaml_text = """
servers:
  - name: filesystem
    domain: system
    owner_agent: aria-conductor
    tier: 0
    transport: stdio
    lifecycle: enabled
    auth_mode: keyless
    statefulness: stateful
    expected_tools: [read, write]
    risk_level: medium
    cost_class: free
    source_of_truth: npx -y @modelcontextprotocol/server-filesystem
    rollback_class: server
    baseline_status: lkg
    notes: minimal fixture

  - name: stub
    domain: search
    owner_agent: search-agent
    tier: 1
    transport: stdio
    lifecycle: disabled
    auth_mode: keyless
    statefulness: stateless
    expected_tools: [stub_search]
    risk_level: low
    cost_class: free
    source_of_truth: stub
    rollback_class: server
    baseline_status: shadow
    notes: disabled fixture
"""
    p = tmp_path / "catalog.yaml"
    p.write_text(yaml_text.lstrip())
    return p


@pytest.fixture
def minimal_mcp_json(tmp_path: Path) -> Path:
    """A JSON file matching the catalog filesystem entry."""
    import json

    p = tmp_path / "mcp.json"
    payload: dict[str, Any] = {
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", str(tmp_path)],
            }
        }
    }
    p.write_text(json.dumps(payload))
    return p
