# Tests for wiki.db — WikiStore CRUD operations

from __future__ import annotations

from typing import Any

import pytest

from aria.memory.wiki.db import WikiStore, slugify
from aria.memory.wiki.schema import PageKind, PagePatch


@pytest.fixture
async def store(tmp_path: Any) -> WikiStore:
    """Create a WikiStore with a temporary database."""
    db_path = tmp_path / "wiki.db"
    s = WikiStore(db_path)
    await s.connect()
    yield s
    await s.close()


class TestSlugify:
    """slugify() tests."""

    def test_simple(self) -> None:
        assert slugify("Memory System") == "memory-system"

    def test_with_apostrophe(self) -> None:
        # Apostrophe is replaced by hyphen, producing "don-t"
        assert slugify("Don't Mock DB") == "don-t-mock-db"

    def test_uppercase(self) -> None:
        assert slugify("OAuth Fix") == "oauth-fix"

    def test_multiple_spaces(self) -> None:
        assert slugify("  multiple   spaces  ") == "multiple-spaces"

    def test_special_chars(self) -> None:
        assert slugify("Hello @World!") == "hello-world"

    def test_already_kebab(self) -> None:
        assert slugify("already-kebab") == "already-kebab"


class TestWikiStoreConnect:
    """WikiStore connection tests."""

    async def test_creates_db_file(self, tmp_path: Any) -> None:
        db_path = tmp_path / "test.db"
        store = WikiStore(db_path)
        await store.connect()
        assert db_path.exists()
        await store.close()

    async def test_creates_parent_dirs(self, tmp_path: Any) -> None:
        db_path = tmp_path / "nested" / "dir" / "wiki.db"
        store = WikiStore(db_path)
        await store.connect()
        assert db_path.exists()
        await store.close()

    async def test_idempotent_connect(self, tmp_path: Any) -> None:
        db_path = tmp_path / "wiki.db"
        store = WikiStore(db_path)
        await store.connect()
        await store.connect()  # Should not raise
        await store.close()


class TestWikiStoreCreatePage:
    """WikiStore.create_page tests."""

    async def test_create_profile(self, store: WikiStore) -> None:
        patch = PagePatch(
            kind=PageKind.PROFILE,
            slug="profile",
            op="create",
            title="User Profile",
            body_md="Identity: Fulvio\nWorking Style: prefers detailed explanations",
            confidence=0.9,
            source_kilo_msg_ids=["msg-1"],
            diff_summary="Initial profile",
        )
        page = await store.create_page(patch)

        assert page.slug == "profile"
        assert page.kind == PageKind.PROFILE
        assert page.title == "User Profile"
        assert page.occurrences == 1

    async def test_create_topic(self, store: WikiStore) -> None:
        patch = PagePatch(
            kind=PageKind.TOPIC,
            slug="memory-system",
            op="create",
            title="Memory System Design",
            body_md="## Overview\nThe memory system uses...",
            source_kilo_msg_ids=["msg-2"],
        )
        page = await store.create_page(patch)
        assert page.slug == "memory-system"
        assert page.kind == PageKind.TOPIC

    async def test_create_lesson(self, store: WikiStore) -> None:
        patch = PagePatch(
            kind=PageKind.LESSON,
            slug="dont-mock-db",
            op="create",
            title="Don't Mock the Database",
            body_md="## Rule\nAlways use real DB in integration tests",
            source_kilo_msg_ids=["msg-3"],
        )
        page = await store.create_page(patch)
        assert page.kind == PageKind.LESSON

    async def test_create_entity(self, store: WikiStore) -> None:
        patch = PagePatch(
            kind=PageKind.ENTITY,
            slug="fulvio",
            op="create",
            title="Fulvio",
            body_md="Type: Person\nRole: Developer",
            source_kilo_msg_ids=["msg-4"],
        )
        page = await store.create_page(patch)
        assert page.kind == PageKind.ENTITY

    async def test_create_decision(self, store: WikiStore) -> None:
        patch = PagePatch(
            kind=PageKind.DECISION,
            slug="drop-episodic-db",
            op="create",
            title="Drop Episodic DB",
            body_md="## Decision\nDrop episodic.db in favor of kilo.db",
            source_kilo_msg_ids=["msg-5"],
        )
        page = await store.create_page(patch)
        assert page.kind == PageKind.DECISION

    async def test_duplicate_rejected(self, store: WikiStore) -> None:
        patch = PagePatch(
            kind=PageKind.TOPIC,
            slug="test-topic",
            op="create",
            title="Test Topic",
            body_md="content",
        )
        await store.create_page(patch)
        with pytest.raises(RuntimeError, match="already exists"):
            await store.create_page(patch)

    async def test_create_without_title_raises(self, store: WikiStore) -> None:
        patch = PagePatch(
            kind=PageKind.TOPIC,
            slug="test",
            op="create",
            title=None,
            body_md="content",
        )
        with pytest.raises(ValueError, match="title is required"):
            await store.create_page(patch)

    async def test_all_five_kinds(self, store: WikiStore) -> None:
        """Verify all 5 kinds can coexist."""
        for kind in PageKind:
            patch = PagePatch(
                kind=kind,
                slug=f"test-{kind.value}",
                op="create",
                title=f"Test {kind.value}",
                body_md=f"Content for {kind.value}",
            )
            page = await store.create_page(patch)
            assert page.kind == kind

        pages = await store.list_pages()
        assert len(pages) == 5


class TestWikiStoreUpdatePage:
    """WikiStore.update_page tests."""

    async def test_update_body(self, store: WikiStore) -> None:
        # Create
        await store.create_page(
            PagePatch(
                kind=PageKind.PROFILE,
                slug="profile",
                op="create",
                title="Profile",
                body_md="Old body",
            )
        )
        # Update
        updated = await store.update_page(
            PagePatch(
                kind=PageKind.PROFILE,
                slug="profile",
                op="update",
                body_md="New body",
            )
        )
        assert updated.body_md == "New body"
        assert updated.occurrences == 2

    async def test_update_title(self, store: WikiStore) -> None:
        await store.create_page(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="test",
                op="create",
                title="Old Title",
                body_md="body",
            )
        )
        updated = await store.update_page(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="test",
                op="update",
                title="New Title",
                body_md="body",
            )
        )
        assert updated.title == "New Title"

    async def test_update_nonexistent_raises(self, store: WikiStore) -> None:
        with pytest.raises(LookupError, match="not found"):
            await store.update_page(
                PagePatch(
                    kind=PageKind.TOPIC,
                    slug="nonexistent",
                    op="update",
                    body_md="body",
                )
            )

    async def test_update_decision_immutable(self, store: WikiStore) -> None:
        await store.create_page(
            PagePatch(
                kind=PageKind.DECISION,
                slug="test-decision",
                op="create",
                title="Decision",
                body_md="Original decision",
            )
        )
        with pytest.raises(ValueError, match="immutable"):
            await store.update_page(
                PagePatch(
                    kind=PageKind.DECISION,
                    slug="test-decision",
                    op="update",
                    body_md="Modified decision",
                )
            )


class TestWikiStoreAppendPage:
    """WikiStore.append_page tests."""

    async def test_append_content(self, store: WikiStore) -> None:
        await store.create_page(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="test",
                op="create",
                title="Test",
                body_md="Initial content",
            )
        )
        updated = await store.append_page(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="test",
                op="append",
                body_md="## New Section\nAppended content",
            )
        )
        assert "Initial content" in updated.body_md
        assert "Appended content" in updated.body_md
        assert updated.occurrences == 2

    async def test_append_nonexistent_raises(self, store: WikiStore) -> None:
        with pytest.raises(LookupError, match="not found"):
            await store.append_page(
                PagePatch(
                    kind=PageKind.TOPIC,
                    slug="nonexistent",
                    op="append",
                    body_md="content",
                )
            )

    async def test_append_decision_immutable(self, store: WikiStore) -> None:
        await store.create_page(
            PagePatch(
                kind=PageKind.DECISION,
                slug="test-decision",
                op="create",
                title="Decision",
                body_md="Original",
            )
        )
        with pytest.raises(ValueError, match="immutable"):
            await store.append_page(
                PagePatch(
                    kind=PageKind.DECISION,
                    slug="test-decision",
                    op="append",
                    body_md="Extra",
                )
            )


class TestWikiStoreGetPage:
    """WikiStore.get_page tests."""

    async def test_get_existing(self, store: WikiStore) -> None:
        await store.create_page(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="test-topic",
                op="create",
                title="Test Topic",
                body_md="Content",
            )
        )
        page = await store.get_page(PageKind.TOPIC, "test-topic")
        assert page is not None
        assert page.title == "Test Topic"

    async def test_get_nonexistent(self, store: WikiStore) -> None:
        page = await store.get_page(PageKind.TOPIC, "nonexistent")
        assert page is None

    async def test_get_by_id(self, store: WikiStore) -> None:
        created = await store.create_page(
            PagePatch(
                kind=PageKind.ENTITY,
                slug="test-entity",
                op="create",
                title="Test Entity",
                body_md="Content",
            )
        )
        page = await store.get_page_by_id(created.id)
        assert page is not None
        assert page.slug == "test-entity"

    async def test_get_by_id_nonexistent(self, store: WikiStore) -> None:
        page = await store.get_page_by_id("nonexistent-id")
        assert page is None


class TestWikiStoreListPages:
    """WikiStore.list_pages tests."""

    async def test_list_all(self, store: WikiStore) -> None:
        for kind in PageKind:
            await store.create_page(
                PagePatch(
                    kind=kind,
                    slug=f"list-test-{kind.value}",
                    op="create",
                    title=f"Test {kind.value}",
                    body_md=f"Content for {kind.value}",
                )
            )

        pages = await store.list_pages()
        assert len(pages) == 5

    async def test_list_by_kind(self, store: WikiStore) -> None:
        for i in range(3):
            await store.create_page(
                PagePatch(
                    kind=PageKind.TOPIC,
                    slug=f"topic-{i}",
                    op="create",
                    title=f"Topic {i}",
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

        topics = await store.list_pages(kind=PageKind.TOPIC)
        assert len(topics) == 3
        assert all(p.kind == PageKind.TOPIC for p in topics)

        lessons = await store.list_pages(kind=PageKind.LESSON)
        assert len(lessons) == 1

    async def test_list_with_limit(self, store: WikiStore) -> None:
        for i in range(10):
            await store.create_page(
                PagePatch(
                    kind=PageKind.TOPIC,
                    slug=f"limit-test-{i}",
                    op="create",
                    title=f"Topic {i}",
                    body_md="content",
                )
            )

        pages = await store.list_pages(limit=3)
        assert len(pages) == 3


class TestWikiStoreApplyPatch:
    """WikiStore.apply_patch tests."""

    async def test_create_via_apply(self, store: WikiStore) -> None:
        page = await store.apply_patch(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="apply-test",
                op="create",
                title="Apply Test",
                body_md="content",
            )
        )
        assert page.slug == "apply-test"

    async def test_update_via_apply(self, store: WikiStore) -> None:
        await store.apply_patch(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="apply-test",
                op="create",
                title="Apply Test",
                body_md="initial",
            )
        )
        updated = await store.apply_patch(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="apply-test",
                op="update",
                body_md="updated",
            )
        )
        assert updated.body_md == "updated"

    async def test_append_via_apply(self, store: WikiStore) -> None:
        await store.apply_patch(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="apply-test",
                op="create",
                title="Apply Test",
                body_md="initial",
            )
        )
        updated = await store.apply_patch(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="apply-test",
                op="append",
                body_md="appended",
            )
        )
        assert "initial" in updated.body_md
        assert "appended" in updated.body_md

    async def test_invalid_op_raises(self, store: WikiStore) -> None:
        with pytest.raises(Exception):  # ValidationError from Pydantic
            await store.apply_patch(
                PagePatch(
                    kind=PageKind.TOPIC,
                    slug="test",
                    op="delete",  # type: ignore[typeddict-item]
                    body_md="content",
                )
            )


class TestWikiStoreTombstone:
    """WikiStore tombstone tests (P7 HITL)."""

    async def test_tombstone_page(self, store: WikiStore) -> None:
        page = await store.create_page(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="to-delete",
                op="create",
                title="To Delete",
                body_md="content",
            )
        )

        result = await store.tombstone_page(page.id, "user requested deletion")
        assert result is True

        # Page should be gone
        deleted = await store.get_page(PageKind.TOPIC, "to-delete")
        assert deleted is None

        # But tombstoned
        assert await store.is_tombstoned(page.id)

    async def test_tombstone_nonexistent(self, store: WikiStore) -> None:
        result = await store.tombstone_page("nonexistent-id", "reason")
        assert result is False


class TestWikiStoreWatermark:
    """WikiStore watermark tests (Phase B infrastructure)."""

    async def test_set_and_get_watermark(self, store: WikiStore) -> None:
        await store.set_watermark("session-1", "msg-100", 1000)
        wm = await store.get_watermark("session-1")
        assert wm is not None
        assert wm["last_seen_msg_id"] == "msg-100"
        assert wm["last_seen_ts"] == 1000

    async def test_get_nonexistent_watermark(self, store: WikiStore) -> None:
        wm = await store.get_watermark("nonexistent-session")
        assert wm is None

    async def test_update_watermark(self, store: WikiStore) -> None:
        await store.set_watermark("session-1", "msg-1", 100)
        await store.set_watermark("session-1", "msg-2", 200)

        wm = await store.get_watermark("session-1")
        assert wm is not None
        assert wm["last_seen_msg_id"] == "msg-2"
        assert wm["last_seen_ts"] == 200


class TestWikiStoreStats:
    """WikiStore.stats tests."""

    async def test_empty_stats(self, store: WikiStore) -> None:
        stats = await store.stats()
        assert stats["total_pages"] == 0
        assert stats["total_revisions"] == 0
        assert stats["total_tombstones"] == 0

    async def test_stats_after_operations(self, store: WikiStore) -> None:
        await store.create_page(
            PagePatch(
                kind=PageKind.PROFILE,
                slug="profile",
                op="create",
                title="Profile",
                body_md="content",
            )
        )
        await store.create_page(
            PagePatch(
                kind=PageKind.TOPIC,
                slug="topic-1",
                op="create",
                title="Topic 1",
                body_md="content",
            )
        )

        stats = await store.stats()
        assert stats["total_pages"] == 2
        assert stats["total_revisions"] == 2  # One revision per create
        assert stats["kind_counts"]["profile"] == 1
        assert stats["kind_counts"]["topic"] == 1
