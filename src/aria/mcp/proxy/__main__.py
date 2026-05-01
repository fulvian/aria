"""Entry point: python -m aria.mcp.proxy"""
from __future__ import annotations

import asyncio
import logging

from aria.mcp.proxy.server import build_proxy
from aria.utils.logging import get_logger

logger = get_logger("aria.mcp.proxy")


async def _run() -> None:
    proxy = build_proxy()
    logger.info("aria-mcp-proxy starting", extra={"event": "proxy.start"})
    await proxy.run_async(transport="stdio")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
