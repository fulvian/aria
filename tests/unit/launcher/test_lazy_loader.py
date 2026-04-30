from __future__ import annotations

import json
from typing import TYPE_CHECKING

from aria.launcher.lazy_loader import build_mcp_config, load_catalog

if TYPE_CHECKING:
    from pathlib import Path


def test_load_catalog_supports_list_schema(tmp_path: Path) -> None:
    catalog_path = tmp_path / "mcp_catalog.yaml"
    catalog_path.write_text(
        """
servers:
  - name: filesystem
    lazy_load: false
    intent_tags: [system]
  - name: tavily-mcp
    lazy_load: true
    intent_tags: [general, news]
""".strip(),
        encoding="utf-8",
    )

    catalog = load_catalog(str(catalog_path))

    assert catalog["filesystem"].lazy_load is False
    assert catalog["filesystem"].intent_tags == ["system"]
    assert catalog["tavily-mcp"].intent_tags == ["general", "news"]


def test_build_mcp_config_filters_against_list_schema(tmp_path: Path) -> None:
    catalog_path = tmp_path / "mcp_catalog.yaml"
    catalog_path.write_text(
        """
servers:
  - name: filesystem
    lazy_load: false
    intent_tags: [system]
  - name: tavily-mcp
    lazy_load: true
    intent_tags: [general, news]
  - name: scientific-papers-mcp
    lazy_load: true
    intent_tags: [academic]
""".strip(),
        encoding="utf-8",
    )
    template_path = tmp_path / "mcp.json"
    template_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "filesystem": {"command": "npx"},
                    "tavily-mcp": {"command": "wrapper"},
                    "scientific-papers-mcp": {"command": "wrapper"},
                    "uncatalogued": {"command": "keep-me"},
                }
            }
        ),
        encoding="utf-8",
    )

    config = build_mcp_config(["academic"], str(catalog_path), str(template_path))

    assert set(config["mcpServers"]) == {
        "filesystem",
        "scientific-papers-mcp",
        "uncatalogued",
    }
