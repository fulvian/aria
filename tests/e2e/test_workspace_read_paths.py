"""E2E tests: Workspace read paths (no HITL required).

Tests the complete flow for workspace read operations that do not require HITL:
- Gmail thread intelligence
- Docs structure reader
- Sheets analytics reader
- Slides content auditor
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.e2e
class TestGmailThreadIntelligenceReadFlow:
    """E2E tests for Gmail thread intelligence (read-only)."""

    async def test_gmail_thread_read_returns_messages(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Gmail thread read returns all messages without HITL."""
        thread_id = "thread-read-123"

        mock_workspace_client.gmail.get_thread = AsyncMock(
            return_value={
                "id": thread_id,
                "messages": [
                    {
                        "id": "msg-1",
                        "from": "sender@example.com",
                        "to": "recipient@example.com",
                        "subject": "Test Thread",
                        "body": "First message",
                    },
                    {
                        "id": "msg-2",
                        "from": "recipient@example.com",
                        "to": "sender@example.com",
                        "subject": "Re: Test Thread",
                        "body": "Reply content",
                    },
                ],
                "message_count": 2,
            }
        )

        thread = await mock_workspace_client.gmail.get_thread(thread_id)

        assert thread["id"] == thread_id
        assert len(thread["messages"]) == 2
        assert thread["messages"][0]["id"] == "msg-1"
        assert thread["messages"][1]["id"] == "msg-2"

    async def test_gmail_thread_intelligence_analyzes_context(
        self,
        mock_workspace_client: MagicMock,
        mock_skill_executor: MagicMock,
    ) -> None:
        """E2E: Gmail thread intelligence provides context analysis."""
        thread_id = "thread-ai-456"

        mock_workspace_client.gmail.get_thread = AsyncMock(
            return_value={
                "id": thread_id,
                "messages": [
                    {"id": "msg-1", "body": "Meeting request for Monday"},
                    {"id": "msg-2", "body": "Confirmed for 2pm"},
                ],
            }
        )

        mock_skill_executor.execute_skill = AsyncMock(
            return_value={
                "status": "success",
                "output": {
                    "summary": "Meeting confirmed for Monday 2pm",
                    "action_items": ["Prepare agenda"],
                    "entities": ["Monday", "2pm"],
                },
            }
        )

        thread = await mock_workspace_client.gmail.get_thread(thread_id)

        skill_result = await mock_skill_executor.execute_skill(
            skill_name="gmail-thread-intelligence",
            input={"thread": thread},
        )

        assert skill_result["status"] == "success"
        assert "summary" in skill_result["output"]
        assert "action_items" in skill_result["output"]


@pytest.mark.e2e
class TestDocsStructureReaderReadFlow:
    """E2E tests for Docs structure reader (read-only)."""

    async def test_docs_read_returns_structure(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Docs document read returns full structure without HITL."""
        doc_id = "doc-read-123"

        mock_workspace_client.docs.get_document = AsyncMock(
            return_value={
                "documentId": doc_id,
                "title": "Test Document",
                "body": {
                    "content": [
                        {
                            "paragraph": {
                                "elements": [{"text_run": {"content": "Heading 1"}}],
                                "bullet": None,
                            },
                            "start_index": 0,
                            "end_index": 10,
                        },
                        {
                            "paragraph": {
                                "elements": [{"text_run": {"content": "Normal paragraph text"}}],
                                "bullet": None,
                            },
                            "start_index": 11,
                            "end_index": 35,
                        },
                    ]
                },
                "headers": {"1": {"content": "Header text"}},
                "footers": {},
            }
        )

        doc = await mock_workspace_client.docs.get_document(doc_id)

        assert doc["documentId"] == doc_id
        assert doc["title"] == "Test Document"
        assert len(doc["body"]["content"]) == 2
        assert "headers" in doc

    async def test_docs_structure_reader_extracts_outline(
        self,
        mock_workspace_client: MagicMock,
        mock_skill_executor: MagicMock,
    ) -> None:
        """E2E: Docs structure reader extracts outline structure."""
        doc_id = "doc-outline-456"

        mock_workspace_client.docs.get_document = AsyncMock(
            return_value={
                "documentId": doc_id,
                "title": "Project Plan",
                "body": {
                    "content": [
                        {
                            "paragraph": {
                                "elements": [{"text_run": {"content": "1. Introduction"}}],
                            },
                        },
                        {
                            "paragraph": {
                                "elements": [{"text_run": {"content": "1.1 Background"}}],
                            },
                        },
                        {
                            "paragraph": {
                                "elements": [{"text_run": {"content": "2. Methodology"}}],
                            },
                        },
                    ]
                },
            }
        )

        mock_skill_executor.execute_skill = AsyncMock(
            return_value={
                "status": "success",
                "output": {
                    "outline": [
                        {"level": 1, "text": "1. Introduction", "index": 0},
                        {"level": 2, "text": "1.1 Background", "index": 1},
                        {"level": 1, "text": "2. Methodology", "index": 2},
                    ],
                    "word_count": 15,
                },
            }
        )

        doc = await mock_workspace_client.docs.get_document(doc_id)

        skill_result = await mock_skill_executor.execute_skill(
            skill_name="docs-structure-reader",
            input={"document": doc},
        )

        assert skill_result["status"] == "success"
        assert len(skill_result["output"]["outline"]) == 3


@pytest.mark.e2e
class TestSheetsAnalyticsReaderReadFlow:
    """E2E tests for Sheets analytics reader (read-only)."""

    async def test_sheets_read_returns_data(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Sheets spreadsheet read returns data without HITL."""
        sheet_id = "sheet-read-123"

        mock_workspace_client.sheets.get_spreadsheet = AsyncMock(
            return_value={
                "spreadsheetId": sheet_id,
                "title": "Sales Data",
                "sheets": [
                    {
                        "sheetId": 0,
                        "title": "Q1 Sales",
                        "data": [
                            ["Product", "Q1 Sales", "Growth"],
                            ["Widget A", "10000", "15%"],
                            ["Widget B", "8500", "8%"],
                        ],
                    }
                ],
            }
        )

        sheet = await mock_workspace_client.sheets.get_spreadsheet(sheet_id)

        assert sheet["spreadsheetId"] == sheet_id
        assert sheet["title"] == "Sales Data"
        assert len(sheet["sheets"]) == 1
        assert sheet["sheets"][0]["title"] == "Q1 Sales"

    async def test_sheets_analytics_reader_computes_metrics(
        self,
        mock_workspace_client: MagicMock,
        mock_skill_executor: MagicMock,
    ) -> None:
        """E2E: Sheets analytics reader computes summary metrics."""
        sheet_id = "sheet-analytics-456"

        mock_workspace_client.sheets.get_spreadsheet = AsyncMock(
            return_value={
                "spreadsheetId": sheet_id,
                "title": "Revenue Report",
                "sheets": [
                    {
                        "data": [
                            ["Month", "Revenue", "Costs"],
                            ["Jan", "50000", "30000"],
                            ["Feb", "55000", "32000"],
                            ["Mar", "62000", "35000"],
                        ],
                    }
                ],
            }
        )

        mock_skill_executor.execute_skill = AsyncMock(
            return_value={
                "status": "success",
                "output": {
                    "total_revenue": 167000,
                    "total_costs": 97000,
                    "net_profit": 70000,
                    "avg_monthly_revenue": 55666.67,
                    "profit_margin": 0.42,
                },
            }
        )

        sheet = await mock_workspace_client.sheets.get_spreadsheet(sheet_id)

        skill_result = await mock_skill_executor.execute_skill(
            skill_name="sheets-analytics-reader",
            input={"spreadsheet": sheet},
        )

        assert skill_result["status"] == "success"
        assert skill_result["output"]["total_revenue"] == 167000
        assert "profit_margin" in skill_result["output"]


@pytest.mark.e2e
class TestSlidesContentAuditorReadFlow:
    """E2E tests for Slides content auditor (read-only)."""

    async def test_slides_read_returns_content(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Slides presentation read returns content without HITL."""
        slides_id = "slides-read-123"

        mock_workspace_client.slides.get_presentation = AsyncMock(
            return_value={
                "presentationId": slides_id,
                "title": "Quarterly Review",
                "slides": [
                    {
                        "slideId": "slide-1",
                        "title": "Overview",
                        "content": [
                            {"type": "text", "content": "Q4 Performance Summary"},
                            {"type": "image", "content": "chart.png"},
                        ],
                    },
                    {
                        "slideId": "slide-2",
                        "title": "Metrics",
                        "content": [
                            {"type": "text", "content": "Revenue: $2.5M"},
                            {"type": "text", "content": "Growth: 15%"},
                        ],
                    },
                ],
            }
        )

        presentation = await mock_workspace_client.slides.get_presentation(slides_id)

        assert presentation["presentationId"] == slides_id
        assert presentation["title"] == "Quarterly Review"
        assert len(presentation["slides"]) == 2
        assert presentation["slides"][0]["title"] == "Overview"

    async def test_slides_content_auditor_checks_accessibility(
        self,
        mock_workspace_client: MagicMock,
        mock_skill_executor: MagicMock,
    ) -> None:
        """E2E: Slides content auditor checks accessibility compliance."""
        slides_id = "slides-audit-456"

        mock_workspace_client.slides.get_presentation = AsyncMock(
            return_value={
                "presentationId": slides_id,
                "title": "Training Deck",
                "slides": [
                    {
                        "slideId": "slide-1",
                        "content": [
                            {"type": "text", "content": "Welcome to Training"},
                            {"type": "image", "alt_text": None},
                        ],
                    },
                    {
                        "slideId": "slide-2",
                        "content": [
                            {"type": "text", "content": "Step 1: Click button"},
                            {"type": "image", "alt_text": "Screenshot of button"},
                        ],
                    },
                ],
            }
        )

        mock_skill_executor.execute_skill = AsyncMock(
            return_value={
                "status": "success",
                "output": {
                    "total_slides": 2,
                    "issues": [
                        {
                            "slide": "slide-1",
                            "issue": "Missing alt text on image",
                            "severity": "warning",
                        }
                    ],
                    "score": 0.9,
                },
            }
        )

        presentation = await mock_workspace_client.slides.get_presentation(slides_id)

        skill_result = await mock_skill_executor.execute_skill(
            skill_name="slides-content-auditor",
            input={"presentation": presentation},
        )

        assert skill_result["status"] == "success"
        assert len(skill_result["output"]["issues"]) == 1
        assert skill_result["output"]["issues"][0]["slide"] == "slide-1"
