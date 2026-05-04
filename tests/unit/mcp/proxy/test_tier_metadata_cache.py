"""Unit tests for the persistent metadata cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from aria.mcp.proxy.tier.metadata_cache import MetadataCache


@pytest.mark.asyncio
async def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    cache = MetadataCache(cache_path=tmp_path / "nonexistent.json")
    await cache.load()
    assert cache.catalog_hash == ""
    assert cache.get("any") == []


@pytest.mark.asyncio
async def test_update_and_get(tmp_path: Path) -> None:
    cache = MetadataCache(cache_path=tmp_path / "cache.json")
    await cache.load()

    tools = [{"name": "foo", "description": "Foo tool", "parameters": {}}]
    await cache.update("test-backend", tools)

    result = cache.get("test-backend")
    assert len(result) == 1
    assert result[0]["name"] == "foo"
    assert result[0]["description"] == "Foo tool"


@pytest.mark.asyncio
async def test_update_batch(tmp_path: Path) -> None:
    cache = MetadataCache(cache_path=tmp_path / "cache.json")
    await cache.load()

    await cache.update_batch(
        {
            "backend-a": [{"name": "a_tool", "description": "Tool A", "parameters": {}}],
            "backend-b": [{"name": "b_tool", "description": "Tool B", "parameters": {}}],
        }
    )

    assert len(cache.get("backend-a")) == 1
    assert len(cache.get("backend-b")) == 1
    assert cache.get("backend-c") == []


@pytest.mark.asyncio
async def test_persistence_across_loads(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    cache1 = MetadataCache(cache_path=path)
    await cache1.load()
    assert cache1.catalog_hash == ""

    cache1.catalog_hash = "abc123"
    await cache1.update(  # noqa: E501
        "persist-backend", [{"name": "persist_tool", "description": "", "parameters": {}}]
    )

    # Load a fresh instance
    cache2 = MetadataCache(cache_path=path)
    await cache2.load()
    assert cache2.catalog_hash == "abc123"
    result = cache2.get("persist-backend")
    assert len(result) == 1
    assert result[0]["name"] == "persist_tool"


@pytest.mark.asyncio
async def test_invalidation_on_catalog_hash_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    cache1 = MetadataCache(cache_path=path)
    await cache1.load()
    cache1.catalog_hash = "old-hash"
    await cache1.update("backend", [{"name": "t1", "description": "", "parameters": {}}])

    # Fresh load with different catalog_hash simulates mismatch
    cache2 = MetadataCache(cache_path=path)
    await cache2.load()
    assert cache2.catalog_hash == "old-hash"
    # Normally the provider would call invalidate() on mismatch
    cache2.invalidate()
    assert cache2.catalog_hash == ""
    assert cache2.get("backend") == []


@pytest.mark.asyncio
async def test_corrupted_file_falls_back_to_empty(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    path.write_text("not valid json{")
    cache = MetadataCache(cache_path=path)
    await cache.load()
    assert cache.catalog_hash == ""
    assert cache.get("any") == []


@pytest.mark.asyncio
async def test_has_backend(tmp_path: Path) -> None:
    cache = MetadataCache(cache_path=tmp_path / "cache.json")
    await cache.load()
    assert cache.has_backend("test") is False
    await cache.update("test", [{"name": "t", "description": "", "parameters": {}}])
    assert cache.has_backend("test") is True


@pytest.mark.asyncio
async def test_backend_names(tmp_path: Path) -> None:
    cache = MetadataCache(cache_path=tmp_path / "cache.json")
    await cache.load()
    assert cache.backend_names == []

    await cache.update_batch(
        {
            "a": [],
            "b": [],
        }
    )
    assert sorted(cache.backend_names) == ["a", "b"]


@pytest.mark.asyncio
async def test_get_all_backends(tmp_path: Path) -> None:
    cache = MetadataCache(cache_path=tmp_path / "cache.json")
    await cache.load()
    await cache.update_batch(
        {
            "a": [{"name": "a1", "description": "", "parameters": {}}],
        }
    )
    all_b = cache.get_all_backends()
    assert "a" in all_b
    assert len(all_b["a"]) == 1
