#!/usr/bin/env python
"""Connect to the proxy and emit a sample of search_tools latency.

Output JSONL to .aria/runtime/proxy/shadow-{YYYYMMDD-HHMM}.jsonl.
Uses ARIA_PROXY_DISABLE_BACKENDS to skip real MCP backend startup —
search_tools operates on tool name/index metadata, not backend data,
so latency measurements are valid without real backends.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path

os.environ["ARIA_PROXY_DISABLE_BACKENDS"] = "1"

from aria.mcp.proxy.server import build_proxy  # noqa: E402

QUERIES = [
    "wiki recall",
    "send email",
    "search papers",
    "read pdf",
    "calendar event",
    "tavily search",
    "reddit search",
    "filesystem read",
    "convert pdf",
    "github repo discovery",
]


async def main() -> None:
    out_dir = Path(".aria/runtime/proxy")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M")
    out_file = out_dir / f"shadow-{stamp}.jsonl"

    proxy = build_proxy(strict=False)
    from fastmcp import Client  # noqa: E402

    async with Client(proxy) as client:
        with out_file.open("w") as f:
            for q in QUERIES * 3:  # 30 calls = 3 rounds
                t0 = time.perf_counter()
                try:
                    res = await client.call_tool("search_tools", {"query": q})
                    latency_ms = (time.perf_counter() - t0) * 1000
                    entry = {
                        "q": q,
                        "ok": True,
                        "latency_ms": round(latency_ms, 1),
                        "n_results": (len(res.content) if hasattr(res, "content") else 0),
                    }
                    f.write(json.dumps(entry) + "\n")
                    print(f"OK  {q:40s} {latency_ms:7.1f}ms")
                except Exception as exc:
                    entry = {"q": q, "ok": False, "err": str(exc)}
                    f.write(json.dumps(entry) + "\n")
                    print(f"ERR {q:40s} {exc}")

    print(f"\nWrote {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
