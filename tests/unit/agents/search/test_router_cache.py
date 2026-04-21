"""Unit tests for search router and cache behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from aria.agents.search.cache import SearchCache
from aria.agents.search.router import SearchRouter
from aria.agents.search.schema import Intent, ProviderStatus, SearchHit


class _FakeStore:
    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []
        self.tombstoned: set[str] = set()

    async def add(self, **kwargs):
        entry_id = str(uuid4())
        entry = {
            "id": entry_id,
            "content": kwargs["content"],
            "meta": kwargs.get("meta", {}),
            "tags": kwargs.get("tags", []),
        }
        self.entries.append(entry)
        return entry

    async def search_by_tag(self, tag, since=None, until=None, limit=100):
        results = []
        for entry in reversed(self.entries):
            if entry["id"] in self.tombstoned:
                continue
            if tag in entry.get("tags", []):
                results.append(entry)
            if len(results) >= limit:
                break
        return results

    async def tombstone(self, id: UUID, reason: str):
        _ = reason
        needle = str(id)
        ids = {str(e["id"]) for e in self.entries}
        if needle in ids:
            self.tombstoned.add(needle)
            return True
        return False


class _Key:
    def __init__(self) -> None:
        self.key_id = "k1"


class _FakeCM:
    def __init__(self):
        self.success = 0
        self.failure = 0
        self.blocked: set[str] = set()

    async def acquire(self, provider):
        if provider in self.blocked:
            return None
        return _Key()

    async def report_success(self, provider, key_id, credits_used=1):
        _ = (provider, key_id, credits_used)
        self.success += 1

    async def report_failure(self, provider, key_id, reason, retry_after=None):
        _ = (provider, key_id, reason, retry_after)
        self.failure += 1


class _FakeHealth:
    def __init__(self):
        self.map: dict[str, ProviderStatus] = {}

    def status(self, provider):
        return self.map.get(provider, ProviderStatus.AVAILABLE)


class _FakeProvider:
    def __init__(self, name: str):
        self.name = name
        self.calls = 0

    async def search(self, query, top_k=10, **kwargs):
        _ = (query, top_k, kwargs)
        self.calls += 1
        return [
            SearchHit(
                title=f"{self.name} result",
                url="https://example.com/article",
                snippet="snippet",
                published_at=datetime.now(UTC) - timedelta(days=1),
                score=0.8,
                provider=self.name,
            )
        ]

    async def health_check(self):
        return ProviderStatus.AVAILABLE


@pytest.mark.asyncio
async def test_search_cache_put_get_invalidate():
    store = _FakeStore()
    cache = SearchCache(store=store, ttl_hours=6)

    hits = [
        SearchHit(
            title="Result",
            url="https://example.com/path",
            snippet="content",
            provider="tavily",
            score=0.9,
        )
    ]

    await cache.put(query="Test Query", intent="general", hits=hits)
    cached = await cache.get(query="test query", intent="general")

    assert cached is not None
    assert len(cached) == 1
    assert str(cached[0].url) == "https://example.com/path"

    invalidated = await cache.invalidate(query="Test Query")
    assert invalidated == 1


@pytest.mark.asyncio
async def test_router_resolves_provider_aliases_and_skips_degraded():
    cm = _FakeCM()
    health = _FakeHealth()
    store = _FakeStore()
    cache = SearchCache(store=store, ttl_hours=6)

    brave = _FakeProvider("brave")
    providers = {"brave": brave}

    router = SearchRouter(cm=cm, health=health, cache=cache, providers=providers)

    # alias route `brave_news` should resolve to `brave`
    results = await router.route("ultime news su AI", intent=Intent.NEWS)
    assert len(results) == 1
    assert brave.calls == 1

    # degraded provider should be skipped
    health.map["brave"] = ProviderStatus.DEGRADED
    results_2 = await router.route("breaking news economia", intent=Intent.NEWS)
    assert len(results_2) == 0
