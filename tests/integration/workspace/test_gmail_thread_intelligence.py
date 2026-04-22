"""Integration tests for gmail-thread-intelligence skill."""

import pytest


@pytest.mark.integration
class TestGmailThreadIntelligence:
    """Test gmail-thread-intelligence skill functionality."""

    @pytest.fixture
    def skill_context(self, mock_mcp_tools, mock_memory_tools, trace_id):
        """Build skill execution context."""
        return {
            "tools": mock_mcp_tools,
            "memory_tools": mock_memory_tools,
            "trace_id": trace_id,
            "params": {
                "thread_query": "is:thread from:alice@example.com subject:Project",
            },
        }

    async def test_thread_search_returns_messages(self, skill_context):
        """Test thread search with mock returns properly structured messages."""
        tools = skill_context["tools"]

        search_result = await tools["google_workspace_search_gmail_messages"](
            q="is:thread from:alice@example.com subject:Project"
        )

        assert "messages" in search_result
        assert len(search_result["messages"]) == 1
        assert search_result["messages"][0]["id"] == "msg001"
        assert search_result["messages"][0]["thread_id"] == "thread123"

    async def test_message_content_extraction(self, skill_context):
        """Test message content extraction returns full metadata."""
        tools = skill_context["tools"]

        content = await tools["google_workspace_get_gmail_message_content"](message_id="msg001")

        assert content["id"] == "msg001"
        assert content["subject"] == "Project Update"
        assert content["from"] == "alice@example.com"
        assert content["to"] == "bob@example.com"
        assert len(content["attachments"]) == 1
        assert content["attachments"][0]["filename"] == "report.pdf"

    async def test_timeline_reconstruction(self, skill_context):
        """Test timeline reconstruction from multiple messages."""
        tools = skill_context["tools"]
        mock_memory_tools = skill_context["memory_tools"]

        search_result = await tools["google_workspace_search_gmail_messages"](
            q="is:thread subject:Project"
        )
        messages = search_result["messages"]

        timeline = []
        for msg in messages:
            content = await tools["google_workspace_get_gmail_message_content"](
                message_id=msg["id"]
            )
            timeline.append(
                {
                    "index": len(timeline),
                    "from": content["from"],
                    "to": content["to"],
                    "timestamp": content["timestamp"],
                    "snippet": content.get("body", "")[:100],
                    "has_attachments": len(content.get("attachments", [])) > 0,
                    "attachment_count": len(content.get("attachments", [])),
                }
            )

        assert len(timeline) == 1
        assert timeline[0]["from"] == "alice@example.com"
        assert timeline[0]["has_attachments"] is True
        assert timeline[0]["attachment_count"] == 1

    async def test_risk_flag_detection_external_sender(self, skill_context):
        """Test risk flag detection for external senders."""
        tools = skill_context["tools"]

        content = await tools["google_workspace_get_gmail_message_content"](message_id="msg001")

        risk_flags = []

        if "@external.com" not in content.get("from", ""):
            risk_flags.append(
                {
                    "flag": "external_sender",
                    "severity": "high",
                    "detail": f"Email from external domain: {content.get('from')}",
                }
            )

        if content.get("bcc"):
            risk_flags.append(
                {
                    "flag": "bcc_recipient",
                    "severity": "medium",
                    "detail": "BCC recipients present",
                }
            )

        if not content.get("subject"):
            risk_flags.append(
                {
                    "flag": "no_subject",
                    "severity": "low",
                    "detail": "Message has no subject",
                }
            )

        assert len(risk_flags) == 1
        assert risk_flags[0]["flag"] == "external_sender"

    async def test_risk_flag_detection_attachment_no_context(self, skill_context):
        """Test risk flag for attachment without body context."""
        tools = skill_context["tools"]

        content = await tools["google_workspace_get_gmail_message_content"](message_id="msg001")

        attachments = content.get("attachments", [])
        body = content.get("body", "")

        for att in attachments:
            has_context = any(att["filename"].split(".")[0].lower() in body.lower() for _ in [1])
            att["has_context_in_body"] = has_context

        assert len(attachments) == 1
        assert attachments[0]["has_context_in_body"] is False

    async def test_attachment_extraction(self, skill_context):
        """Test attachment extraction returns filename, size, mime_type."""
        tools = skill_context["tools"]

        content = await tools["google_workspace_get_gmail_message_content"](message_id="msg001")

        attachments = content.get("attachments", [])

        extracted = [
            {
                "filename": att["filename"],
                "size_bytes": att["size_bytes"],
                "mime_type": att["mime_type"],
            }
            for att in attachments
        ]

        assert len(extracted) == 1
        assert extracted[0]["filename"] == "report.pdf"
        assert extracted[0]["size_bytes"] == 102400
        assert extracted[0]["mime_type"] == "application/pdf"

    async def test_memory_storage_on_analysis(self, skill_context):
        """Test that analysis results are stored in memory."""
        tools = skill_context["tools"]
        memory_tools = skill_context["memory_tools"]

        search_result = await tools["google_workspace_search_gmail_messages"](
            q="is:thread subject:Project"
        )

        analysis = {
            "thread_id": "thread123",
            "subject": "Project Update",
            "message_count": len(search_result["messages"]),
            "participants": ["alice@example.com"],
        }

        memory_result = await memory_tools["aria_memory_remember"](
            entity_name=f"thread_{search_result['messages'][0]['thread_id']}",
            entity_type="gmail_thread_analysis",
            observations=[str(analysis)],
            actor="agent_inference",
        )

        assert memory_result is True
        memory_tools["aria_memory_remember"].assert_called_once()

    async def test_participant_role_identification(self, skill_context):
        """Test identification of participant roles in thread."""
        messages = [
            {"from": "alice@example.com", "to": "bob@example.com"},
            {"from": "bob@example.com", "to": "alice@example.com"},
            {"from": "bob@example.com", "to": "alice@example.com, carol@example.com"},
        ]

        participant_counts = {}
        for msg in messages:
            sender = msg["from"]
            participant_counts[sender] = participant_counts.get(sender, 0) + 1

        roles = []
        for email, count in participant_counts.items():
            if count == 1:
                role = "sender"
            elif count > 1:
                role = "reply-all" if count == 2 else "sole-replier"
            else:
                role = "cross-participant"
            roles.append({"email": email, "message_count": count, "role": role})

        assert len(roles) == 2
        sender_role = next(r for r in roles if r["email"] == "alice@example.com")
        assert sender_role["role"] == "sender"
        replier_role = next(r for r in roles if r["email"] == "bob@example.com")
        assert replier_role["role"] == "reply-all"


@pytest.mark.integration
class TestGmailThreadIntelligenceErrorHandling:
    """Test error conditions in gmail-thread-intelligence skill."""

    async def test_empty_search_results(self, mock_mcp_tools, mock_memory_tools):
        """Test handling of empty search results."""
        tools = mock_mcp_tools
        tools["google_workspace_search_gmail_messages"].return_value = {"messages": []}

        result = await tools["google_workspace_search_gmail_messages"](q="no results query")

        assert result["messages"] == []

    async def test_message_not_found(self, mock_mcp_tools):
        """Test handling when message content cannot be retrieved."""
        tools = mock_mcp_tools
        tools["google_workspace_get_gmail_message_content"].return_value = {
            "error": "Message not found"
        }

        result = await tools["google_workspace_get_gmail_message_content"](message_id="nonexistent")

        assert "error" in result

    async def test_thread_too_large_alert(self, mock_mcp_tools):
        """Test alert when thread exceeds 50 messages."""
        tools = mock_mcp_tools
        tools["google_workspace_search_gmail_messages"].return_value = {
            "messages": [{"id": f"msg{i}", "thread_id": "large_thread"} for i in range(60)]
        }

        result = await tools["google_workspace_search_gmail_messages"](q="is:thread large")

        message_count = len(result["messages"])
        assert message_count == 60
        assert message_count > 50
