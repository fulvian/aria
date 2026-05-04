"""Persistent JSON metadata cache for tool discovery.

Stores tool descriptions per-backend on disk so that `tools/list`
can return discovery metadata without connecting to backend processes.
Invalidated automatically when catalog_hash changes.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from aria.utils.logging import get_logger

logger = get_logger("aria.mcp.proxy.tier.metadata_cache")

CACHE_SCHEMA_VERSION = 1
DEFAULT_CACHE_PATH = Path(".aria/runtime/proxy/tool_metadata.json")


class MetadataCache:
    """Persistent tool metadata cache backed by a JSON file.

    Thread-safe (asyncio.Lock) for concurrent read/write.
    """

    def __init__(self, cache_path: Path = DEFAULT_CACHE_PATH) -> None:
        self._path = cache_path
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "catalog_hash": "",
            "updated_at": "",
            "backends": {},
        }

    @property
    def catalog_hash(self) -> str:
        val = self._data.get("catalog_hash", "")
        return val if isinstance(val, str) else ""

    @catalog_hash.setter
    def catalog_hash(self, value: str) -> None:
        self._data["catalog_hash"] = value

    async def load(self) -> None:
        """Load cache from disk. Resets if schema/catalog_hash mismatch."""
        async with self._lock:
            if not self._path.exists():
                self._data = {
                    "schema_version": CACHE_SCHEMA_VERSION,
                    "catalog_hash": "",
                    "updated_at": "",
                    "backends": {},
                }
                return

            try:
                raw = self._path.read_text()
                parsed = json.loads(raw)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("metadata_cache.load_failed", extra={"error": str(exc)})
                self._data = {
                    "schema_version": CACHE_SCHEMA_VERSION,
                    "catalog_hash": "",
                    "updated_at": "",
                    "backends": {},
                }
                return

            if parsed.get("schema_version") != CACHE_SCHEMA_VERSION:
                logger.info("metadata_cache.schema_mismatch_reset")
                self._data = {
                    "schema_version": CACHE_SCHEMA_VERSION,
                    "catalog_hash": "",
                    "updated_at": "",
                    "backends": {},
                }
                return

            self._data = parsed

    async def _save(self) -> None:
        """Atomically write cache to disk (tmp + rename)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self._data, indent=2)
        fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=self._path.parent)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.replace(tmp_path, str(self._path))
        except OSError:
            # Async function using Path for cleanup after os.replace — acceptable.
            tmp = Path(tmp_path)  # noqa: ASYNC240
            if tmp.exists():  # noqa: ASYNC240
                tmp.unlink()  # noqa: ASYNC240
            raise

    async def update(self, backend_name: str, tools: list[dict[str, Any]]) -> None:
        """Update tools for a backend and persist to disk."""
        async with self._lock:
            self._data.setdefault("backends", {})[backend_name] = tools
            self._data["updated_at"] = (
                __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            )
            await self._save()

    async def update_batch(self, updates: dict[str, list[dict[str, Any]]]) -> None:
        """Update multiple backends at once and persist."""
        async with self._lock:
            for name, tools in updates.items():
                self._data.setdefault("backends", {})[name] = tools
            self._data["updated_at"] = (
                __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            )
            await self._save()

    def get(self, backend_name: str) -> list[dict[str, Any]]:
        """Get cached tools for a backend. Returns empty list if missing."""
        return list(self._data.get("backends", {}).get(backend_name, []))

    def get_all_backends(self) -> dict[str, list[dict[str, Any]]]:
        """Get all cached backends and their tools."""
        return dict(self._data.get("backends", {}))

    def invalidate(self) -> None:
        """Reset all cached data in memory (not persisted)."""
        self._data = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "catalog_hash": "",
            "updated_at": "",
            "backends": {},
        }

    def has_backend(self, backend_name: str) -> bool:
        return backend_name in self._data.get("backends", {})

    @property
    def backend_names(self) -> list[str]:
        return list(self._data.get("backends", {}).keys())
