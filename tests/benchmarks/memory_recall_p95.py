from __future__ import annotations

import argparse
import asyncio
import math
import random
import statistics
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from aria.config import ARIAConfig
from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry


@dataclass(frozen=True)
class BenchmarkConfig:
    entries: int
    queries: int
    threshold_ms: float
    seed: int


def _random_actor() -> Actor:
    return random.choice(list(Actor))


def _random_content(index: int) -> str:
    themes = [
        "user authentication",
        "file processing task",
        "tool execution result",
        "conversation summary",
        "agent reasoning trace",
    ]
    verbs = ["completed", "failed", "started", "reviewed", "optimized"]
    theme = random.choice(themes)
    verb = random.choice(verbs)
    anchors = [theme.split()[0], verb, "ARIA", "agent"]
    filler = " ".join(random.choices(anchors, k=40))
    return f"[{index:04d}] {verb} {theme} - {filler}"


async def _build_store(db_path: Path, config: BenchmarkConfig) -> EpisodicStore:
    random.seed(config.seed)
    aria_config = ARIAConfig.from_env()
    store = EpisodicStore(db_path=db_path, config=aria_config)
    await store.connect()

    entries = [
        EpisodicEntry(
            session_id=uuid4(),
            ts=datetime.now(tz=UTC),
            actor=_random_actor(),
            role="user",
            content=_random_content(index),
        )
        for index in range(config.entries)
    ]
    await store.insert_many(entries)
    return store


async def _run_queries(store: EpisodicStore, config: BenchmarkConfig) -> list[float]:
    keywords = [
        "authentication",
        "processing",
        "execution",
        "conversation",
        "reasoning",
        "ARIA",
        "agent",
    ]
    latencies_ms: list[float] = []
    for _ in range(config.queries):
        query = random.choice(keywords)
        start = time.perf_counter()
        await store.search_text(query, top_k=20)
        latencies_ms.append((time.perf_counter() - start) * 1000)
    return latencies_ms


async def run_benchmark(config: BenchmarkConfig) -> dict[str, float]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "episodic_benchmark.db"
        populate_start = time.perf_counter()
        store = await _build_store(db_path, config)
        populate_ms = (time.perf_counter() - populate_start) * 1000
        try:
            latencies = await _run_queries(store, config)
        finally:
            await store.close()

        latencies.sort()
        p50 = latencies[math.floor(config.queries * 0.50)]
        p95 = latencies[math.floor(config.queries * 0.95)]
        p99 = latencies[math.floor(config.queries * 0.99)]

        return {
            "populate_ms": populate_ms,
            "mean": statistics.mean(latencies),
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "max": latencies[-1],
        }


def _parse_args() -> BenchmarkConfig:
    parser = argparse.ArgumentParser(description="ARIA memory recall p95 benchmark")
    parser.add_argument("--entries", type=int, default=1000)
    parser.add_argument("--queries", type=int, default=200)
    parser.add_argument("--fail-if-p95-above-ms", type=float, default=250.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    return BenchmarkConfig(
        entries=args.entries,
        queries=args.queries,
        threshold_ms=args.fail_if_p95_above_ms,
        seed=args.seed,
    )


def main() -> int:
    config = _parse_args()
    print("=== ARIA Memory Recall p95 Benchmark ===")
    print(f"Entries: {config.entries}")
    print(f"Queries: {config.queries}")
    print(f"Threshold: {config.threshold_ms}ms")
    print()

    try:
        stats = asyncio.run(run_benchmark(config))
    except MemoryError as exc:
        print(f"Environment does not satisfy SQLite minimum requirement: {exc}")
        return 2

    print(f"Populate: {stats['populate_ms']:.1f}ms ({config.entries} entries)")
    print("Query latencies:")
    print(f"  mean: {stats['mean']:.2f}ms")
    print(f"  p50 : {stats['p50']:.2f}ms")
    print(f"  p95 : {stats['p95']:.2f}ms")
    print(f"  p99 : {stats['p99']:.2f}ms")
    print(f"  max : {stats['max']:.2f}ms")

    if stats["p95"] < config.threshold_ms:
        print(f"BENCHMARK PASSED: p95 ({stats['p95']:.2f}ms) < {config.threshold_ms}ms")
        return 0

    print(f"BENCHMARK FAILED: p95 ({stats['p95']:.2f}ms) >= {config.threshold_ms}ms")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
