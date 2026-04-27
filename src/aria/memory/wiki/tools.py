# ARIA Memory Wiki — MCP Tool Implementations
#
# Per docs/plans/auto_persistence_echo.md §7.
#
# Four MCP tools for wiki operations:
# - wiki_update: End-of-turn structured patch
# - wiki_recall: FTS5 search returning scored pages
# - wiki_show: Get full page by kind+slug
# - wiki_list: List pages by kind
#
# These are registered alongside existing tools in mcp_server.py.
#
# Usage:
#   from aria.memory.wiki.tools import register_wiki_tools
#   register_wiki_tools(mcp_server, wiki_store)

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from aria.memory.wiki.db import WikiStore
from aria.memory.wiki.recall import WikiRecallEngine
from aria.memory.wiki.schema import (
    PageKind,
    WikiUpdatePayload,
)
from aria.utils.logging import new_trace_id, set_trace_id

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# === Global State ===

_wiki_store: WikiStore | None = None
_recall_engine: WikiRecallEngine | None = None


async def _ensure_wiki() -> tuple[WikiStore, WikiRecallEngine]:
    """Ensure wiki store and recall engine are initialized."""
    global _wiki_store, _recall_engine  # noqa: PLW0603

    if _wiki_store is None:
        aria_home = Path(os.environ.get("ARIA_HOME", "/home/fulvio/coding/aria"))
        db_path = aria_home / ".aria" / "runtime" / "memory" / "wiki.db"
        _wiki_store = WikiStore(db_path)
        await _wiki_store.connect()
        _recall_engine = WikiRecallEngine(_wiki_store)

    if _recall_engine is None:
        _recall_engine = WikiRecallEngine(_wiki_store)

    return _wiki_store, _recall_engine


# === Tool Functions ===


async def wiki_update(
    patches_json: str,
) -> dict:
    """Persist salience extracted from current turn.

    Called ONCE at end of every conductor turn.
    Per plan §5.1: structured patches for wiki page mutations.

    Args:
        patches_json: JSON string of WikiUpdatePayload.

    Returns:
        {"status": "ok", "applied": N, "errors": [...]}
    """
    import json

    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, _ = await _ensure_wiki()

        # Parse payload
        raw = json.loads(patches_json)
        payload = WikiUpdatePayload(**raw)

        applied = 0
        errors: list[str] = []
        profile_updated = False

        for i, patch in enumerate(payload.patches):
            try:
                await store.apply_patch(patch)
                applied += 1
                # Track if profile was updated (for template regeneration)
                if patch.kind.value == "profile":
                    profile_updated = True
            except Exception as exc:
                error_msg = f"Patch {i} ({patch.kind.value}/{patch.slug}): {exc}"
                errors.append(error_msg)
                logger.warning("wiki_update patch failed: %s", error_msg)

        # Regenerate conductor template on profile update (plan §6.1)
        if profile_updated:
            try:
                from aria.memory.wiki.prompt_inject import regenerate_conductor_template

                await regenerate_conductor_template(store)
            except Exception as exc:
                logger.warning("Failed to regenerate conductor template: %s", exc)

        # Advance watermark if session info provided
        if payload.kilo_session_id and payload.last_msg_id:
            import time

            await store.set_watermark(
                payload.kilo_session_id,
                payload.last_msg_id,
                int(time.time()),
            )

        result: dict = {
            "status": "ok" if not errors else "partial",
            "applied": applied,
            "total_patches": len(payload.patches),
        }
        if errors:
            result["errors"] = errors
        if not payload.patches and payload.no_salience_reason:
            result["no_salience_reason"] = payload.no_salience_reason

        return result

    except json.JSONDecodeError as exc:
        return {"status": "error", "error": f"Invalid JSON: {exc}"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def wiki_recall(
    query: str,
    max_pages: int = 5,
    min_score: float = 0.3,
) -> list[dict]:
    """FTS5 search returning scored wiki pages.

    Per plan §6.2: mandatory first action of each conductor turn.
    Returns pages matched against the user's message.

    Args:
        query: Search query (typically the user's message).
        max_pages: Maximum pages to return (default 5).
        min_score: Minimum relevance score 0-1 (default 0.3).

    Returns:
        List of {kind, slug, title, body_excerpt, score}.
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        _, engine = await _ensure_wiki()

        results = await engine.recall(
            query=query,
            max_pages=max_pages,
            min_score=min_score,
        )

        return [
            {
                "kind": r.kind.value,
                "slug": r.slug,
                "title": r.title,
                "body_excerpt": r.body_excerpt,
                "score": r.score,
            }
            for r in results
        ]

    except Exception as exc:
        return [{"error": str(exc)}]


async def wiki_show(
    kind: str,
    slug: str,
) -> dict:
    """Get full wiki page by kind and slug.

    Args:
        kind: Page kind (profile, topic, lesson, entity, decision).
        slug: Page slug (kebab-case).

    Returns:
        Full page dict or {"error": "not found"}.
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, _ = await _ensure_wiki()

        page_kind = PageKind(kind)
        page = await store.get_page(page_kind, slug)

        if page is None:
            return {"status": "not_found", "kind": kind, "slug": slug}

        return {
            "status": "ok",
            "id": page.id,
            "kind": page.kind.value,
            "slug": page.slug,
            "title": page.title,
            "body_md": page.body_md,
            "confidence": page.confidence,
            "importance": page.importance,
            "source_kilo_msg_ids": page.source_kilo_msg_ids,
            "first_seen": page.first_seen,
            "last_seen": page.last_seen,
            "occurrences": page.occurrences,
        }

    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def wiki_list(
    kind: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List wiki pages, optionally filtered by kind.

    Args:
        kind: Optional page kind filter.
        limit: Maximum pages to return (default 50).

    Returns:
        List of page summary dicts.
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, _ = await _ensure_wiki()

        kind_filter = PageKind(kind) if kind else None
        pages = await store.list_pages(kind=kind_filter, limit=limit)

        return [
            {
                "id": p.id,
                "kind": p.kind.value,
                "slug": p.slug,
                "title": p.title,
                "importance": p.importance,
                "last_seen": p.last_seen,
                "occurrences": p.occurrences,
            }
            for p in pages
        ]

    except Exception as exc:
        return [{"error": str(exc)}]


# === Registration Helper ===


def register_wiki_tools(mcp_server: FastMCP) -> None:
    """Register wiki MCP tools on an existing FastMCP server.

    Per plan §7: adds 4 new wiki tools alongside existing memory tools.

    Args:
        mcp_server: FastMCP server instance.
    """

    @mcp_server.tool
    async def wiki_update_tool(
        patches_json: str,
    ) -> dict:
        """Persist salience extracted from current turn.

        Called ONCE at end of every conductor turn.
        patches_json: JSON string of WikiUpdatePayload with patches list.
        """
        return await wiki_update(patches_json)

    @mcp_server.tool
    async def wiki_recall_tool(
        query: str,
        max_pages: int = 5,
        min_score: float = 0.3,
    ) -> list[dict]:
        """FTS5 search returning scored wiki pages. Mandatory first action per turn.

        Args:
            query: Search query (user message).
            max_pages: Max results (default 5).
            min_score: Min relevance 0-1 (default 0.3).
        """
        return await wiki_recall(query, max_pages, min_score)

    @mcp_server.tool
    async def wiki_show_tool(
        kind: str,
        slug: str,
    ) -> dict:
        """Get full wiki page by kind and slug.

        Args:
            kind: Page kind (profile, topic, lesson, entity, decision).
            slug: Page slug (kebab-case).
        """
        return await wiki_show(kind, slug)

    @mcp_server.tool
    async def wiki_list_tool(
        kind: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List wiki pages, optionally filtered by kind.

        Args:
            kind: Optional page kind filter.
            limit: Max pages to return (default 50).
        """
        return await wiki_list(kind, limit)

    logger.info("Registered 4 wiki MCP tools")
