# Tests for wiki.recall — FTS5 search + score thresholding

from __future__ import annotations

from typing import Any

import pytest

from aria.memory.wiki.db import WikiStore
from aria.memory.wiki.recall import RecallResult, WikiRecallEngine
from aria.memory.wiki.schema import PageKind, PagePatch


@pytest.fixture
async def populated_store(tmp_path: Any) -> WikiStore:
    """Create a WikiStore with test pages for recall testing."""
    db_path = tmp_path / "wiki.db"
    store = WikiStore(db_path)
    await store.connect()

    # Create profile
    await store.create_page(
        PagePatch(
            kind=PageKind.PROFILE,
            slug="profile",
            op="create",
            title="User Profile",
            body_md=(
                "Identity: Fulvio\n"
                "Preferences: prefers detailed explanations, hates vague answers\n"
                "Working Style: iterative, test-driven"
            ),
            source_kilo_msg_ids=["msg-1"],
        )
    )

    # Create topics
    await store.create_page(
        PagePatch(
            kind=PageKind.TOPIC,
            slug="memory-system",
            op="create",
            title="Memory System Design",
            body_md=(
                "## Overview\n"
                "The memory system uses SQLite with FTS5 for full-text search.\n"
                "Pages are organized by kind: profile, topic, lesson, entity, decision.\n"
                "## Architecture\n"
                "Two-store model: kilo.db (raw) + wiki.db (distilled)."
            ),
            source_kilo_msg_ids=["msg-2"],
        )
    )

    await store.create_page(
        PagePatch(
            kind=PageKind.TOPIC,
            slug="oauth-fix",
            op="create",
            title="OAuth Fix Implementation",
            body_md=(
                "## Problem\n"
                "OAuth callback was failing due to localhost resolution.\n"
                "## Solution\n"
                "Changed redirect URI from localhost to 127.0.0.1."
            ),
            source_kilo_msg_ids=["msg-3"],
        )
    )

    # Create lesson
    await store.create_page(
        PagePatch(
            kind=PageKind.LESSON,
            slug="dont-mock-db",
            op="create",
            title="Don't Mock the Database",
            body_md=(
                "## Rule\n"
                "Always use real SQLite in-memory databases for integration tests.\n"
                "## Why\n"
                "Mocked databases hide real query behavior and edge cases.\n"
                "## When to Apply\n"
                "All database-dependent tests."
            ),
            source_kilo_msg_ids=["msg-4"],
        )
    )

    # Create entity
    await store.create_page(
        PagePatch(
            kind=PageKind.ENTITY,
            slug="fulvio",
            op="create",
            title="Fulvio",
            body_md="Type: Person\nRole: Developer\nRelated: [[aria-scheduler]], [[kilo-code]]",
            source_kilo_msg_ids=["msg-5"],
        )
    )

    # Create decision
    await store.create_page(
        PagePatch(
            kind=PageKind.DECISION,
            slug="drop-episodic-db",
            op="create",
            title="Drop Episodic DB",
            body_md=(
                "## Context\n"
                "Both kilo.db and episodic.db capture conversations.\n"
                "## Decision\n"
                "Drop episodic.db, use kilo.db as single T0 source.\n"
                "## Rationale\n"
                "Reduces duplication and maintenance burden."
            ),
            source_kilo_msg_ids=["msg-6"],
        )
    )

    yield store
    await store.close()


class TestWikiRecallEngine:
    """WikiRecallEngine tests."""

    async def test_recall_by_keyword(self, populated_store: WikiStore) -> None:
        engine = WikiRecallEngine(populated_store)
        results = await engine.recall("memory system design", max_pages=5)

        assert len(results) > 0
        # Memory system topic should be in results
        slugs = [r.slug for r in results]
        assert "memory-system" in slugs

    async def test_recall_profile(self, populated_store: WikiStore) -> None:
        engine = WikiRecallEngine(populated_store)
        profile = await engine.get_profile()
        assert profile is not None
        assert profile.slug == "profile"
        assert "Fulvio" in profile.body_md

    async def test_recall_returns_scored_results(self, populated_store: WikiStore) -> None:
        engine = WikiRecallEngine(populated_store)
        results = await engine.recall("SQLite database tests")

        assert len(results) > 0
        for result in results:
            assert 0.0 <= result.score <= 1.0
            assert result.kind in PageKind
            assert result.slug
            assert result.title

    async def test_recall_min_score_filter(self, populated_store: WikiStore) -> None:
        engine = WikiRecallEngine(populated_store)
        # Very high min_score should filter most results
        results = await engine.recall("memory system", min_score=0.99)
        # May be 0 or very few results
        for result in results:
            assert result.score >= 0.99

    async def test_recall_max_pages(self, populated_store: WikiStore) -> None:
        engine = WikiRecallEngine(populated_store)
        results = await engine.recall("database system memory oauth", max_pages=2)
        assert len(results) <= 2

    async def test_recall_empty_query(self, populated_store: WikiStore) -> None:
        engine = WikiRecallEngine(populated_store)
        results = await engine.recall("")
        assert results == []

    async def test_recall_no_results(self, populated_store: WikiStore) -> None:
        engine = WikiRecallEngine(populated_store)
        results = await engine.recall("xyzzyfrobnicate12345")
        assert results == []

    async def test_recall_kind_filter(self, populated_store: WikiStore) -> None:
        engine = WikiRecallEngine(populated_store)
        results = await engine.recall("Fulvio", kind_filter=PageKind.ENTITY)
        for result in results:
            assert result.kind == PageKind.ENTITY

    async def test_recall_token_budget(self, populated_store: WikiStore) -> None:
        engine = WikiRecallEngine(populated_store)
        results = await engine.recall("database memory", max_tokens=50)
        total_tokens = sum(r.estimated_tokens for r in results)
        # Should be within budget (with some tolerance)
        assert total_tokens <= 100  # Allow some overshoot


class TestRecallResult:
    """RecallResult dataclass tests."""

    def test_estimated_tokens(self) -> None:
        result = RecallResult(
            kind=PageKind.TOPIC,
            slug="test",
            title="Test Topic",
            body_excerpt="Some content here",
            score=0.8,
        )
        assert result.estimated_tokens > 0

    def test_estimated_tokens_empty(self) -> None:
        result = RecallResult(
            kind=PageKind.TOPIC,
            slug="a",
            title="",
            body_excerpt="",
            score=0.5,
        )
        assert result.estimated_tokens >= 1
