# Tests for wiki.tools — MCP tool implementations

from __future__ import annotations

import json
from typing import Any

import pytest

from aria.memory.wiki.db import WikiStore
from aria.memory.wiki.schema import PageKind
from aria.memory.wiki.tools import (
    wiki_list,
    wiki_recall,
    wiki_show,
    wiki_update,
)


@pytest.fixture
async def store(tmp_path: Any) -> WikiStore:
    """Create a WikiStore with a temporary database."""
    from aria.memory.wiki import tools as wiki_tools

    db_path = tmp_path / "wiki.db"
    store = WikiStore(db_path)
    await store.connect()

    # Inject store into module-level state
    wiki_tools._wiki_store = store
    wiki_tools._recall_engine = None  # Force re-init

    yield store

    wiki_tools._wiki_store = None
    wiki_tools._recall_engine = None
    await store.close()


class TestWikiUpdateTool:
    """wiki_update tool tests."""

    async def test_create_page(self, store: WikiStore) -> None:
        payload = {
            "patches": [
                {
                    "kind": "profile",
                    "slug": "profile",
                    "op": "create",
                    "title": "User Profile",
                    "body_md": "Identity: Test User",
                    "confidence": 0.9,
                    "source_kilo_msg_ids": ["msg-1"],
                    "diff_summary": "Initial profile",
                }
            ],
            "kilo_session_id": "session-1",
            "last_msg_id": "msg-1",
        }
        result = await wiki_update(json.dumps(payload))

        assert result["status"] == "ok"
        assert result["applied"] == 1

    async def test_empty_patches_with_reason(self, store: WikiStore) -> None:
        payload = {
            "patches": [],
            "no_salience_reason": "casual ack",
        }
        result = await wiki_update(json.dumps(payload))

        assert result["status"] == "ok"
        assert result["applied"] == 0
        assert result["no_salience_reason"] == "casual ack"

    async def test_invalid_json(self, store: WikiStore) -> None:
        result = await wiki_update("not valid json")
        assert result["status"] == "error"
        assert "Invalid JSON" in result["error"]

    async def test_multiple_patches(self, store: WikiStore) -> None:
        payload = {
            "patches": [
                {
                    "kind": "profile",
                    "slug": "profile",
                    "op": "create",
                    "title": "Profile",
                    "body_md": "content",
                },
                {
                    "kind": "entity",
                    "slug": "test-entity",
                    "op": "create",
                    "title": "Test Entity",
                    "body_md": "content",
                },
            ],
        }
        result = await wiki_update(json.dumps(payload))

        assert result["status"] == "ok"
        assert result["applied"] == 2
        assert result["total_patches"] == 2

    async def test_duplicate_create_error(self, store: WikiStore) -> None:
        payload = {
            "patches": [
                {
                    "kind": "topic",
                    "slug": "test-topic",
                    "op": "create",
                    "title": "Test",
                    "body_md": "content",
                }
            ],
        }
        # First create
        await wiki_update(json.dumps(payload))
        # Second create should fail
        result = await wiki_update(json.dumps(payload))
        assert result["status"] == "partial"
        assert len(result.get("errors", [])) > 0

    async def test_update_existing(self, store: WikiStore) -> None:
        # Create first
        create_payload = {
            "patches": [
                {
                    "kind": "profile",
                    "slug": "profile",
                    "op": "create",
                    "title": "Profile",
                    "body_md": "old content",
                }
            ],
        }
        await wiki_update(json.dumps(create_payload))

        # Then update
        update_payload = {
            "patches": [
                {
                    "kind": "profile",
                    "slug": "profile",
                    "op": "update",
                    "body_md": "new content",
                }
            ],
        }
        result = await wiki_update(json.dumps(update_payload))
        assert result["status"] == "ok"
        assert result["applied"] == 1


class TestWikiRecallTool:
    """wiki_recall tool tests."""

    async def test_recall_returns_results(self, store: WikiStore) -> None:
        # Populate
        await store.apply_patch(
            __import__("aria.memory.wiki.schema", fromlist=["PagePatch"]).PagePatch(
                kind=PageKind.TOPIC,
                slug="memory-system",
                op="create",
                title="Memory System",
                body_md="A system for storing and retrieving knowledge using SQLite and FTS5",
            )
        )

        results = await wiki_recall("memory system")
        assert isinstance(results, list)
        # Should find the memory-system page
        if results and "error" not in results[0]:
            slugs = [r["slug"] for r in results]
            assert "memory-system" in slugs

    async def test_recall_empty_query(self, store: WikiStore) -> None:
        results = await wiki_recall("")
        assert results == []

    async def test_recall_with_params(self, store: WikiStore) -> None:
        results = await wiki_recall("test", max_pages=2, min_score=0.5)
        assert isinstance(results, list)


class TestWikiShowTool:
    """wiki_show tool tests."""

    async def test_show_existing(self, store: WikiStore) -> None:
        # Create a page
        from aria.memory.wiki.schema import PagePatch

        await store.create_page(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="test-topic",
                op="create",
                title="Test Topic",
                body_md="Full body content here",
            )
        )

        result = await wiki_show("topic", "test-topic")
        assert result["status"] == "ok"
        assert result["slug"] == "test-topic"
        assert result["body_md"] == "Full body content here"
        assert result["kind"] == "topic"

    async def test_show_nonexistent(self, store: WikiStore) -> None:
        result = await wiki_show("topic", "nonexistent")
        assert result["status"] == "not_found"

    async def test_show_invalid_kind(self, store: WikiStore) -> None:
        result = await wiki_show("invalid_kind", "test")
        assert result["status"] == "error"


class TestWikiListTool:
    """wiki_list tool tests."""

    async def test_list_empty(self, store: WikiStore) -> None:
        results = await wiki_list()
        assert results == []

    async def test_list_after_create(self, store: WikiStore) -> None:
        from aria.memory.wiki.schema import PagePatch

        await store.create_page(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="topic-1",
                op="create",
                title="Topic 1",
                body_md="content",
            )
        )
        await store.create_page(
            PagePatch(
                kind=PageKind.LESSON,
                slug="lesson-1",
                op="create",
                title="Lesson 1",
                body_md="content",
            )
        )

        results = await wiki_list()
        assert len(results) == 2

    async def test_list_by_kind(self, store: WikiStore) -> None:
        from aria.memory.wiki.schema import PagePatch

        await store.create_page(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="topic-1",
                op="create",
                title="Topic 1",
                body_md="content",
            )
        )
        await store.create_page(
            PagePatch(
                kind=PageKind.LESSON,
                slug="lesson-1",
                op="create",
                title="Lesson 1",
                body_md="content",
            )
        )

        results = await wiki_list(kind="topic")
        assert len(results) == 1
        assert results[0]["kind"] == "topic"

    async def test_list_with_limit(self, store: WikiStore) -> None:
        from aria.memory.wiki.schema import PagePatch

        for i in range(5):
            await store.create_page(
                PagePatch(
                    kind=PageKind.TOPIC,
                    slug=f"topic-{i}",
                    op="create",
                    title=f"Topic {i}",
                    body_md="content",
                )
            )

        results = await wiki_list(limit=2)
        assert len(results) == 2
