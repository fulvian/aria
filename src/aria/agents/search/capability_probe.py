"""Capability Probe Framework for MCP Servers.

Esegue `initialize` + `tools/list` su server MCP via stdio, confronta i tool
contro uno snapshot atteso, e restituisce un risultato strutturato per quarantena.

Uso:
    from aria.agents.search.capability_probe import probe_mcp_server, load_snapshot

    result = await probe_mcp_server("pubmed-mcp", ["npx", ...], snapshot)
    if result.quarantine:
        log.warning("Server %s in quarantena: tool mismatch", result.server_name)
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aria.utils.logging import get_logger, log_event

logger = get_logger("aria.agents.search.capability_probe")

# ─── Expected Snapshots (canonical) ──────────────────────────────────────────
# Questi snapshot rappresentano i tool attesi per ogni MCP server.
# Se un server espone tool diversi, viene messo in quarantena.
# Ultimo aggiornamento: 2026-04-29 (verificato via Context7 e benchmark)

EXPECTED_TOOL_SNAPSHOTS: dict[str, set[str]] = {
    # pubmed-mcp REMOVED 2026-04-30: scientific-papers-mcp covers PubMed via source="europepmc"
    "scientific-papers-mcp": {
        "search_papers",
        "fetch_content",
        "fetch_latest",
        "list_categories",
        "fetch_top_cited",
    },
}

# Directory per snapshot persistenti
_ARIA_HOME_DEFAULT = str(Path.home() / "coding" / "aria")
SNAPSHOTS_DIR = (
    Path(os.environ.get("ARIA_HOME", _ARIA_HOME_DEFAULT)) / ".aria" / "runtime" / "mcp_snapshots"
)


# ─── Data structures ─────────────────────────────────────────────────────────


@dataclass
class ProbeResult:
    """Risultato del probe su un MCP server."""

    server_name: str
    tool_count: int = 0
    tools: set[str] = field(default_factory=set)
    quarantine: bool = False  # True se mismatch critico
    quarantine_reason: str | None = None
    error: str | None = None
    elapsed_ms: float = 0.0
    protocol_version: str | None = None
    server_version: str | None = None

    @property
    def success(self) -> bool:
        """True se initialize + tools/list completati senza errori."""
        return self.error is None


# ─── JSON-RPC helpers ────────────────────────────────────────────────────────


def _build_initialize() -> bytes:
    """Build JSON-RPC initialize request."""
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "0.1.0",
            "capabilities": {},
            "clientInfo": {"name": "aria-capability-probe", "version": "1.0.0"},
        },
    }
    return (json.dumps(req) + "\n").encode("utf-8")


def _build_list_tools() -> bytes:
    """Build JSON-RPC tools/list request."""
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    return (json.dumps(req) + "\n").encode("utf-8")


def _build_notification_initialized() -> bytes:
    """Build initialized notification."""
    req = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    return (json.dumps(req) + "\n").encode("utf-8")


async def _read_json_line(
    reader: asyncio.StreamReader,
    timeout_secs: float = 15.0,
) -> dict[str, Any]:
    """Read one JSON-RPC response line from an asyncio stream reader."""
    deadline = asyncio.get_event_loop().time() + timeout_secs
    while asyncio.get_event_loop().time() < deadline:
        line = await asyncio.wait_for(reader.readline(), timeout=timeout_secs)
        if not line:
            raise TimeoutError("Connection closed before JSON response")
        line_str = line.decode("utf-8").strip()
        if not line_str:
            continue
        try:
            parsed: dict[str, Any] = json.loads(line_str)
            return parsed
        except json.JSONDecodeError:
            # Linea informativa (log), continua
            continue
    raise TimeoutError(f"No JSON-RPC response within {timeout_secs}s")


# ─── Probe execution ─────────────────────────────────────────────────────────


async def probe_mcp_server(  # noqa: PLR0912, PLR0915
    server_name: str,
    cmd: list[str],
    expected_tools: set[str] | None = None,
    timeout_secs: float = 20.0,
) -> ProbeResult:
    """Esegue capability probe su un MCP server via stdio.

    Args:
        server_name: Nome logico del server (es. "pubmed-mcp").
        cmd: Comando e argomenti per avviare il server (es. ["npx", "-y", "..."]).
        expected_tools: Set di tool attesi. Se None, non fa quarantena.
        timeout: Timeout totale in secondi.

    Returns:
        ProbeResult con esito del probe.
    """
    import time

    result = ProbeResult(server_name=server_name)
    start = time.perf_counter()

    proc: asyncio.subprocess.Process | None = None

    try:
        # ─── Avvio server ───
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={
                **os.environ,
                "ARIA_HOME": os.environ.get("ARIA_HOME", ""),
                "MCP_LOG_LEVEL": "error",
            },
        )
        assert proc.stdin is not None
        assert proc.stdout is not None

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(
            lambda: protocol,
            proc.stdout,
        )

        # ─── Initialize ───
        proc.stdin.write(_build_initialize())
        await proc.stdin.drain()

        init_resp = await _read_json_line(reader, timeout_secs=timeout_secs)
        if "error" in init_resp:
            result.error = f"initialize error: {init_resp['error'].get('message', 'unknown')}"
            return result

        result.protocol_version = init_resp.get("result", {}).get("protocolVersion", None)
        server_info = init_resp.get("result", {}).get("serverInfo", {})
        result.server_version = server_info.get("version", None)

        # Send initialized notification (best-effort)
        try:
            proc.stdin.write(_build_notification_initialized())
            await proc.stdin.drain()
        except Exception:
            pass

        # ─── tools/list ───
        proc.stdin.write(_build_list_tools())
        await proc.stdin.drain()

        list_resp = await _read_json_line(reader, timeout_secs=timeout_secs)

        if "error" in list_resp:
            result.error = f"tools/list error: {list_resp['error'].get('message', 'unknown')}"
            return result

        # Extract tools
        tools_raw = list_resp.get("result", {}).get("tools", [])
        result.tool_count = len(tools_raw)
        result.tools = {t.get("name", "?") for t in tools_raw}
        # success = True (error is None)

        # ─── Quarantine check ───
        if expected_tools is not None:
            missing = expected_tools - result.tools
            extra = result.tools - expected_tools
            if missing:
                result.quarantine = True
                result.quarantine_reason = (
                    f"Tool mancanti ({len(missing)}): {', '.join(sorted(missing))}"
                )
            elif extra and len(extra) > len(expected_tools) * 0.5:
                # Se ci sono molti tool in piu', potrebbe essere un aggiornamento maggiore
                result.quarantine = True
                result.quarantine_reason = (
                    f"Tool extra ({len(extra)}): {', '.join(sorted(extra))} — "
                    f"possibile aggiornamento major, verificare compatibilita'"
                )

    except TimeoutError as e:
        result.error = f"Timeout: {e}"
    except FileNotFoundError as e:
        result.error = f"Command not found: {e}"
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
    finally:
        result.elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        if proc is not None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5)
            except Exception:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except Exception:
                    pass

    return result


# ─── Snapshot management ─────────────────────────────────────────────────────


def save_snapshot(result: ProbeResult) -> Path:
    """Salva uno snapshot del probe su disco.

    Lo snapshot contiene tool list, versioni, e timestamp.
    Usato per tracking di drift tra sessioni.
    """
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "server_name": result.server_name,
        "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
        "success": result.success,
        "tool_count": result.tool_count,
        "tools": sorted(result.tools),
        "protocol_version": result.protocol_version,
        "server_version": result.server_version,
        "quarantine": result.quarantine,
        "quarantine_reason": result.quarantine_reason,
        "elapsed_ms": result.elapsed_ms,
    }

    path = SNAPSHOTS_DIR / f"{result.server_name}.snapshot.json"
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    log_event(
        logger,
        20,
        "snapshot_saved",
        server=result.server_name,
        path=str(path),
        success=result.success,
        tool_count=result.tool_count,
    )
    return path


def load_snapshot(server_name: str) -> dict[str, Any] | None:
    """Carica l'ultimo snapshot per un server."""
    path = SNAPSHOTS_DIR / f"{server_name}.snapshot.json"
    if not path.exists():
        return None
    try:
        loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return loaded
    except (json.JSONDecodeError, OSError) as e:
        log_event(logger, 30, "snapshot_load_error", server=server_name, error=str(e))
        return None


def get_expected_tools(server_name: str) -> set[str] | None:
    """Restituisce il set di tool attesi per un server.

    Prima cerca nella cache snapshot, poi nel dizionario EXPECTED_TOOL_SNAPSHOTS.
    """
    snapshot = load_snapshot(server_name)
    if snapshot and snapshot.get("success"):
        return set(snapshot.get("tools", []))
    return EXPECTED_TOOL_SNAPSHOTS.get(server_name)


async def probe_and_quarantine(
    server_name: str,
    cmd: list[str],
    timeout_secs: float = 20.0,
) -> ProbeResult:
    """Esegue probe + confronto snapshot atteso + quarantena automatica.

    Se il server supera il probe, lo snapshot viene salvato.
    Se il server fallisce, il risultato e' marcato quarantine=True.
    """
    expected = get_expected_tools(server_name)
    result = await probe_mcp_server(
        server_name,
        cmd,
        expected_tools=expected,
        timeout_secs=timeout_secs,
    )

    # Salva snapshot solo se il probe ha avuto successo (per evitare snapshot corrotti)
    if result.success:
        save_snapshot(result)

    if result.quarantine:
        log_event(
            logger,
            40,
            "server_quarantined",
            server=server_name,
            reason=result.quarantine_reason,
            tool_count=result.tool_count,
            elapsed_ms=result.elapsed_ms,
        )
    elif result.success:
        log_event(
            logger,
            20,
            "server_probe_ok",
            server=server_name,
            tool_count=result.tool_count,
            elapsed_ms=result.elapsed_ms,
        )
    else:
        log_event(
            logger,
            40,
            "server_probe_failed",
            server=server_name,
            error=result.error,
            elapsed_ms=result.elapsed_ms,
        )

    return result


# ─── Exports ─────────────────────────────────────────────────────────────────

__all__ = [
    "EXPECTED_TOOL_SNAPSHOTS",
    "ProbeResult",
    "SNAPSHOTS_DIR",
    "get_expected_tools",
    "load_snapshot",
    "probe_and_quarantine",
    "probe_mcp_server",
    "save_snapshot",
]
