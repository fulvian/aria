"""Pytest fixtures for workspace skill integration tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_mcp_tools():
    """Mock MCP tools for workspace operations."""
    tools = {
        "google_workspace_search_gmail_messages": AsyncMock(
            return_value={
                "messages": [
                    {
                        "id": "msg001",
                        "thread_id": "thread123",
                        "subject": "Project Update",
                        "from": "alice@example.com",
                        "to": "bob@example.com",
                        "timestamp": "2026-04-22T10:00:00Z",
                        "snippet": "Here's the latest update...",
                    }
                ]
            }
        ),
        "google_workspace_get_gmail_message_content": AsyncMock(
            return_value={
                "id": "msg001",
                "thread_id": "thread123",
                "subject": "Project Update",
                "from": "alice@example.com",
                "to": "bob@example.com",
                "cc": "",
                "bcc": "",
                "timestamp": "2026-04-22T10:00:00Z",
                "body": "Here's the latest update on the project.",
                "attachments": [
                    {
                        "filename": "report.pdf",
                        "size_bytes": 102400,
                        "mime_type": "application/pdf",
                    }
                ],
            }
        ),
        "google_workspace_search_docs": AsyncMock(
            return_value={
                "documents": [
                    {
                        "document_id": "doc123",
                        "title": "Q1 Report",
                        "created_time": "2026-01-15T09:00:00Z",
                        "modified_time": "2026-04-20T14:30:00Z",
                    }
                ]
            }
        ),
        "google_workspace_get_doc_content": AsyncMock(
            return_value={
                "document_id": "doc123",
                "title": "Q1 Report",
                "content": "# Q1 Report\n\n## Overview\n\nThis is the quarterly report content.\n\n## Data\n\n| Column A | Column B |\n|----------|----------|\n| Value 1  | Value 2  |",
                "headings": [
                    {"level": 1, "text": "Q1 Report", "position": "0"},
                    {"level": 2, "text": "Overview", "position": "1"},
                    {"level": 2, "text": "Data", "position": "2"},
                ],
                "tables": [
                    {
                        "position": "A1:B3",
                        "rows": 3,
                        "columns": 2,
                        "content_summary": "Two-column table with headers",
                    }
                ],
            }
        ),
        "google_workspace_list_docs_in_folder": AsyncMock(
            return_value={
                "documents": [
                    {"document_id": "doc456", "title": "Meeting Notes"},
                ]
            }
        ),
        "google_workspace_read_doc_comments": AsyncMock(
            return_value={
                "comments": [
                    {
                        "comment_id": "c001",
                        "author": "alice@example.com",
                        "timestamp": "2026-04-21T11:00:00Z",
                        "content": "Please review this section.",
                        "resolved": False,
                        "position": "paragraph-1",
                    }
                ]
            }
        ),
        "google_workspace_list_spreadsheets": AsyncMock(
            return_value={
                "spreadsheets": [
                    {
                        "spreadsheet_id": "ss001",
                        "title": "Sales Data 2026",
                        "sheets": ["Q1", "Q2", "Q3", "Q4"],
                    }
                ]
            }
        ),
        "google_workspace_get_spreadsheet_info": AsyncMock(
            return_value={
                "spreadsheet_id": "ss001",
                "title": "Sales Data 2026",
                "sheets": [
                    {"name": "Q1", "grid_properties": {"row_count": 100, "column_count": 10}},
                    {"name": "Q2", "grid_properties": {"row_count": 100, "column_count": 10}},
                ],
                "named_ranges": [],
            }
        ),
        "google_workspace_read_sheet_values": AsyncMock(
            return_value={
                "range": "Sheet1!A1:Z100",
                "major_dimension": "ROWS",
                "values": [
                    ["Product", "Revenue", "Cost"],
                    ["Widget A", "50000", "30000"],
                    ["Widget B", "75000", "45000"],
                    ["", "", ""],
                    ["Widget C", "60000", "36000"],
                ],
            }
        ),
        "google_workspace_read_sheet_comments": AsyncMock(
            return_value={
                "comments": [
                    {
                        "cell": "A1",
                        "content": "Review needed",
                        "author": "manager@example.com",
                        "resolved": False,
                    }
                ]
            }
        ),
        "google_workspace_get_presentation": AsyncMock(
            return_value={
                "presentation_id": "pres001",
                "title": "Annual Review 2026",
                "slides": [
                    {
                        "slide_id": "slide1",
                        "layout": "title",
                        "position": {"index": 0},
                    },
                    {
                        "slide_id": "slide2",
                        "layout": "title_and_content",
                        "position": {"index": 1},
                    },
                    {
                        "slide_id": "slide3",
                        "layout": "blank",
                        "position": {"index": 2},
                    },
                ],
            }
        ),
        "google_workspace_get_page": AsyncMock(
            return_value={
                "slide_id": "slide1",
                "title": "Annual Review",
                "layout": "title",
                "elements": [
                    {"type": "title", "text": "Annual Review 2026"},
                    {"type": "body", "text": "Overview of company performance"},
                ],
                "text_element_count": 2,
                "character_count": 45,
            }
        ),
        "google_workspace_get_page_thumbnail": AsyncMock(
            return_value={
                "thumbnail_url": "https://example.com/thumb/slide1.png",
                "height": 720,
                "width": 1280,
            }
        ),
        "google_workspace_read_presentation_comments": AsyncMock(
            return_value={
                "comments": [
                    {
                        "comment_id": "pc001",
                        "author": "reviewer@example.com",
                        "timestamp": "2026-04-20T15:00:00Z",
                        "content": "Please add more details.",
                        "resolved": False,
                    }
                ]
            }
        ),
        "google_workspace_draft_gmail_message": AsyncMock(
            return_value={
                "draft_id": "draft123",
                "message": {
                    "to": ["bob@example.com"],
                    "subject": "Re: Project Update",
                    "body": "Thank you for the update.",
                },
            }
        ),
        "google_workspace_send_gmail_message": AsyncMock(
            return_value={
                "message_id": "sent001",
                "timestamp": "2026-04-22T18:59:00Z",
                "status": "sent",
            }
        ),
    }
    return tools


@pytest.fixture
def mock_memory_tools():
    """Mock memory tools for HITL."""
    return {
        "aria_memory_remember": AsyncMock(return_value=True),
        "aria_memory_recall": AsyncMock(return_value=[]),
        "aria_memory_hitl_ask": AsyncMock(return_value={"action": "accept", "response": "yes"}),
    }


@pytest.fixture
def trace_id():
    """Generate trace ID for test."""
    return "test-trace-id-12345"


@pytest.fixture
def mock_config():
    """Mock config for workspace tests."""
    config = MagicMock()
    config.timezone = "Europe/Rome"
    config.quiet_hours_start = "22:00"
    config.quiet_hours_end = "07:00"
    return config
