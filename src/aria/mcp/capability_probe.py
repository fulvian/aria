"""Generalized MCP capability probe.

Probes MCP servers via stdio JSON-RPC, validates tool sets,
and manages schema snapshots for drift detection across all MCP servers.

Usage:
    from aria.mcp.capability_probe import probe_all_servers, probe_server_from_config

    # Probe all enabled servers from the catalog
    results = await probe_all_servers("/path/to/mcp.json")

    # Probe a single server from its config entry
    result = await probe_server_from_config("my-server", config_entry)

CLI:
    python -m aria.mcp.capability_probe --catalog /path/to/mcp.json
    python -m aria.mcp.capability_probe --catalog .aria/config/mcp_catalog.yaml
"""

# ruff: noqa: T201, ASYNC240

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from aria.agents.search.capability_probe import (
    EXPECTED_TOOL_SNAPSHOTS,
    ProbeResult,
    get_expected_tools,
    probe_mcp_server,
)
from aria.agents.search.capability_probe import (
    SNAPSHOTS_DIR as SEARCH_SNAPSHOTS_DIR,
)
from aria.utils.logging import get_logger, log_event

logger = get_logger("aria.mcp.capability_probe")

# ─── Re-exports from search-specific probe ────────────────────────────────────

SNAPSHOTS_DIR = SEARCH_SNAPSHOTS_DIR

# ─── Schema snapshots directory ──────────────────────────────────────────────
# Snapshots are saved to .aria/runtime/mcp-schema-snapshots/{server}-{date}.json

_ARIA_RUNTIME_DEFAULT = Path("/home/fulvio/coding/aria/.aria/runtime")
SCHEMA_SNAPSHOTS_DIR = (
    Path(os.environ.get("ARIA_RUNTIME", str(_ARIA_RUNTIME_DEFAULT))) / "mcp-schema-snapshots"
)


# ─── Catalog parsing ──────────────────────────────────────────────────────────


def _strip_jsonc_comments(text: str) -> str:
    """Strip // and /* */ comments from JSONC text, preserving string contents."""
    result: list[str] = []
    in_string = False
    escape = False
    i = 0
    while i < len(text):
        ch = text[i]
        if escape:
            result.append(ch)
            escape = False
            i += 1
            continue
        if ch == "\\" and in_string:
            escape = True
            result.append(ch)
            i += 1
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            result.append(ch)
            i += 1
            continue
        if not in_string and ch == "/" and i + 1 < len(text):
            if text[i + 1] == "/":
                i += 2
                while i < len(text) and text[i] != "\n":
                    i += 1
                continue
            if text[i + 1] == "*":
                i += 2
                while i < len(text):
                    if text[i] == "*" and i + 1 < len(text) and text[i + 1] == "/":
                        i += 2
                        break
                    i += 1
                continue
        result.append(ch)
        i += 1
    return "".join(result)


def _load_json_or_jsonc(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = json.loads(_strip_jsonc_comments(raw))
    return data if isinstance(data, dict) else {}


def _read_runtime_mcp_config(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    runtime_path = Path(path) if path is not None else _resolve_default_runtime_config()
    if runtime_path is None or not runtime_path.exists():
        return {}

    data = _load_json_or_jsonc(runtime_path)
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return {}
    return {name: cfg for name, cfg in servers.items() if isinstance(cfg, dict)}


def _resolve_enabled_catalog_names(data: dict[str, Any]) -> list[str]:
    raw_servers = data.get("servers")
    if not isinstance(raw_servers, list):
        return []

    enabled: list[str] = []
    for entry in raw_servers:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue

        lifecycle = str(entry.get("lifecycle", "enabled")).strip().lower()
        if lifecycle in {"disabled", "quarantined", "shadow"}:
            continue
        if entry.get("enabled") is False:
            continue

        enabled.append(name)

    return enabled


def _read_yaml_catalog(
    path: Path,
    runtime_config_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    raw_yaml = yaml.safe_load(path.read_text(encoding="utf-8"))
    data = raw_yaml if isinstance(raw_yaml, dict) else {}
    enabled_names = _resolve_enabled_catalog_names(data)
    runtime_servers = _read_runtime_mcp_config(runtime_config_path)

    resolved: dict[str, dict[str, Any]] = {}
    for name in enabled_names:
        runtime_cfg = runtime_servers.get(name)
        if runtime_cfg is None:
            log_event(
                logger,
                20,
                "catalog_server_missing_from_runtime",
                server=name,
                path=str(path),
            )
            continue
        if runtime_cfg.get("disabled", False) or runtime_cfg.get("enabled") is False:
            log_event(logger, 20, "catalog_server_disabled_in_runtime", server=name)
            continue

        cmd = _normalise_command(name, runtime_cfg)
        if not cmd:
            continue

        resolved[name] = {
            "command": cmd,
            "env": _normalise_environment(runtime_cfg),
            "timeout": runtime_cfg.get("timeout", 20),
        }

    return resolved


def read_catalog(
    filepath: str | Path,
    runtime_config_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Read MCP server catalog from YAML, JSON, or JSONC.

    Supports both legacy ``mcpServers`` (``mcp.json``) and modern ``mcp``
    (``kilo.jsonc``) key formats. When given the YAML catalog
    (``.aria/config/mcp_catalog.yaml``), it resolves enabled server names
    against the runtime ``mcp.json`` configuration.

    Returns only *enabled* server entries with a normalised structure::

        {"command": ["npx", "-y", "pkg"], "env": {...}, "timeout": 20}
    """
    path = Path(filepath)
    if not path.exists():
        log_event(logger, 30, "catalog_not_found", path=str(path))
        return {}

    if path.suffix.lower() in {".yaml", ".yml"}:
        return _read_yaml_catalog(path, runtime_config_path=runtime_config_path)

    data = _load_json_or_jsonc(path)

    servers: dict[str, Any] | None = None

    if "mcp" in data:
        servers = data["mcp"]
    elif "mcpServers" in data:
        servers = data["mcpServers"]

    if not isinstance(servers, dict):
        log_event(logger, 30, "catalog_invalid", path=str(path))
        return {}

    result: dict[str, dict[str, Any]] = {}
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        if cfg.get("disabled", False) or cfg.get("enabled") is False:
            continue

        cmd = _normalise_command(name, cfg)
        if not cmd:
            continue

        env = _normalise_environment(cfg)
        timeout = cfg.get("timeout", 20)

        result[name] = {
            "command": cmd,
            "env": env,
            "timeout": timeout,
        }

    return result


def _normalise_command(name: str, cfg: dict[str, Any]) -> list[str] | None:
    """Extract the command list from a server config entry.

    Handles both modern (command is a list) and legacy (command + args) formats.
    """
    raw_cmd = cfg.get("command")
    if isinstance(raw_cmd, list) and raw_cmd:
        return [str(c) for c in raw_cmd]

    if isinstance(raw_cmd, str) and raw_cmd:
        args = cfg.get("args")
        if isinstance(args, list):
            return [raw_cmd] + [str(a) for a in args]
        return [raw_cmd]

    log_event(logger, 20, "server_no_command", server=name)
    return None


def _normalise_environment(cfg: dict[str, Any]) -> dict[str, str]:
    """Extract environment variables from a server config entry."""
    env = cfg.get("env") or cfg.get("environment") or {}
    if not isinstance(env, dict):
        return {}
    return {str(k): str(v) for k, v in env.items()}


# ─── Probe from config ────────────────────────────────────────────────────────


async def probe_server_from_config(
    server_name: str,
    server_config: dict[str, Any],
    timeout_secs: float = 20.0,
) -> ProbeResult:
    """Probe a single MCP server from its catalog config entry.

    Args:
        server_name: Logical server name (key in the catalog).
        server_config: Catalog entry dict. Must contain ``command``
            (list of strings). May also contain ``env`` and ``timeout``.
        timeout_secs: Maximum probe duration in seconds (overridden by
            per-server ``timeout`` in config).

    Returns:
        ProbeResult with the probe outcome.
    """
    cmd = server_config.get("command")
    if not cmd:
        return ProbeResult(
            server_name=server_name,
            error="No command in server config",
        )

    cmd_timeout = float(server_config.get("timeout", timeout_secs))
    expected = get_expected_tools(server_name)

    return await probe_mcp_server(
        server_name,
        cmd,
        expected_tools=expected,
        timeout_secs=cmd_timeout,
    )


# ─── Probe all servers ────────────────────────────────────────────────────────


async def probe_all_servers(
    mcp_catalog_path: str | Path,
    timeout_secs: float = 20.0,
    runtime_config_path: str | Path | None = None,
) -> dict[str, ProbeResult]:
    """Probe every enabled MCP server in a catalog file.

    Args:
        mcp_catalog_path: Path to the MCP server catalog
            (``mcp.json`` or ``kilo.jsonc``).
        timeout_secs: Default per-server timeout (overridden by per-server
            values in the catalog).

    Returns:
        Dict mapping server name to ProbeResult.
    """
    catalog = read_catalog(mcp_catalog_path, runtime_config_path=runtime_config_path)
    if not catalog:
        log_event(logger, 30, "probe_all_no_servers", path=str(mcp_catalog_path))
        return {}

    log_event(
        logger,
        20,
        "probe_all_start",
        path=str(mcp_catalog_path),
        server_count=len(catalog),
    )

    tasks: dict[str, asyncio.Task[ProbeResult]] = {}
    for name, cfg in catalog.items():
        cmd_timeout = float(cfg.get("timeout", timeout_secs))
        tasks[name] = asyncio.create_task(
            probe_server_from_config(name, cfg, timeout_secs=cmd_timeout),
        )

    results: dict[str, ProbeResult] = {}
    for name, task in tasks.items():
        try:
            results[name] = await task
        except Exception as exc:
            results[name] = ProbeResult(
                server_name=name,
                error=f"Task failed: {exc}",
            )

    ok_count = sum(1 for r in results.values() if r.success and not r.quarantine)
    quarantine_count = sum(1 for r in results.values() if r.quarantine)
    fail_count = sum(1 for r in results.values() if not r.success)

    log_event(
        logger,
        20,
        "probe_all_done",
        total=len(results),
        ok=ok_count,
        quarantine=quarantine_count,
        failed=fail_count,
    )

    return results


# ─── Schema snapshot management ───────────────────────────────────────────────


def save_snapshot(result: ProbeResult) -> Path:
    """Save a schema snapshot for the probed server.

    Snapshots are stored under ``SCHEMA_SNAPSHOTS_DIR`` with filename
    ``{server_name}-{YYYYMMDD}.json``, enabling tool-set drift tracking
    over time.
    """
    SCHEMA_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now(UTC).strftime("%Y%m%d")
    snapshot = {
        "server_name": result.server_name,
        "timestamp": datetime.now(UTC).isoformat(),
        "success": result.success,
        "tool_count": result.tool_count,
        "tools": sorted(result.tools),
        "protocol_version": result.protocol_version,
        "server_version": result.server_version,
        "quarantine": result.quarantine,
        "quarantine_reason": result.quarantine_reason,
        "elapsed_ms": result.elapsed_ms,
    }

    path = SCHEMA_SNAPSHOTS_DIR / f"{result.server_name}-{today}.json"
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    log_event(
        logger,
        20,
        "schema_snapshot_saved",
        server=result.server_name,
        path=str(path),
        success=result.success,
        tool_count=result.tool_count,
    )
    return path


def load_latest_schema_snapshot(server_name: str) -> dict[str, Any] | None:
    """Load the most recent schema snapshot for a server."""
    if not SCHEMA_SNAPSHOTS_DIR.exists():
        return None

    pattern = f"{server_name}-*.json"
    matches = sorted(SCHEMA_SNAPSHOTS_DIR.glob(pattern), reverse=True)
    if not matches:
        return None

    try:
        return json.loads(matches[0].read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError) as exc:
        log_event(
            logger,
            30,
            "schema_snapshot_load_error",
            server=server_name,
            path=str(matches[0]),
            error=str(exc),
        )
        return None


# ─── CLI entry point ──────────────────────────────────────────────────────────


def _resolve_default_catalog() -> Path | None:
    """Resolve the default MCP catalog path.

    Tries, in order:
    1. ``KILOCODE_CONFIG_DIR/mcp.json`` (legacy)
    2. ``XDG_CONFIG_HOME/kilo/kilo.jsonc`` (modern)
    3. ``ARIA_KILO_HOME/.config/kilo/kilo.jsonc`` (isolated runtime)
    """
    candidates: list[Path] = []

    kilocode_cfg = os.environ.get("KILOCODE_CONFIG_DIR")
    if kilocode_cfg:
        candidates.append(Path(kilocode_cfg) / "mcp.json")

    xdg_cfg = os.environ.get("XDG_CONFIG_HOME")
    if xdg_cfg:
        candidates.append(Path(xdg_cfg) / "kilo" / "kilo.jsonc")

    kilo_home = os.environ.get("ARIA_KILO_HOME")
    if kilo_home:
        candidates.append(Path(kilo_home) / ".config" / "kilo" / "kilo.jsonc")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _resolve_default_runtime_config() -> Path | None:
    """Resolve the default runtime ``mcp.json`` path."""

    kilocode_cfg = os.environ.get("KILOCODE_CONFIG_DIR")
    if kilocode_cfg:
        candidate = Path(kilocode_cfg) / "mcp.json"
        if candidate.exists():
            return candidate

    candidate = (
        Path(os.environ.get("ARIA_HOME", "/home/fulvio/coding/aria"))
        / ".aria"
        / "kilocode"
        / "mcp.json"
    )
    if candidate.exists():
        return candidate

    return None


def _print_result(name: str, result: ProbeResult) -> None:
    status = (
        "OK"
        if result.success and not result.quarantine
        else "QUARANTINE"
        if result.quarantine
        else "FAIL"
    )
    print(f"  [{status:>10}] {name}: {result.tool_count} tools ({result.elapsed_ms:.0f}ms)")
    if result.error:
        print(f"           error: {result.error}")
    if result.quarantine_reason:
        print(f"           reason: {result.quarantine_reason}")


async def _main(argv: list[str]) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Probe MCP servers and validate capabilities",
    )
    parser.add_argument(
        "--catalog",
        "-c",
        help="Path to MCP catalog file (.yaml, mcp.json, or kilo.jsonc)",
    )
    parser.add_argument(
        "--runtime-config",
        help="Optional runtime mcp.json used to resolve YAML catalog entries",
    )
    parser.add_argument(
        "--server",
        "-s",
        help="Probe only a single server by name",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=20.0,
        help="Per-server timeout in seconds",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        default=True,
        help="Save schema snapshots (default: true)",
    )
    parser.add_argument(
        "--no-save",
        action="store_false",
        dest="save",
        help="Skip saving schema snapshots",
    )

    args = parser.parse_args(argv)

    catalog_path: Path | None = Path(args.catalog) if args.catalog else _resolve_default_catalog()

    if not catalog_path or not catalog_path.exists():
        print("ERROR: MCP catalog not found. Use --catalog to specify path.", file=sys.stderr)
        sys.exit(1)

    print(f"MCP catalog: {catalog_path}")
    print()

    if args.server:
        catalog = read_catalog(str(catalog_path), runtime_config_path=args.runtime_config)
        if args.server not in catalog:
            print(f"ERROR: Server '{args.server}' not found in catalog.", file=sys.stderr)
            sys.exit(1)

        result = await probe_server_from_config(
            args.server,
            catalog[args.server],
            timeout_secs=args.timeout,
        )
        if args.save and result.success:
            save_snapshot(result)
        _print_result(args.server, result)
    else:
        results = await probe_all_servers(
            str(catalog_path),
            timeout_secs=args.timeout,
            runtime_config_path=args.runtime_config,
        )

        if not results:
            print("No enabled MCP servers found in catalog.")
            sys.exit(0)

        print(f"Probed {len(results)} servers:")
        print()
        for name, result in sorted(results.items()):
            _print_result(name, result)
            if result.success and args.save:
                save_snapshot(result)

        print()
        ok = sum(1 for r in results.values() if r.success and not r.quarantine)
        q = sum(1 for r in results.values() if r.quarantine)
        f = sum(1 for r in results.values() if not r.success)
        print(f"Summary: {ok} ok, {q} quarantined, {f} failed")


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))

# ─── Exports ──────────────────────────────────────────────────────────────────

__all__ = [
    "EXPECTED_TOOL_SNAPSHOTS",
    "ProbeResult",
    "SCHEMA_SNAPSHOTS_DIR",
    "SNAPSHOTS_DIR",
    "get_expected_tools",
    "load_latest_schema_snapshot",
    "probe_all_servers",
    "probe_mcp_server",
    "probe_server_from_config",
    "read_catalog",
    "save_snapshot",
]
