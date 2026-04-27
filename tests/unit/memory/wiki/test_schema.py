# Tests for wiki.schema — Pydantic models validation

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aria.memory.wiki.schema import (
    Page,
    PageKind,
    PagePatch,
    PageRevision,
    WikiUpdatePayload,
    validate_slug,
)


class TestValidateSlug:
    """Slug validation tests."""

    def test_valid_slug(self) -> None:
        assert validate_slug("memory-system") == "memory-system"

    def test_valid_single_word(self) -> None:
        assert validate_slug("profile") == "profile"

    def test_valid_with_numbers(self) -> None:
        assert validate_slug("oauth-fix-2") == "oauth-fix-2"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_slug("")

    def test_rejects_uppercase(self) -> None:
        with pytest.raises(ValueError, match="kebab-case"):
            validate_slug("Memory-System")

    def test_rejects_spaces(self) -> None:
        with pytest.raises(ValueError, match="kebab-case"):
            validate_slug("memory system")

    def test_rejects_leading_hyphen(self) -> None:
        with pytest.raises(ValueError, match="kebab-case"):
            validate_slug("-memory")

    def test_rejects_double_hyphen(self) -> None:
        with pytest.raises(ValueError, match="kebab-case"):
            validate_slug("memory--system")

    def test_rejects_special_chars(self) -> None:
        with pytest.raises(ValueError, match="kebab-case"):
            validate_slug("memory@system")


class TestPageKind:
    """PageKind enum tests."""

    def test_all_kinds(self) -> None:
        assert set(PageKind) == {
            PageKind.PROFILE,
            PageKind.TOPIC,
            PageKind.LESSON,
            PageKind.ENTITY,
            PageKind.DECISION,
        }

    def test_string_values(self) -> None:
        assert PageKind.PROFILE.value == "profile"
        assert PageKind.TOPIC.value == "topic"
        assert PageKind.LESSON.value == "lesson"
        assert PageKind.ENTITY.value == "entity"
        assert PageKind.DECISION.value == "decision"


class TestPagePatch:
    """PagePatch model tests."""

    def test_valid_create(self) -> None:
        patch = PagePatch(
            kind=PageKind.TOPIC,
            slug="memory-system",
            op="create",
            title="Memory System",
            body_md="## Overview\n...",
            confidence=0.9,
            source_kilo_msg_ids=["msg-1"],
            diff_summary="Created memory system topic",
        )
        assert patch.kind == PageKind.TOPIC
        assert patch.slug == "memory-system"
        assert patch.op == "create"
        assert patch.confidence == 0.9

    def test_valid_update(self) -> None:
        patch = PagePatch(
            kind=PageKind.PROFILE,
            slug="profile",
            op="update",
            body_md="New profile body",
        )
        assert patch.op == "update"

    def test_valid_append(self) -> None:
        patch = PagePatch(
            kind=PageKind.TOPIC,
            slug="oauth-fix",
            op="append",
            body_md="## New Section\nContent",
        )
        assert patch.op == "append"

    def test_invalid_slug_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PagePatch(
                kind=PageKind.TOPIC,
                slug="INVALID",
                op="create",
                title="Test",
                body_md="test",
            )

    def test_confidence_clamped(self) -> None:
        patch = PagePatch(
            kind=PageKind.TOPIC,
            slug="test",
            op="create",
            title="Test",
            body_md="test",
            confidence=1.5,
        )
        assert patch.confidence == 1.0

    def test_confidence_negative_clamped(self) -> None:
        patch = PagePatch(
            kind=PageKind.TOPIC,
            slug="test",
            op="create",
            title="Test",
            body_md="test",
            confidence=-0.5,
        )
        assert patch.confidence == 0.0

    def test_importance_default(self) -> None:
        patch = PagePatch(
            kind=PageKind.TOPIC,
            slug="test",
            op="create",
            title="Test",
            body_md="test",
        )
        assert patch.importance == "med"

    def test_default_msg_ids(self) -> None:
        patch = PagePatch(
            kind=PageKind.TOPIC,
            slug="test",
            op="create",
            title="Test",
            body_md="test",
        )
        assert patch.source_kilo_msg_ids == []


class TestWikiUpdatePayload:
    """WikiUpdatePayload model tests."""

    def test_empty_patches_with_reason(self) -> None:
        payload = WikiUpdatePayload(
            patches=[],
            no_salience_reason="casual ack",
            kilo_session_id="sess-1",
            last_msg_id="msg-1",
        )
        assert len(payload.patches) == 0
        assert payload.no_salience_reason == "casual ack"

    def test_with_patches(self) -> None:
        payload = WikiUpdatePayload(
            patches=[
                PagePatch(
                    kind=PageKind.TOPIC,
                    slug="test",
                    op="create",
                    title="Test",
                    body_md="test",
                ),
            ],
        )
        assert len(payload.patches) == 1

    def test_default_fields(self) -> None:
        payload = WikiUpdatePayload()
        assert payload.patches == []
        assert payload.kilo_session_id == ""


class TestPage:
    """Page model tests."""

    def test_valid_page(self) -> None:
        page = Page(
            slug="profile",
            kind=PageKind.PROFILE,
            title="User Profile",
            body_md="Identity: Fulvio\nPreferences: ...",
        )
        assert page.slug == "profile"
        assert page.kind == PageKind.PROFILE
        assert page.occurrences == 1
        assert page.confidence == 1.0

    def test_invalid_slug_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Page(
                slug="INVALID SLUG",
                kind=PageKind.PROFILE,
                title="Test",
                body_md="test",
            )

    def test_auto_generated_fields(self) -> None:
        page = Page(
            slug="test",
            kind=PageKind.TOPIC,
            title="Test",
            body_md="test",
        )
        assert page.id  # UUID generated
        assert page.first_seen > 0
        assert page.last_seen > 0


class TestPageRevision:
    """PageRevision model tests."""

    def test_valid_revision(self) -> None:
        rev = PageRevision(
            page_id="page-1",
            body_md_before="old content",
            body_md_after="new content",
            diff_summary="Updated preferences",
            source_kilo_msg_ids=["msg-1"],
        )
        assert rev.body_md_before == "old content"
        assert rev.body_md_after == "new content"
        assert rev.ts > 0

    def test_creation_revision_no_before(self) -> None:
        rev = PageRevision(
            page_id="page-1",
            body_md_after="initial content",
            source_kilo_msg_ids=["msg-1"],
        )
        assert rev.body_md_before is None
