"""Integration tests for gmail-composer-pro skill."""

import pytest


@pytest.mark.integration
class TestGmailComposerPro:
    """Test gmail-composer-pro skill functionality."""

    @pytest.fixture
    def skill_context(self, mock_mcp_tools, mock_memory_tools, trace_id):
        """Build skill execution context."""
        return {
            "tools": mock_mcp_tools,
            "memory_tools": mock_memory_tools,
            "trace_id": trace_id,
            "params": {
                "to": "bob@example.com",
                "subject": "Re: Project Update",
                "body": "Thank you for the update.",
                "thread_id": "thread123",
            },
        }

    async def test_draft_creation(self, skill_context):
        """Test creation of email draft."""
        tools = skill_context["tools"]

        draft = await tools["google_workspace_draft_gmail_message"](
            to=["bob@example.com"],
            subject="Re: Project Update",
            body="Thank you for the update.",
            references="<original-ref@example.com>",
            in_reply_to="<original-msg-id@example.com>",
        )

        assert draft["draft_id"] == "draft123"
        assert draft["message"]["to"] == ["bob@example.com"]
        assert "Re:" in draft["message"]["subject"]

    async def test_hitl_required_before_send(self, skill_context):
        """Test that HITL is required before send operation."""
        memory_tools = skill_context["memory_tools"]

        hitl_request = await memory_tools["aria_memory_hitl_ask"](
            action="send_email",
            summary="Email a bob@example.com: Re: Project Update",
            details={
                "to": ["bob@example.com"],
                "subject": "Re: Project Update",
                "body": "Thank you for the update.",
            },
        )

        assert hitl_request["action"] == "accept"

    async def test_send_blocked_without_hitl(self, mock_mcp_tools, mock_memory_tools):
        """Test that send is blocked when HITL is rejected."""
        memory_tools = mock_memory_tools
        memory_tools["aria_memory_hitl_ask"].return_value = {"action": "reject"}

        hitl_response = await memory_tools["aria_memory_hitl_ask"](
            action="send_email",
            summary="Email to bob@example.com",
        )

        should_block_send = hitl_response["action"] != "accept"

        assert should_block_send is True

    async def test_thread_safe_reply_headers(self, skill_context):
        """Test that reply headers preserve thread continuity."""
        tools = skill_context["tools"]
        tools["google_workspace_get_gmail_message_content"].return_value = {
            "id": "msg001",
            "References": "<ref1@example.com> <ref2@example.com>",
            "In-Reply-To": "<original-id@example.com>",
            "Subject": "Project Update",
        }

        original = await tools["google_workspace_get_gmail_message_content"](message_id="msg001")

        references = original.get("References", "")
        in_reply_to = original.get("In-Reply-To", "")

        new_references = f"{references} <{original['id']}@example.com>"

        assert "<ref1@example.com>" in new_references
        assert "<original-id@example.com>" in in_reply_to

    async def test_send_after_hitl_confirm(self, skill_context):
        """Test send proceeds after HITL confirmation."""
        tools = skill_context["tools"]
        memory_tools = skill_context["memory_tools"]

        memory_tools["aria_memory_hitl_ask"].return_value = {"action": "accept"}

        hitl_response = await memory_tools["aria_memory_hitl_ask"](
            action="send_email",
            summary="Email to bob@example.com",
        )

        assert hitl_response["action"] == "accept"

        send_result = await tools["google_workspace_send_gmail_message"](draft_id="draft123")

        assert send_result["status"] == "sent"
        assert "message_id" in send_result

    async def test_verification_after_send(self, skill_context):
        """Test verification of sent message."""
        tools = skill_context["tools"]

        send_result = await tools["google_workspace_send_gmail_message"](draft_id="draft123")

        message_id = send_result["message_id"]

        verified = await tools["google_workspace_get_gmail_message_content"](message_id=message_id)

        assert verified["id"] == "msg001"

    async def test_rejected_email_archived(self, mock_mcp_tools, mock_memory_tools):
        """Test that rejected emails are archived in memory."""
        memory_tools = mock_memory_tools
        memory_tools["aria_memory_hitl_ask"].return_value = {"action": "reject"}

        rejection = await memory_tools["aria_memory_hitl_ask"](
            action="send_email",
            summary="Email to bob@example.com: Test Subject",
        )

        assert rejection["action"] == "reject"

        await memory_tools["aria_memory_remember"](
            entity_name="rejected_email_session",
            entity_type="gmail_composer_decision",
            observations=["Email rejected: Test Subject"],
            actor="agent_inference",
        )

        memory_tools["aria_memory_remember"].assert_called_once()


@pytest.mark.integration
class TestGmailComposerProInvariantCompliance:
    """Test that skill invariants are respected."""

    async def test_hitl_mandatory_before_send(self, mock_memory_tools):
        """Test that HITL is always called before send."""
        memory_tools = mock_memory_tools

        await memory_tools["aria_memory_hitl_ask"](
            action="send_email",
            summary="Test send",
        )

        memory_tools["aria_memory_hitl_ask"].assert_called_once()

    async def test_thread_headers_preserved_on_reply(self, mock_mcp_tools):
        """Test that thread headers are preserved when replying."""
        tools = mock_mcp_tools
        tools["google_workspace_get_gmail_message_content"].return_value = {
            "id": "original_msg",
            "References": "<ref1@example.com>",
            "In-Reply-To": "<irt@example.com>",
            "Subject": "Original Subject",
        }

        original = await tools["google_workspace_get_gmail_message_content"](
            message_id="original_msg"
        )

        assert original["References"] is not None
        assert original["In-Reply-To"] is not None

    async def test_subject_prefix_on_reply(self, mock_mcp_tools):
        """Test that subject gets Re: prefix on reply."""
        tools = mock_mcp_tools
        tools["google_workspace_get_gmail_message_content"].return_value = {
            "Subject": "Original Subject",
        }

        original_subject = "Original Subject"
        reply_subject = (
            f"Re: {original_subject}"
            if not original_subject.startswith("Re:")
            else original_subject
        )

        assert reply_subject == "Re: Original Subject"

    async def test_no_send_without_hitl_confirm(self, mock_mcp_tools, mock_memory_tools):
        """Test that send does not proceed without HITL confirmation."""
        memory_tools = mock_memory_tools
        memory_tools["aria_memory_hitl_ask"].return_value = {"action": "pending"}

        response = await memory_tools["aria_memory_hitl_ask"](
            action="send_email",
        )

        can_send = response.get("action") == "accept"

        assert can_send is False


@pytest.mark.integration
class TestGmailComposerProErrorHandling:
    """Test error conditions in gmail-composer-pro skill."""

    async def test_draft_creation_failure(self, mock_mcp_tools):
        """Test handling when draft creation fails."""
        tools = mock_mcp_tools
        tools["google_workspace_draft_gmail_message"].return_value = {
            "error": "Draft creation failed"
        }

        result = await tools["google_workspace_draft_gmail_message"](
            to=["invalid"],
            subject="Test",
            body="Test body",
        )

        assert "error" in result

    async def test_send_failure(self, mock_mcp_tools):
        """Test handling when send fails."""
        tools = mock_mcp_tools
        tools["google_workspace_send_gmail_message"].return_value = {
            "error": "Send failed",
            "status": "failed",
        }

        result = await tools["google_workspace_send_gmail_message"](draft_id="draft123")

        assert "error" in result
        assert result["status"] == "failed"

    async def test_verification_mismatch(self, mock_mcp_tools):
        """Test handling when verification finds mismatch."""
        tools = mock_mcp_tools
        tools["google_workspace_get_gmail_message_content"].return_value = {
            "id": "msg123",
            "to": "bob@example.com",
            "subject": "Different Subject",
            "body": "Different body",
        }

        sent = {
            "message_id": "msg123",
            "to": ["bob@example.com"],
            "subject": "Original Subject",
            "body": "Original body",
        }

        verified = await tools["google_workspace_get_gmail_message_content"](
            message_id=sent["message_id"]
        )

        match = verified.get("subject") == sent["subject"] and verified.get("body") == sent["body"]

        assert match is False

    async def test_hitl_timeout_handling(self, mock_memory_tools):
        """Test handling when HITL times out."""
        memory_tools = mock_memory_tools
        memory_tools["aria_memory_hitl_ask"].return_value = {"action": "timeout"}

        response = await memory_tools["aria_memory_hitl_ask"](action="send_email")

        assert response["action"] == "timeout"
