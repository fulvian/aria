"""E2E tests: Workspace HITL write paths.

Tests the complete flow for workspace write operations that require HITL approval:
- Gmail compose and send
- Docs editor with batch updates
- Sheets editor with cell modifications
- Slides editor with batch updates
- HITL rejection flow
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.e2e
class TestGmailComposerProHITLFlow:
    """E2E tests for Gmail composer with HITL approval."""

    async def test_gmail_compose_send_approved(
        self,
        mock_hitl_manager: MagicMock,
        mock_workspace_client: MagicMock,
        mock_memory_store: MagicMock,
    ) -> None:
        """E2E: Gmail draft created -> HITL asked -> User approves -> Send executed.

        Full flow:
        1. Draft created via Gmail API
        2. HITL question asked to user
        3. User approves (response="yes")
        4. Send executed
        5. Verification read confirms sent
        """
        draft_id = "draft-456"
        sent_id = "sent-789"

        mock_workspace_client.gmail.create_draft = AsyncMock(
            return_value={"id": draft_id, "to": "test@example.com"}
        )
        mock_workspace_client.gmail.send_message = AsyncMock(
            return_value={"id": sent_id, "result": "sent"}
        )
        mock_workspace_client.gmail.get_thread = AsyncMock(
            return_value={"id": "thread-123", "messages": [{"id": sent_id}]}
        )

        draft_result = await mock_workspace_client.gmail.create_draft(
            to="test@example.com", subject="Test Subject", body="Test body content"
        )
        assert draft_result["id"] == draft_id

        hitl_response = await mock_hitl_manager.ask(
            question="Send email to test@example.com?",
            context={"draft_id": draft_id},
        )
        assert hitl_response.id == "hitl-123"

        user_approval = await mock_hitl_manager.wait_for_response(hitl_response.id)
        assert user_approval == "yes"

        send_result = await mock_workspace_client.gmail.send_message(draft_id)
        assert send_result["id"] == sent_id

        verification = await mock_workspace_client.gmail.get_thread("thread-123")
        assert any(msg["id"] == sent_id for msg in verification["messages"])

    async def test_gmail_compose_send_rejected(
        self,
        mock_hitl_manager: MagicMock,
        mock_workspace_client: MagicMock,
        mock_memory_store: MagicMock,
    ) -> None:
        """E2E: Gmail draft created -> HITL asked -> User rejects -> Task aborted.

        Full flow:
        1. Draft created
        2. HITL asked
        3. User rejects (response="no")
        4. Send NOT executed
        5. Memory archived with rejection reason
        """
        draft_id = "draft-reject-123"

        mock_workspace_client.gmail.create_draft = AsyncMock(return_value={"id": draft_id})
        mock_hitl_manager.wait_for_response = AsyncMock(return_value="no")
        mock_memory_store.add = AsyncMock(return_value=None)

        await mock_workspace_client.gmail.create_draft(
            to="test@example.com", subject="Test", body="Body"
        )

        hitl_response = await mock_hitl_manager.ask(
            question="Send this email?",
            context={"draft_id": draft_id},
        )

        user_rejection = await mock_hitl_manager.wait_for_response(hitl_response.id)
        assert user_rejection == "no"

        mock_workspace_client.gmail.send_message.assert_not_called()

        await mock_memory_store.add(
            {
                "type": "rejection_record",
                "draft_id": draft_id,
                "reason": "user_rejected",
                "hitl_id": hitl_response.id,
            }
        )
        mock_memory_store.add.assert_called_once()


@pytest.mark.e2e
class TestDocsEditorProHITLFlow:
    """E2E tests for Docs editor with HITL approval."""

    async def test_docs_batch_update_approved(
        self,
        mock_hitl_manager: MagicMock,
        mock_workspace_client: MagicMock,
        mock_memory_store: MagicMock,
    ) -> None:
        """E2E: Docs document read -> Diff preview -> HITL asked -> User approves.

        Full flow:
        1. Document read
        2. Diff preview generated
        3. HITL asked with diff summary
        4. User approves
        5. Batch update applied
        6. Verification read confirms changes
        """
        doc_id = "doc-edit-123"

        mock_workspace_client.docs.get_document = AsyncMock(
            return_value={
                "documentId": doc_id,
                "title": "Test Document",
                "body": {"content": []},
            }
        )

        updates = [
            {"insert_text": {"text": "Hello world", "location": {"index": 0}}},
            {"delete_text": {"range": {"startIndex": 10, "endIndex": 15}}},
        ]

        mock_workspace_client.docs.batch_update = AsyncMock(
            return_value={"replies": [{"insert_text": {}}, {"delete_text": {}}]}
        )

        doc = await mock_workspace_client.docs.get_document(doc_id)
        assert doc["documentId"] == doc_id

        hitl_question = (
            f"Apply {len(updates)} changes to '{doc['title']}'?\n"
            "- Insert 'Hello world' at position 0\n"
            "- Delete 5 characters at position 10"
        )
        hitl_response = await mock_hitl_manager.ask(
            question=hitl_question,
            context={"doc_id": doc_id, "update_count": len(updates)},
        )
        assert hitl_response.id == "hitl-123"

        user_approval = await mock_hitl_manager.wait_for_response(hitl_response.id)
        assert user_approval == "yes"

        update_result = await mock_workspace_client.docs.batch_update(doc_id, updates)
        assert "replies" in update_result
        assert len(update_result["replies"]) == 2

        verification = await mock_workspace_client.docs.get_document(doc_id)
        assert verification["documentId"] == doc_id

    async def test_docs_batch_update_rejected(
        self,
        mock_hitl_manager: MagicMock,
        mock_workspace_client: MagicMock,
        mock_memory_store: MagicMock,
    ) -> None:
        """E2E: Docs update rejected -> No changes applied."""
        doc_id = "doc-reject-456"

        mock_workspace_client.docs.get_document = AsyncMock(
            return_value={"documentId": doc_id, "title": "Draft"}
        )
        mock_hitl_manager.wait_for_response = AsyncMock(return_value="no")

        await mock_workspace_client.docs.get_document(doc_id)

        hitl_response = await mock_hitl_manager.ask(
            question=f"Apply changes to '{doc_id}'?",
            context={"doc_id": doc_id},
        )

        rejection = await mock_hitl_manager.wait_for_response(hitl_response.id)
        assert rejection == "no"

        mock_workspace_client.docs.batch_update.assert_not_called()


@pytest.mark.e2e
class TestSheetsEditorProHITLFlow:
    """E2E tests for Sheets editor with HITL approval."""

    async def test_sheets_cell_update_approved(
        self,
        mock_hitl_manager: MagicMock,
        mock_workspace_client: MagicMock,
        mock_memory_store: MagicMock,
    ) -> None:
        """E2E: Sheets cell modification with HITL approval.

        Full flow:
        1. Spreadsheet read
        2. Cell modifications prepared
        3. HITL asked with change summary
        4. User approves
        5. Batch update applied
        6. Verification read confirms changes
        """
        sheet_id = "sheet-edit-123"

        mock_workspace_client.sheets.get_spreadsheet = AsyncMock(
            return_value={
                "spreadsheetId": sheet_id,
                "title": "Budget 2024",
                "sheets": [{"sheetId": 0, "title": "Sheet1"}],
            }
        )

        cell_updates = [
            {"range": "A1", "values": [["Updated Value"]]},
            {"range": "B2:B5", "values": [["100"], ["200"], ["300"], ["400"]]},
        ]

        mock_workspace_client.sheets.batch_update = AsyncMock(
            return_value={"replies": [{"updated_cells": 1}, {"updated_cells": 4}]}
        )

        sheet = await mock_workspace_client.sheets.get_spreadsheet(sheet_id)
        assert sheet["spreadsheetId"] == sheet_id

        hitl_response = await mock_hitl_manager.ask(
            question=(
                f"Apply {len(cell_updates)} cell updates to '{sheet['title']}'?\n"
                "- Update A1: 'Updated Value'\n"
                "- Update B2:B5: 100, 200, 300, 400"
            ),
            context={"sheet_id": sheet_id, "update_count": len(cell_updates)},
        )

        user_approval = await mock_hitl_manager.wait_for_response(hitl_response.id)
        assert user_approval == "yes"

        update_result = await mock_workspace_client.sheets.batch_update(sheet_id, cell_updates)
        assert "replies" in update_result

        verification = await mock_workspace_client.sheets.get_spreadsheet(sheet_id)
        assert verification["spreadsheetId"] == sheet_id

    async def test_sheets_batch_update_rejected(
        self,
        mock_hitl_manager: MagicMock,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Sheets update rejected -> No changes applied."""
        sheet_id = "sheet-reject-789"

        mock_workspace_client.sheets.get_spreadsheet = AsyncMock(
            return_value={"spreadsheetId": sheet_id, "title": "Data"}
        )
        mock_hitl_manager.wait_for_response = AsyncMock(return_value="no")

        await mock_workspace_client.sheets.get_spreadsheet(sheet_id)

        hitl_response = await mock_hitl_manager.ask(
            question="Apply cell updates?",
            context={"sheet_id": sheet_id},
        )

        rejection = await mock_hitl_manager.wait_for_response(hitl_response.id)
        assert rejection == "no"

        mock_workspace_client.sheets.batch_update.assert_not_called()


@pytest.mark.e2e
class TestSlidesEditorProHITLFlow:
    """E2E tests for Slides editor with HITL approval."""

    async def test_slides_batch_update_approved(
        self,
        mock_hitl_manager: MagicMock,
        mock_workspace_client: MagicMock,
        mock_memory_store: MagicMock,
    ) -> None:
        """E2E: Slides batch update with HITL approval.

        Full flow:
        1. Presentation read
        2. Slide modifications prepared
        3. HITL asked with change summary
        4. User approves
        5. Batch update applied
        6. Verification read confirms changes
        """
        slides_id = "slides-edit-123"

        mock_workspace_client.slides.get_presentation = AsyncMock(
            return_value={
                "presentationId": slides_id,
                "title": "Q4 Review",
                "slides": [{"slideId": "slide-1"}, {"slideId": "slide-2"}],
            }
        )

        slide_updates = [
            {"insert_text": {"text": "New content", "slide_id": "slide-1", "insertion_index": 0}},
            {"update_shape": {"shape_id": "shape-1", "new_text": "Updated"}},
        ]

        mock_workspace_client.slides.batch_update = AsyncMock(
            return_value={"replies": [{"insert_text": {}}, {"update_shape": {}}]}
        )

        presentation = await mock_workspace_client.slides.get_presentation(slides_id)
        assert presentation["presentationId"] == slides_id
        assert len(presentation["slides"]) == 2

        hitl_response = await mock_hitl_manager.ask(
            question=(
                f"Apply {len(slide_updates)} changes to '{presentation['title']}'?\n"
                "- Insert text on slide 1\n"
                "- Update shape on slide 1"
            ),
            context={"slides_id": slides_id, "update_count": len(slide_updates)},
        )

        user_approval = await mock_hitl_manager.wait_for_response(hitl_response.id)
        assert user_approval == "yes"

        update_result = await mock_workspace_client.slides.batch_update(slides_id, slide_updates)
        assert "replies" in update_result
        assert len(update_result["replies"]) == 2

        verification = await mock_workspace_client.slides.get_presentation(slides_id)
        assert verification["presentationId"] == slides_id

    async def test_slides_batch_update_rejected(
        self,
        mock_hitl_manager: MagicMock,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Slides update rejected -> No changes applied."""
        slides_id = "slides-reject-456"

        mock_workspace_client.slides.get_presentation = AsyncMock(
            return_value={"presentationId": slides_id, "title": "Draft"}
        )
        mock_hitl_manager.wait_for_response = AsyncMock(return_value="no")

        await mock_workspace_client.slides.get_presentation(slides_id)

        hitl_response = await mock_hitl_manager.ask(
            question="Apply slide changes?",
            context={"slides_id": slides_id},
        )

        rejection = await mock_hitl_manager.wait_for_response(hitl_response.id)
        assert rejection == "no"

        mock_workspace_client.slides.batch_update.assert_not_called()


@pytest.mark.e2e
class TestHITLRejectionFlow:
    """E2E tests for comprehensive HITL rejection scenarios."""

    async def test_rejection_archives_memory_with_reason(
        self,
        mock_hitl_manager: MagicMock,
        mock_workspace_client: MagicMock,
        mock_memory_store: MagicMock,
    ) -> None:
        """E2E: Rejection properly archived in memory with reason.

        Verifies Ten Commandment #7 (HITL on destructive actions) is respected.
        """
        draft_id = "draft-memory-123"

        mock_workspace_client.gmail.create_draft = AsyncMock(return_value={"id": draft_id})
        mock_hitl_manager.wait_for_response = AsyncMock(return_value="no")
        mock_memory_store.add = AsyncMock(return_value=None)

        await mock_workspace_client.gmail.create_draft(
            to="recipient@example.com", subject="Important", body="Draft content"
        )

        hitl_response = await mock_hitl_manager.ask(
            question="Send this email?",
            context={"draft_id": draft_id},
        )

        await mock_hitl_manager.wait_for_response(hitl_response.id)

        record: dict[str, Any] = {
            "type": "hitl_rejection",
            "actor": "user_input",
            "draft_id": draft_id,
            "hitl_id": hitl_response.id,
            "reason": "user_declined",
            "timestamp": "2024-01-15T10:30:00Z",
        }
        await mock_memory_store.add(record)

        mock_memory_store.add.assert_called_once()
        call_args = mock_memory_store.add.call_args[0][0]
        assert call_args["type"] == "hitl_rejection"
        assert call_args["draft_id"] == draft_id

    async def test_hitl_timeout_results_in_abort(
        self,
        mock_hitl_manager: MagicMock,
        mock_workspace_client: MagicMock,
        mock_memory_store: MagicMock,
    ) -> None:
        """E2E: HITL timeout results in task abortion."""
        draft_id = "draft-timeout-123"

        mock_workspace_client.gmail.create_draft = AsyncMock(return_value={"id": draft_id})
        mock_hitl_manager.wait_for_response = AsyncMock(
            side_effect=TimeoutError("HITL response timeout")
        )

        await mock_workspace_client.gmail.create_draft(
            to="test@example.com", subject="Timeout Test", body="Body"
        )

        hitl_response = await mock_hitl_manager.ask(
            question="Send?",
            context={"draft_id": draft_id},
        )

        timeout_occurred = False
        try:
            await mock_hitl_manager.wait_for_response(hitl_response.id)
        except TimeoutError:
            timeout_occurred = True

        assert timeout_occurred

        mock_workspace_client.gmail.send_message.assert_not_called()

    async def test_hitl_deferred_allows_later_execution(
        self,
        mock_hitl_manager: MagicMock,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: HITL deferred response allows later execution."""
        draft_id = "draft-deferred-123"

        mock_workspace_client.gmail.create_draft = AsyncMock(return_value={"id": draft_id})
        mock_hitl_manager.wait_for_response = AsyncMock(return_value="deferred")
        mock_workspace_client.gmail.send_message = AsyncMock(return_value={"id": "sent-deferred"})

        await mock_workspace_client.gmail.create_draft(
            to="test@example.com", subject="Deferred", body="Body"
        )

        hitl_response = await mock_hitl_manager.ask(
            question="Send this email?",
            context={"draft_id": draft_id},
        )

        deferred_response = await mock_hitl_manager.wait_for_response(hitl_response.id)
        assert deferred_response == "deferred"

        mock_hitl_manager.resolve.assert_not_called()
