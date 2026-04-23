"""E2E fixtures for workspace tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_conductor() -> MagicMock:
    """Mock conductor for workspace routing."""
    conductor = MagicMock()
    conductor.route_workspace_task = AsyncMock(return_value={"status": "executed"})
    return conductor


@pytest.fixture
def mock_hitl_manager() -> MagicMock:
    """Mock HITL manager for write approval."""
    hitl = MagicMock()
    hitl.ask = AsyncMock(return_value=MagicMock(id="hitl-123"))
    hitl.wait_for_response = AsyncMock(return_value="yes")
    hitl.resolve = AsyncMock(return_value=None)
    return hitl


@pytest.fixture
def mock_skill_executor() -> MagicMock:
    """Mock skill executor."""
    executor = MagicMock()
    executor.execute_skill = AsyncMock(return_value={"status": "success", "output": {}})
    return executor


@pytest.fixture
def mock_workspace_client() -> MagicMock:
    """Mock workspace API client (Gmail, Docs, Sheets, Slides)."""
    client = MagicMock()
    client.gmail = MagicMock()
    client.gmail.send_message = AsyncMock(return_value={"id": "msg-123"})
    client.gmail.create_draft = AsyncMock(return_value={"id": "draft-123"})
    client.gmail.get_thread = AsyncMock(return_value={"id": "thread-123", "messages": []})

    client.docs = MagicMock()
    client.docs.get_document = AsyncMock(return_value={"documentId": "doc-123"})
    client.docs.batch_update = AsyncMock(return_value={"replies": []})

    client.sheets = MagicMock()
    client.sheets.get_spreadsheet = AsyncMock(return_value={"spreadsheetId": "sheet-123"})
    client.sheets.batch_update = AsyncMock(return_value={"replies": []})

    client.slides = MagicMock()
    client.slides.get_presentation = AsyncMock(return_value={"presentationId": "slides-123"})
    client.slides.batch_update = AsyncMock(return_value={"replies": []})

    return client


@pytest.fixture
def mock_memory_store() -> MagicMock:
    """Mock memory store for archiving."""
    store = MagicMock()
    store.add = AsyncMock(return_value=None)
    store.query = AsyncMock(return_value=[])
    return store


@pytest.fixture
def workspace_context() -> dict[str, Any]:
    """Standard workspace execution context."""
    return {
        "actor": "user_input",
        "session_id": "test-session-123",
        "trace_id": "trace-abc",
        "skill_name": "test-skill",
    }
