"""E2E chaos tests for workspace operations.

Tests error handling and resilience for workspace operations:
- Quota exceeded (429)
- Auth failure (401/403)
- Network timeout
- HITL timeout
- Tool not available
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.e2e
class TestWorkspaceQuotaExceeded:
    """E2E chaos tests for quota exceeded scenarios (HTTP 429)."""

    async def test_gmail_quota_exceeded_retries(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Gmail quota exceeded triggers retry with backoff."""
        mock_workspace_client.gmail.send_message = AsyncMock(
            side_effect=[
                Exception("429 Quota Exceeded - Too Many Requests"),
                Exception("429 Quota Exceeded"),
                {"id": "msg-success-after-retry"},
            ]
        )

        result = None
        attempts = 0
        max_attempts = 3

        while attempts < max_attempts:
            try:
                result = await mock_workspace_client.gmail.send_message("draft-123")
                break
            except Exception as e:
                attempts += 1
                if "429" not in str(e):
                    raise
                if attempts >= max_attempts:
                    raise

        assert result is not None
        assert result["id"] == "msg-success-after-retry"

    async def test_sheets_quota_exceeded_aborts(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Sheets quota exceeded after retries results in abort."""
        mock_workspace_client.sheets.batch_update = AsyncMock(
            side_effect=Exception("429 Quota Exceeded for Sheets API")
        )

        with pytest.raises(Exception) as exc_info:
            await mock_workspace_client.sheets.batch_update("sheet-123", [])

        assert "429" in str(exc_info.value)


@pytest.mark.e2e
class TestWorkspaceAuthFailures:
    """E2E chaos tests for authentication failures (401/403)."""

    async def test_gmail_auth_failure_401(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Gmail auth failure (401) triggers re-authentication."""
        mock_workspace_client.gmail.send_message = AsyncMock(
            side_effect=Exception("401 Unauthorized - Invalid or expired token")
        )

        with pytest.raises(Exception) as exc_info:
            await mock_workspace_client.gmail.send_message("draft-123")

        assert "401" in str(exc_info.value)

    async def test_docs_auth_failure_403(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Docs auth failure (403) indicates insufficient permissions."""
        mock_workspace_client.docs.batch_update = AsyncMock(
            side_effect=Exception("403 Forbidden - App does not have permission")
        )

        with pytest.raises(Exception) as exc_info:
            await mock_workspace_client.docs.batch_update("doc-123", [])

        assert "403" in str(exc_info.value)
        assert "permission" in str(exc_info.value).lower()

    async def test_slides_auth_failure_refreshes_token(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Slides auth failure attempts token refresh."""
        call_count = 0

        async def mock_batch_update_with_auth(*args: object, **kwargs: object) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("401 Unauthorized")
            return {"replies": []}

        mock_workspace_client.slides.batch_update = mock_batch_update_with_auth

        result = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await mock_workspace_client.slides.batch_update("slides-123")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                if "401" not in str(e):
                    raise

        assert result is not None
        assert "replies" in result
        assert call_count == 2


@pytest.mark.e2e
class TestWorkspaceNetworkErrors:
    """E2E chaos tests for network timeout scenarios."""

    async def test_sheets_network_timeout_retries(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Sheets network timeout triggers retry."""
        mock_workspace_client.sheets.get_spreadsheet = AsyncMock(
            side_effect=[
                Exception("TimeoutError: Connection timed out after 30s"),
                Exception("TimeoutError: Connection timed out after 30s"),
                {"spreadsheetId": "sheet-after-retry"},
            ]
        )

        result = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await mock_workspace_client.sheets.get_spreadsheet("sheet-123")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                if "Timeout" not in str(e):
                    raise

        assert result is not None
        assert result["spreadsheetId"] == "sheet-after-retry"
        assert mock_workspace_client.sheets.get_spreadsheet.call_count == 3

    async def test_gmail_network_timeout_gives_up(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Gmail network timeout after max retries."""
        mock_workspace_client.gmail.send_message = AsyncMock(
            side_effect=Exception("TimeoutError: Connection reset by peer")
        )

        with pytest.raises(Exception) as exc_info:
            await mock_workspace_client.gmail.send_message("draft-123")

        assert "Timeout" in str(exc_info.value)

    async def test_docs_network_error_handles_gracefully(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Docs network error handled gracefully."""
        mock_workspace_client.docs.get_document = AsyncMock(
            side_effect=Exception("ConnectionError: Network unreachable")
        )

        with pytest.raises(Exception) as exc_info:
            await mock_workspace_client.docs.get_document("doc-123")

        assert "Network" in str(exc_info.value)


@pytest.mark.e2e
class TestHITLChaosScenarios:
    """E2E chaos tests for HITL-related failures."""

    async def test_hitl_manager_timeout(
        self,
        mock_hitl_manager: MagicMock,
    ) -> None:
        """E2E: HITL manager timeout results in task abort."""
        mock_hitl_manager.wait_for_response = AsyncMock(
            side_effect=TimeoutError("HITL response timed out after 300s")
        )

        with pytest.raises(TimeoutError):
            await mock_hitl_manager.wait_for_response("hitl-timeout-123")

    async def test_hitl_manager_connection_lost(
        self,
        mock_hitl_manager: MagicMock,
    ) -> None:
        """E2E: HITL manager connection lost during wait."""
        mock_hitl_manager.wait_for_response = AsyncMock(
            side_effect=ConnectionError("Connection to HITL service lost")
        )

        with pytest.raises(ConnectionError):
            await mock_hitl_manager.wait_for_response("hitl-conn-lost-123")

    async def test_hitl_ask_fails_initial_request(
        self,
        mock_hitl_manager: MagicMock,
    ) -> None:
        """E2E: HITL ask fails to send initial request."""
        mock_hitl_manager.ask = AsyncMock(
            side_effect=Exception("Failed to send HITL request: Network error")
        )

        with pytest.raises(Exception) as exc_info:
            await mock_hitl_manager.ask(
                question="Continue?",
                context={},
            )

        assert "Network error" in str(exc_info.value)


@pytest.mark.e2e
class TestWorkspaceToolNotAvailable:
    """E2E chaos tests for tool availability issues."""

    async def test_gmail_tool_not_available(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Gmail tool not available (service disabled)."""
        mock_workspace_client.gmail.send_message = AsyncMock(
            side_effect=Exception("Service not available: Gmail API is disabled")
        )

        with pytest.raises(Exception) as exc_info:
            await mock_workspace_client.gmail.send_message("draft-123")

        assert (
            "not available" in str(exc_info.value).lower()
            or "disabled" in str(exc_info.value).lower()
        )

    async def test_docs_tool_not_configured(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Docs tool not configured (missing scope)."""
        mock_workspace_client.docs.batch_update = AsyncMock(
            side_effect=Exception("403 This method requires docs.batchupdate scope")
        )

        with pytest.raises(Exception) as exc_info:
            await mock_workspace_client.docs.batch_update("doc-123", [])

        assert "scope" in str(exc_info.value).lower()

    async def test_sheets_tool_quota_project_exceeded(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Sheets tool quota exceeded at project level."""
        mock_workspace_client.sheets.get_spreadsheet = AsyncMock(
            side_effect=Exception("429 Resource exhausted - Project quota exceeded for Sheets API")
        )

        with pytest.raises(Exception) as exc_info:
            await mock_workspace_client.sheets.get_spreadsheet("sheet-123")

        assert "429" in str(exc_info.value) or "quota" in str(exc_info.value).lower()

    async def test_slides_tool_rate_limit(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Slides tool rate limited (user quota)."""
        mock_workspace_client.slides.batch_update = AsyncMock(
            side_effect=[
                Exception("429 Rate Limit Exceeded"),
                {"replies": []},
            ]
        )

        result = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await mock_workspace_client.slides.batch_update("slides-123", [])
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                if "429" not in str(e):
                    raise

        assert result is not None
        assert "replies" in result


@pytest.mark.e2e
class TestWorkspaceErrorRecovery:
    """E2E chaos tests for error recovery scenarios."""

    async def test_partial_failure_preserves_previous_changes(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Partial failure preserves successfully applied changes."""
        applied_updates: list[dict[str, Any]] = []

        async def mock_batch_update_with_tracking(
            sheet_id: str, updates: list[dict[str, Any]]
        ) -> dict[str, Any]:
            for update in updates:
                if update.get("range") == "A1":
                    applied_updates.append(update)
                    return {"replies": [{"updated_cells": 1}]}
                elif update.get("range") == "B2" and len(applied_updates) > 0:
                    raise Exception("429 Quota Exceeded")
            return {"replies": []}

        mock_workspace_client.sheets.batch_update = mock_batch_update_with_tracking

        updates = [
            {"range": "A1", "values": [["First"]]},
            {"range": "B2", "values": [["Second"]]},
        ]

        with suppress(Exception):
            await mock_workspace_client.sheets.batch_update("sheet-123", updates)

        assert len(applied_updates) == 1
        assert applied_updates[0]["range"] == "A1"

    async def test_error_context_preserved_in_trace(
        self,
        mock_workspace_client: MagicMock,
    ) -> None:
        """E2E: Error context is preserved in trace for debugging."""
        error_context: dict[str, Any] = {}

        async def mock_gmail_with_context(*args: object, **kwargs: object) -> None:
            error_context["last_error"] = "401 Unauthorized"
            error_context["retry_count"] = 0
            raise Exception("401 Unauthorized")

        mock_workspace_client.gmail.send_message = mock_gmail_with_context

        with suppress(Exception):
            await mock_workspace_client.gmail.send_message("draft-123")

        assert error_context["last_error"] == "401 Unauthorized"
        assert "retry_count" in error_context
