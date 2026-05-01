"""Tombstone benchmark/test pollution from the episodic store.

Idempotent. Tombstones (P6) only — never hard-deletes.

Usage:
    uv run python -m scripts.memory.cleanup_benchmark_entries [--dry-run]
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from typing import Any

from aria.memory.episodic import EpisodicStore, create_episodic_store

BENCHMARK_PATTERN = re.compile(
    r"^test\s+content\s+entry\s+\d+\s+for\s+memory\s+recall\s+benchmark$",
    re.IGNORECASE,
)
BENCHMARK_TAGS = {"benchmark", "test_seed"}


async def cleanup_benchmark_entries(store: EpisodicStore, *, dry_run: bool) -> dict[str, Any]:
    """Tombstone benchmark entries in the episodic store.

    Args:
        store: Connected EpisodicStore.
        dry_run: If True, only report without writing tombstones.

    Returns:
        Report dict with scanned/tombstoned counts.
    """
    conn = await store._ensure_connected()
    cursor = await conn.execute(
        """
        SELECT e.id, e.content, e.tags
        FROM episodic e
        LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
        WHERE t.episodic_id IS NULL
        """
    )
    rows = await cursor.fetchall()
    scanned = len(rows)
    targets: list[str] = []
    for row in rows:
        tags = json.loads(row["tags"] or "[]")
        if BENCHMARK_TAGS.intersection(tags) or BENCHMARK_PATTERN.match(row["content"] or ""):
            targets.append(row["id"])

    if not dry_run and targets:
        now = int(time.time())
        await conn.executemany(
            """
            INSERT OR IGNORE INTO episodic_tombstones (episodic_id, tombstoned_at, reason)
            VALUES (?, ?, 'benchmark_cleanup')
            """,
            [(tid, now) for tid in targets],
        )
        await conn.commit()

    return {"scanned": scanned, "tombstoned": len(targets), "dry_run": dry_run}


async def _amain(dry_run: bool) -> int:
    from aria.config import get_config

    config = get_config()
    store = await create_episodic_store(config)
    try:
        report = await cleanup_benchmark_entries(store, dry_run=dry_run)
    finally:
        await store.close()
    print(json.dumps(report, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Tombstone benchmark/test rows in episodic.db")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return asyncio.run(_amain(dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
