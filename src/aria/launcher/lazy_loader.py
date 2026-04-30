# ARIA MCP Lazy Loader
#
# Per stabilization plan §F3.4:
#   Input:  lista intent richiesti (es. da arg CLI `--intent academic` o da intent classifier)
#   Output: mcp.json ridotto contenente solo server core + server con
#           intent_tags ∩ requested_intents non vuoto + server lazy_load: false
#
# Profiles:
#   baseline  → use full mcp.json (no lazy)
#   candidate → generate runtime reduced mcp.json
#   shadow    → log decisions without applying (observability)

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class Profile(StrEnum):
    """Lazy-loading profile selector."""

    BASELINE = "baseline"
    CANDIDATE = "candidate"
    SHADOW = "shadow"


@dataclass
class MCPServerMeta:
    """Metadata for a single MCP server from the catalog."""

    name: str
    lazy_load: bool = True
    intent_tags: list[str] = field(default_factory=list)


@dataclass
class LazyLoaderConfig:
    """Configuration for MCP lazy bootstrap per intent.

    Attributes:
        catalog_path:   Path to the YAML MCP catalog (server metadata).
        mcp_json_template: Path to the full mcp.json template.
        output_path:    Where to write the filtered mcp.json (None = don't write).
        profile:        BASELINE / CANDIDATE / SHADOW.
    """

    catalog_path: Path
    mcp_json_template: Path
    output_path: Path | None = None
    profile: Profile = Profile.CANDIDATE


def load_catalog(catalog_path: str) -> dict[str, MCPServerMeta]:
    """Load MCP server metadata from a YAML catalog file.

    Expected structure::

        servers:
          server-name:
            lazy_load: true
            intent_tags: ["search", "web"]

    Returns a dict keyed by server name.  Returns an empty dict when the
    catalog file does not exist (graceful degradation).
    """
    path = Path(catalog_path)
    if not path.exists():
        logger.warning("MCP catalog not found at %s — no lazy metadata available", path)
        return {}

    with open(path) as f:
        raw: Any = yaml.safe_load(f)
        data: dict[str, Any] = raw if isinstance(raw, dict) else {}

    servers: dict[str, MCPServerMeta] = {}
    for name, meta in data.get("servers", {}).items():
        servers[name] = MCPServerMeta(
            name=name,
            lazy_load=bool(meta.get("lazy_load", True)),
            intent_tags=list(meta.get("intent_tags", [])),
        )
    return servers


def build_mcp_config(
    requested_intents: list[str],
    catalog_path: str,
    mcp_json_template: str,
) -> dict[str, Any]:
    """Build a filtered MCP configuration dict based on requested intents.

    Filtering rules:
    1. If *requested_intents* is empty or contains ``"all"``, return every
       server from the template (no filtering).
    2. Always include servers whose catalog entry has ``lazy_load: false``.
    3. Include servers where *intent_tags* intersects with *requested_intents*.
    4. Servers not present in the catalog are included by default
       (conservative — never silently drop an uncatalogued server).

    Returns:
        A dict with a single ``mcpServers`` key containing the filtered set.
    """
    template_path = Path(mcp_json_template)
    if not template_path.exists():
        raise FileNotFoundError(f"mcp.json template not found: {mcp_json_template}")

    with open(template_path) as f:
        full_config: dict[str, Any] = json.load(f)

    all_servers: dict[str, Any] = full_config.get("mcpServers", {})

    if not requested_intents or "all" in requested_intents:
        return full_config

    catalog = load_catalog(catalog_path)
    requested_set = set(requested_intents)

    filtered_servers: dict[str, Any] = {}
    for name, server_cfg in all_servers.items():
        meta = catalog.get(name)

        # Uncatalogued server → include conservatively
        if meta is None:
            filtered_servers[name] = server_cfg
            continue

        # Core / always-on server
        if not meta.lazy_load:
            filtered_servers[name] = server_cfg
            continue

        # Intent match
        if meta.intent_tags and requested_set & set(meta.intent_tags):
            filtered_servers[name] = server_cfg
            continue

        logger.debug("Excluding server %s (lazy, no intent match)", name)

    return {"mcpServers": filtered_servers}


def generate_mcp_json(
    requested_intents: list[str],
    catalog_path: str,
    template_path: str,
    output_path: str,
) -> dict[str, Any]:
    """Build a filtered MCP config and write it to *output_path*.

    Returns the filtered config dict.
    """
    config = build_mcp_config(requested_intents, catalog_path, template_path)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(config, f, indent=2)

    server_count = len(config.get("mcpServers", {}))
    logger.info(
        "Generated MCP config at %s (%d servers, intents: %s)",
        output_path,
        server_count,
        requested_intents,
    )
    return config


def run_with_profile(
    requested_intents: list[str] | None,
    catalog_path: str,
    template_path: str,
    output_path: str | None = None,
    profile: str = "candidate",
) -> dict[str, Any]:
    """Dispatch MCP config generation according to the selected *profile*.

    *   **baseline** — return the full template config untouched (no filtering).
    *   **candidate** — filter and write to *output_path*.
    *   **shadow**    — filter but only log what *would* change; do not write.
    """
    parsed = Profile(profile)

    if parsed == Profile.BASELINE:
        with open(template_path) as f:
            return json.load(f)  # type: ignore[no-any-return]

    intents = requested_intents or []
    config = build_mcp_config(intents, catalog_path, template_path)

    if parsed == Profile.SHADOW:
        with open(template_path) as f:
            full: dict[str, Any] = json.load(f)
        all_names = set(full.get("mcpServers", {}))
        filtered_names = set(config.get("mcpServers", {}))
        excluded = all_names - filtered_names
        logger.info(
            "[SHADOW] Would exclude %d server(s): %s",
            len(excluded),
            sorted(excluded) if excluded else "(none)",
        )
        return config

    if output_path:
        return generate_mcp_json(intents, catalog_path, template_path, output_path)

    return config


# ── CLI ──────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for :code:`aria-launcher-lazy`.

    Usage::

        # Baseline — dump full mcp.json
        aria-launcher-lazy --profile baseline --template mcp.json

        # Candidate — filter by intents, write to output
        aria-launcher-lazy --profile candidate \\
            --intent academic,research --catalog catalog.yaml \\
            --template mcp.json --output filtered.json

        # Shadow — dry-run, log-only
        aria-launcher-lazy --profile shadow \\
            --intent productivity --catalog catalog.yaml \\
            --template mcp.json
    """
    parser = argparse.ArgumentParser(
        prog="aria-launcher-lazy",
        description="MCP lazy bootstrap — generate a reduced mcp.json per intent.",
    )
    parser.add_argument(
        "--profile",
        choices=[p.value for p in Profile],
        default="candidate",
        help="Lazy-loading profile (default: candidate)",
    )
    parser.add_argument(
        "--intent",
        default="",
        help="Comma-separated list of requested intents (e.g. 'academic,research')",
    )
    parser.add_argument(
        "--catalog",
        required=True,
        help="Path to MCP catalog YAML file",
    )
    parser.add_argument(
        "--template",
        required=True,
        help="Path to full mcp.json template",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output path for filtered mcp.json (required for candidate profile)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
    )

    intents: list[str] = [s.strip() for s in args.intent.split(",") if s.strip()]
    output: str | None = args.output if args.output else None

    result = run_with_profile(
        requested_intents=intents or None,
        catalog_path=args.catalog,
        template_path=args.template,
        output_path=output,
        profile=args.profile,
    )

    if args.profile == "baseline" or (args.profile == "candidate" and not output):
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
