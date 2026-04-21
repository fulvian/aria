"""
Search result caching per blueprint §11.5.

Stores query→results in episodic memory tagged `search_cache`.
TTL default: 6 hours per blueprint §11.5.
"""

import hashlib
import json
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import UUID

from aria.agents.search.schema import SearchHit
from aria.memory.episodic import EpisodicStore

logger = logging.getLogger(__name__)

SEARCH_CACHE_TAG = "search_cache"
CACHE_TTL_HOURS = 6


def canonicalize_query(query: str) -> str:
    """Canonicalize query string for cache key.

    Args:
        query: Raw query string.

    Returns:
        Lowercased, stripped query string.
    """
    return query.lower().strip()


def _cache_key(intent: str, query: str) -> str:
    """Generate cache key from intent and query.

    Args:
        intent: Intent classification string.
        query: Canonicalized query.

    Returns:
        SHA256 cache key.
    """
    raw = f"{intent}:{canonicalize_query(query)}"
    return hashlib.sha256(raw.encode()).hexdigest()


class SearchCache:
    """Cache for search results using episodic memory per blueprint §11.5.

    Stores results in EpisodicStore with tag `search_cache`.
    TTL: 6 hours default per blueprint §11.5.
    """

    def __init__(
        self,
        store: EpisodicStore,
        ttl_hours: int = CACHE_TTL_HOURS,
    ) -> None:
        """Initialize cache.

        Args:
            store: EpisodicStore instance.
            ttl_hours: Cache TTL in hours (default 6 per blueprint).
        """
        self._store = store
        self._ttl = timedelta(hours=ttl_hours)

    def _hits_to_json(self, hits: list[SearchHit]) -> str:
        """Serialize hits list to JSON string.

        Args:
            hits: List of SearchHit.

        Returns:
            JSON string.
        """
        data = [
            {
                "title": h.title,
                "url": str(h.url),
                "snippet": h.snippet,
                "published_at": (h.published_at.isoformat() if h.published_at else None),
                "score": h.score,
                "provider": h.provider,
            }
            for h in hits
        ]
        return json.dumps(data, ensure_ascii=False)

    def _json_to_hits(self, data: str) -> list[SearchHit]:
        """Deserialize JSON string to hits list.

        Args:
            data: JSON string.

        Returns:
            List of SearchHit.
        """
        items = json.loads(data)
        hits = []
        for item in items:
            published_at = None
            with suppress(ValueError, TypeError):
                published_at = datetime.fromisoformat(item["published_at"])

            hits.append(
                SearchHit(
                    title=item["title"],
                    url=item["url"],
                    snippet=item["snippet"],
                    published_at=published_at,
                    score=item.get("score", 0.0),
                    provider=item["provider"],
                )
            )
        return hits

    async def get(self, query: str, intent: str) -> list[SearchHit] | None:
        """Get cached search results.

        Args:
            query: Search query string.
            intent: Intent classification string.

        Returns:
            Cached hits if found and not expired, else None.
        """
        cache_key = _cache_key(intent, query)
        now = datetime.now(UTC)
        cutoff = now - self._ttl

        # Search episodic store for cache entries
        entries = await self._store.search_by_tag(
            tag=SEARCH_CACHE_TAG,
            since=None,
            until=None,
            limit=100,
        )

        for entry in entries:
            # Check if this is our cache entry
            meta_obj = entry.get("meta", {})
            if not isinstance(meta_obj, dict):
                continue
            meta = meta_obj
            if meta.get("cache_key") != cache_key:
                continue

            # Check TTL
            entry_ts_str = meta.get("cached_at")
            if not entry_ts_str:
                continue
            try:
                entry_ts = datetime.fromisoformat(str(entry_ts_str))
                if entry_ts.tzinfo is None:
                    entry_ts = entry_ts.replace(tzinfo=UTC)
            except (ValueError, TypeError):
                continue

            if entry_ts < cutoff:
                # Expired
                continue

            # Found valid cache entry
            content_obj = entry.get("content", "")
            if not isinstance(content_obj, str):
                continue
            try:
                return self._json_to_hits(content_obj)
            except (json.JSONDecodeError, KeyError):
                logger.warning("Failed to deserialize cache entry: %s", entry.get("id"))
                return None

        return None

    async def put(self, query: str, intent: str, hits: list[SearchHit]) -> None:
        """Store search results in cache.

        Args:
            query: Search query.
            intent: Intent classification string.
            hits: List of SearchHit to cache.
        """
        if not hits:
            return

        cache_key = _cache_key(intent, query)
        content = self._hits_to_json(hits)
        now = datetime.now(UTC)

        from aria.memory.schema import Actor

        await self._store.add(
            session_id="search_cache",
            actor=Actor.SYSTEM_EVENT,
            role="system",
            content=content,
            tags=[SEARCH_CACHE_TAG, intent],
            meta={
                "cache_key": cache_key,
                "cached_at": now.isoformat(),
                "query": query,
                "intent": intent,
            },
        )

    async def invalidate(self, query: str | None = None) -> int:
        """Invalidate cache entries.

        Args:
            query: If provided, invalidate only entries matching this query.
                   If None, invalidate all cache entries.

        Returns:
            Number of entries invalidated.
        """
        logger.info("Cache invalidate requested for query=%s", query)

        entries = await self._store.search_by_tag(
            tag=SEARCH_CACHE_TAG,
            since=None,
            until=None,
            limit=1000,
        )

        invalidated = 0
        for entry in entries:
            meta = entry.get("meta", {})
            if not isinstance(meta, dict):
                continue

            if query is not None and meta.get("query") != query:
                continue

            entry_id = entry.get("id")
            if not isinstance(entry_id, str):
                continue

            with suppress(ValueError):
                deleted = await self._store.tombstone(
                    UUID(entry_id), reason="search_cache_invalidate"
                )
                if deleted:
                    invalidated += 1

        return invalidated
