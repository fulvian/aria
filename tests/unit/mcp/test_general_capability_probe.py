from __future__ import annotations

import json
from typing import TYPE_CHECKING

from aria.mcp.capability_probe import read_catalog

if TYPE_CHECKING:
    from pathlib import Path


def test_read_catalog_supports_yaml_catalog_via_runtime_mcp_json(tmp_path: Path) -> None:
    catalog_path = tmp_path / "mcp_catalog.yaml"
    catalog_path.write_text(
        """
servers:
  - name: filesystem
    lifecycle: enabled
  - name: tavily-mcp
    lifecycle: enabled
  - name: playwright
    lifecycle: disabled
""".strip(),
        encoding="utf-8",
    )
    runtime_path = tmp_path / "mcp.json"
    runtime_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "filesystem": {"command": "npx", "args": ["-y", "fs"]},
                    "tavily-mcp": {
                        "command": "/tmp/tavily-wrapper.sh",
                        "env": {"TAVILY_API_KEY": "${TAVILY_API_KEY}"},
                        "timeout": 45,
                    },
                    "playwright": {"command": "npx", "disabled": True},
                }
            }
        ),
        encoding="utf-8",
    )

    catalog = read_catalog(catalog_path, runtime_config_path=runtime_path)

    assert set(catalog) == {"filesystem", "tavily-mcp"}
    assert catalog["filesystem"]["command"] == ["npx", "-y", "fs"]
    assert catalog["tavily-mcp"]["env"] == {"TAVILY_API_KEY": "${TAVILY_API_KEY}"}
    assert catalog["tavily-mcp"]["timeout"] == 45


def test_read_catalog_keeps_jsonc_behavior(tmp_path: Path) -> None:
    catalog_path = tmp_path / "kilo.jsonc"
    catalog_path.write_text(
        """
{
  // comment
  "mcp": {
    "filesystem": {
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem"]
    },
    "playwright": {
      "command": "npx",
      "args": ["-y", "@executeautomation/playwright-mcp-server"],
      "enabled": false
    }
  }
}
""".strip(),
        encoding="utf-8",
    )

    catalog = read_catalog(catalog_path)

    assert set(catalog) == {"filesystem"}
    assert catalog["filesystem"]["command"] == [
        "npx",
        "-y",
        "@modelcontextprotocol/server-filesystem",
    ]
