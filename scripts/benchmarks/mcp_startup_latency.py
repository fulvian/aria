#!/usr/bin/env python3
"""MCP Startup Latency Benchmark — misura cold/warm startup + tools/list per MCP server.

Usage:
    .venv/bin/python scripts/benchmarks/mcp_startup_latency.py [--search-only] [--json]

Misura per ogni server MCP nel dominio search:
  1. Cold start: time-to-initialize (primo avvio, cache fredda)
  2. Warm start: time-to-initialize (secondo avvio, package già in cache)
  3. tools/list: latency per ottenere il tool catalog
  4. Tool count: numero di tool esposti

Output: tabella markdown (default) o JSON (--json).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ARIA_HOME = Path(__file__).resolve().parent.parent.parent

# ─── Target MCP servers per dominio ──────────────────────────────────────────

# CORE: servers fondamentali per l'operatività ARIA
CORE_SERVERS: dict[str, list[str]] = {
    "filesystem": ["npx", "-y", "@modelcontextprotocol/server-filesystem", str(ARIA_HOME)],
    "sequential-thinking": ["npx", "-y", "@modelcontextprotocol/server-sequential-thinking"],
    "aria-memory": [str(ARIA_HOME / ".venv/bin/python"), "-m", "aria.memory.mcp_server"],
}

# SEARCH: i 7 provider MCP del dominio search + fetch
SEARCH_SERVERS: dict[str, list[str]] = {
    "fetch": ["uvx", "mcp-server-fetch"],
    "searxng-script": [str(ARIA_HOME / "scripts/wrappers/searxng-wrapper.sh")],
    "reddit-search": ["uvx", "reddit-no-auth-mcp-server"],
    # pubmed-mcp REMOVED 2026-04-30: scientific-papers-mcp covers PubMed via source="europepmc"
    "scientific-papers-mcp": [str(ARIA_HOME / "scripts/wrappers/scientific-papers-wrapper.sh")],
}

# PRODUCTIVITY
PRODUCTIVITY_SERVERS: dict[str, list[str]] = {
    "markitdown-mcp": ["uvx", "markitdown-mcp"],
}

# Tavily/Brave/Exa saltati per mancanza chiavi API in ambiente benchmark
# google_workspace saltato per OAuth

ALL_SERVERS: dict[str, list[str]] = {}
ALL_SERVERS.update(CORE_SERVERS)
ALL_SERVERS.update(SEARCH_SERVERS)
ALL_SERVERS.update(PRODUCTIVITY_SERVERS)


# ─── Data structures ─────────────────────────────────────────────────────────

@dataclass
class ServerResult:
    name: str
    domain: str
    cold_start_ms: float | None = None
    warm_start_ms: float | None = None
    tools_list_ms: float | None = None
    tool_count: int = 0
    error: str | None = None
    skipped: bool = False


@dataclass
class BenchmarkReport:
    results: list[ServerResult] = field(default_factory=list)
    total_cold_ms: float = 0.0
    total_warm_ms: float = 0.0

    def add(self, r: ServerResult) -> None:
        self.results.append(r)
        if r.cold_start_ms is not None:
            self.total_cold_ms += r.cold_start_ms
        if r.warm_start_ms is not None:
            self.total_warm_ms += r.warm_start_ms


# ─── MCP JSON-RPC helpers ────────────────────────────────────────────────────

def _mcp_initialize() -> bytes:
    """Build a JSON-RPC initialize request."""
    req = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "0.1.0",
            "capabilities": {},
            "clientInfo": {"name": "aria-benchmark", "version": "1.0.0"},
        },
        "id": 1,
    }
    return (json.dumps(req) + "\n").encode("utf-8")


def _mcp_list_tools() -> bytes:
    """Build a JSON-RPC tools/list request."""
    req = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": 2,
    }
    return (json.dumps(req) + "\n").encode("utf-8")


def _mcp_notification_initialized() -> bytes:
    """Build an 'initialized' notification."""
    req = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    return (json.dumps(req) + "\n").encode("utf-8")


def _send_and_receive(
    proc: subprocess.Popen[bytes],
    payload: bytes,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Send JSON-RPC payload to an MCP server subprocess and read one response line.

    Gestisce output misti (log info + JSON-RPC) provando ogni linea come JSON.
    """
    assert proc.stdin is not None
    assert proc.stdout is not None

    proc.stdin.write(payload)
    proc.stdin.flush()

    import select

    deadline = time.monotonic() + timeout
    received_lines: list[bytes] = []
    while time.monotonic() < deadline:
        r, _, _ = select.select([proc.stdout], [], [], 0.1)
        if r:
            line = proc.stdout.readline()
            if not line:
                continue
            received_lines.append(line)
            # Prova a parsare ogni linea individualmente come JSON
            try:
                return json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                # linea informativa (log, progress), continua a leggere
                continue
    all_received = b"".join(received_lines)
    raise TimeoutError(
        f"No JSON-RPC response within {timeout}s, "
        f"received {len(received_lines)} lines, "
        f"last line: {received_lines[-1][:200] if received_lines else b'<empty>'}"
    )


def _try_kill(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is not None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
            proc.wait(timeout=5)


# ─── Benchmark runner ────────────────────────────────────────────────────────

def _is_tool_available(name: str) -> bool:
    """Check if a CLI tool is available in PATH."""
    return shutil.which(name) is not None


def benchmark_server(
    server_name: str,
    cmd: list[str],
    domain: str,
    skip_checks: bool = False,
) -> ServerResult:
    """Benchmark a single MCP server: cold start, warm start, tools/list."""
    result = ServerResult(name=server_name, domain=domain)

    print(f"  ⏳ {server_name} ({domain})...", end="", flush=True)

    # Check if the command's primary tool is available
    primary_tool = cmd[0]
    if not skip_checks and not _is_tool_available(primary_tool) and not primary_tool.endswith(".sh"):
        # For shell wrappers, check if bash is available
        if not _is_tool_available("bash"):
            result.skipped = True
            result.error = f"Primary binary not available: {primary_tool}"
            print(f" ⏭️ SKIP ({result.error})")
            return result

    env = {
        "ARIA_HOME": str(ARIA_HOME),
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "NCBI_ADMIN_EMAIL": "benchmark@test.local",
        "MCP_LOG_LEVEL": "error",
    }
    # Environment vars for wrappers
    env["SOPS_AGE_KEY_FILE"] = os.environ.get("SOPS_AGE_KEY_FILE", str(Path.home() / ".config/sops/age/keys.txt"))

    try:
        # ─── COLD START ───
        start = time.perf_counter()
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={**env, **os.environ},
        )
        cold_init_time = time.perf_counter()

        # Send initialize
        init_resp = _send_and_receive(proc, _mcp_initialize(), timeout=15)
        cold_init_end = time.perf_counter()

        _try_kill(proc)
        cold_start_ms = (cold_init_end - start) * 1000
        result.cold_start_ms = round(cold_start_ms, 1)

        # ─── WARM START ───
        start = time.perf_counter()
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={**env, **os.environ},
        )
        warm_init_time = time.perf_counter()

        # Send initialize + tools/list
        _send_and_receive(proc, _mcp_initialize(), timeout=15)
        # Send initialized notification
        try:
            assert proc.stdin is not None
            proc.stdin.write(_mcp_notification_initialized())
            proc.stdin.flush()
        except Exception:
            pass

        start_list = time.perf_counter()
        tools_resp = _send_and_receive(proc, _mcp_list_tools(), timeout=15)
        tools_list_ms = (time.perf_counter() - start_list) * 1000

        warm_end = time.perf_counter()
        warm_start_ms = (warm_end - start) * 1000

        result.warm_start_ms = round(warm_start_ms, 1)
        result.tools_list_ms = round(tools_list_ms, 1)

        # Extract tool count
        if "result" in tools_resp and "tools" in tools_resp["result"]:
            result.tool_count = len(tools_resp["result"]["tools"])
        elif "error" in tools_resp:
            result.error = f"tools/list error: {tools_resp['error'].get('message', 'unknown')}"
            print(f" ⚠️  {result.error}")
        else:
            result.error = f"unexpected response: {str(tools_resp)[:200]}"

        _try_kill(proc)
        print(f" cold={cold_start_ms:.0f}ms warm={warm_start_ms:.0f}ms tools={result.tool_count}")

    except FileNotFoundError as e:
        result.skipped = True
        result.error = f"Command not found: {e}"
        print(f" ⏭️ SKIP ({result.error})")
    except TimeoutError as e:
        result.error = f"Timeout: {e}"
        print(f" ❌ TIMEOUT ({result.error[:80]})")
        _try_kill(locals().get("proc"))
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        print(f" ❌ ERROR ({result.error[:80]})")
        _try_kill(locals().get("proc"))

    return result


# ─── Report ──────────────────────────────────────────────────────────────────

def _print_markdown(report: BenchmarkReport) -> None:
    """Print benchmark report as markdown table."""
    print()
    print("## MCP Startup Latency Benchmark")
    print()
    print(f"**Run**: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}")
    print(f"**Platform**: {sys.platform}")
    print(f"**Python**: {sys.version.split()[0]}")
    print()

    # Summary table
    print("| Server | Domain | Cold (ms) | Warm (ms) | tools/list (ms) | Tools | Status |")
    print("|--------|--------|-----------|-----------|-----------------|-------|--------|")

    for r in report.results:
        cold = f"{r.cold_start_ms:.0f}" if r.cold_start_ms is not None else "—"
        warm = f"{r.warm_start_ms:.0f}" if r.warm_start_ms is not None else "—"
        tlist = f"{r.tools_list_ms:.1f}" if r.tools_list_ms is not None else "—"
        tools = str(r.tool_count) if r.tool_count > 0 else "—"
        status = (
            "⏭️ SKIP" if r.skipped else
            "❌ ERROR" if r.error else
            "✅"
        )
        print(f"| `{r.name}` | {r.domain} | {cold} | {warm} | {tlist} | {tools} | {status} |")

    print()
    print("### Aggregate")
    tested = [r for r in report.results if not r.skipped]
    succeeded = [r for r in tested if not r.error]
    skipped = [r for r in report.results if r.skipped]
    failed = [r for r in tested if r.error]

    print(f"- **Tested**: {len(tested)} servers")
    print(f"- **Succeeded**: {len(succeeded)}")
    print(f"- **Skipped**: {len(skipped)} ({', '.join(r.name for r in skipped)})")
    print(f"- **Failed**: {len(failed)} ({', '.join(r.name for r in failed)})")

    cold_vals = [r.cold_start_ms for r in succeeded if r.cold_start_ms is not None]
    warm_vals = [r.warm_start_ms for r in succeeded if r.warm_start_ms is not None]
    if cold_vals:
        print(f"- **Total cold start**: {sum(cold_vals):.0f}ms ({sum(cold_vals)/1000:.1f}s)")
        print(f"- **Avg cold start**: {sum(cold_vals)/len(cold_vals):.0f}ms")
    if warm_vals:
        print(f"- **Total warm start**: {sum(warm_vals):.0f}ms ({sum(warm_vals)/1000:.1f}s)")
        print(f"- **Avg warm start**: {sum(warm_vals)/len(warm_vals):.0f}ms")
    if succeeded:
        tools_total = sum(r.tool_count for r in succeeded)
        print(f"- **Total tools exposed**: {tools_total}")


def _print_json(report: BenchmarkReport) -> None:
    """Print benchmark report as JSON."""
    data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "results": [
            {
                "name": r.name,
                "domain": r.domain,
                "cold_start_ms": r.cold_start_ms,
                "warm_start_ms": r.warm_start_ms,
                "tools_list_ms": r.tools_list_ms,
                "tool_count": r.tool_count,
                "error": r.error,
                "skipped": r.skipped,
            }
            for r in report.results
        ],
        "summary": {},
    }
    succeeded = [r for r in report.results if not r.skipped and not r.error]
    cold_vals = [r.cold_start_ms for r in succeeded if r.cold_start_ms is not None]
    warm_vals = [r.warm_start_ms for r in succeeded if r.warm_start_ms is not None]
    data["summary"] = {
        "total_servers": len(report.results),
        "succeeded": len(succeeded),
        "skipped": len([r for r in report.results if r.skipped]),
        "failed": len([r for r in report.results if r.error]),
        "total_cold_start_ms": round(sum(cold_vals), 1) if cold_vals else None,
        "avg_cold_start_ms": round(sum(cold_vals) / len(cold_vals), 1) if cold_vals else None,
        "total_warm_start_ms": round(sum(warm_vals), 1) if warm_vals else None,
        "avg_warm_start_ms": round(sum(warm_vals) / len(warm_vals), 1) if warm_vals else None,
    }
    print(json.dumps(data, indent=2))


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    search_only = "--search-only" in sys.argv
    output_json = "--json" in sys.argv

    if search_only:
        servers = dict(SEARCH_SERVERS)
    else:
        servers = dict(ALL_SERVERS)

    report = BenchmarkReport()

    print("ARIA MCP Startup Latency Benchmark")
    print(f"{'='*50}")
    print(f"Servers to test: {len(servers)} ({', '.join(servers.keys())})")
    print()

    for name, cmd in servers.items():
        domain = "core" if name in CORE_SERVERS else (
            "search" if name in SEARCH_SERVERS else "productivity"
        )
        r = benchmark_server(name, cmd, domain)
        report.add(r)
        print()

    if output_json:
        _print_json(report)
    else:
        _print_markdown(report)


if __name__ == "__main__":
    main()
