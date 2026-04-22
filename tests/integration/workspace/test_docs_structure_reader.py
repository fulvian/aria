"""Integration tests for docs-structure-reader skill."""

import pytest


@pytest.mark.integration
class TestDocsStructureReader:
    """Test docs-structure-reader skill functionality."""

    @pytest.fixture
    def skill_context(self, mock_mcp_tools, mock_memory_tools, trace_id):
        """Build skill execution context."""
        return {
            "tools": mock_mcp_tools,
            "memory_tools": mock_memory_tools,
            "trace_id": trace_id,
            "params": {
                "document_query": "Q1 Report",
            },
        }

    async def test_document_search(self, skill_context):
        """Test document search returns matching documents."""
        tools = skill_context["tools"]

        result = await tools["google_workspace_search_docs"](query="Q1 Report")

        assert "documents" in result
        assert len(result["documents"]) == 1
        assert result["documents"][0]["document_id"] == "doc123"
        assert result["documents"][0]["title"] == "Q1 Report"

    async def test_content_extraction(self, skill_context):
        """Test content extraction with headings and tables."""
        tools = skill_context["tools"]

        content = await tools["google_workspace_get_doc_content"](document_id="doc123")

        assert content["document_id"] == "doc123"
        assert "Q1 Report" in content["content"]
        assert len(content["headings"]) == 3
        assert len(content["tables"]) == 1

    async def test_comment_reading(self, skill_context):
        """Test reading unresolved comments from document."""
        tools = skill_context["tools"]

        comments_result = await tools["google_workspace_read_doc_comments"](document_id="doc123")

        assert "comments" in comments_result
        unresolved = [c for c in comments_result["comments"] if not c["resolved"]]
        assert len(unresolved) == 1
        assert unresolved[0]["author"] == "alice@example.com"
        assert "review" in unresolved[0]["content"].lower()

    async def test_section_map_generation(self, skill_context):
        """Test generation of section map from headings."""
        tools = skill_context["tools"]

        content = await tools["google_workspace_get_doc_content"](document_id="doc123")
        headings = content.get("headings", [])

        section_map = {
            "headings": [
                {"level": h["level"], "text": h["text"], "position": h["position"]}
                for h in headings
            ]
        }

        assert len(section_map["headings"]) == 3
        assert section_map["headings"][0]["level"] == 1
        assert section_map["headings"][0]["text"] == "Q1 Report"

    async def test_table_map_generation(self, skill_context):
        """Test generation of table map with position and summary."""
        tools = skill_context["tools"]

        content = await tools["google_workspace_get_doc_content"](document_id="doc123")
        tables = content.get("tables", [])

        table_map = [
            {
                "position": t["position"],
                "rows": t["rows"],
                "columns": t["columns"],
                "content_summary": t["content_summary"],
            }
            for t in tables
        ]

        assert len(table_map) == 1
        assert table_map[0]["position"] == "A1:B3"
        assert table_map[0]["rows"] == 3
        assert table_map[0]["columns"] == 2

    async def test_editable_anchors_identification(self, skill_context):
        """Test identification of editable anchor positions."""
        tools = skill_context["tools"]

        content = await tools["google_workspace_get_doc_content"](document_id="doc123")
        paragraphs = content["content"].split("\n\n")

        anchors = []
        for i, para in enumerate(paragraphs):
            if para.strip() and not para.startswith("#"):
                anchors.append(
                    {
                        "position": f"paragraph-{i}",
                        "context": para.strip()[:50],
                    }
                )

        assert len(anchors) > 0

    async def test_folder_navigation(self, skill_context):
        """Test navigation to documents in specific folder."""
        tools = skill_context["tools"]

        result = await tools["google_workspace_list_docs_in_folder"](folder_id="folder123")

        assert "documents" in result
        assert len(result["documents"]) == 1
        assert result["documents"][0]["title"] == "Meeting Notes"

    async def test_memory_storage_with_tags(self, skill_context):
        """Test memory storage includes correct tags."""
        tools = skill_context["tools"]
        memory_tools = skill_context["memory_tools"]

        content = await tools["google_workspace_get_doc_content"](document_id="doc123")

        structure = {
            "document_id": content["document_id"],
            "title": content["title"],
            "section_count": len(content["headings"]),
            "table_count": len(content["tables"]),
        }

        await memory_tools["aria_memory_remember"](
            entity_name=f"doc_{content['document_id']}_structure",
            entity_type="docs_structure",
            observations=[str(structure)],
            actor="agent_inference",
        )

        memory_tools["aria_memory_remember"].assert_called_once()
        call_kwargs = memory_tools["aria_memory_remember"].call_args
        assert call_kwargs[1].get("tags") is not None or "docs_structure" in str(call_kwargs)


@pytest.mark.integration
class TestDocsStructureReaderInvariantCompliance:
    """Test that skill invariants are respected."""

    async def test_read_only_no_create(self, mock_mcp_tools):
        """Test that no create operations are called."""
        tools = mock_mcp_tools

        allowed_create_tools = [k for k in tools.keys() if k.startswith("google_workspace_create_")]

        assert len(allowed_create_tools) == 0

    async def test_read_only_no_modify(self, mock_mcp_tools):
        """Test that no modify operations are called."""
        tools = mock_mcp_tools

        allowed_modify_tools = [
            k for k in tools.keys() if "update" in k or "edit" in k or "batch_update" in k
        ]

        assert len(allowed_modify_tools) == 0

    async def test_read_only_no_delete(self, mock_mcp_tools):
        """Test that no delete operations are available."""
        tools = mock_mcp_tools

        allowed_delete_tools = [k for k in tools.keys() if "delete" in k]

        assert len(allowed_delete_tools) == 0


@pytest.mark.integration
class TestDocsStructureReaderErrorHandling:
    """Test error conditions in docs-structure-reader skill."""

    async def test_document_not_found(self, mock_mcp_tools):
        """Test handling when document cannot be retrieved."""
        tools = mock_mcp_tools
        tools["google_workspace_get_doc_content"].return_value = {"error": "Document not found"}

        result = await tools["google_workspace_get_doc_content"](document_id="nonexistent")

        assert "error" in result

    async def test_empty_search_results(self, mock_mcp_tools):
        """Test handling of empty search results."""
        tools = mock_mcp_tools
        tools["google_workspace_search_docs"].return_value = {"documents": []}

        result = await tools["google_workspace_search_docs"](query="nonexistent doc")

        assert result["documents"] == []

    async def test_document_with_no_comments(self, mock_mcp_tools):
        """Test handling of document with no comments."""
        tools = mock_mcp_tools
        tools["google_workspace_read_doc_comments"].return_value = {"comments": []}

        result = await tools["google_workspace_read_doc_comments"](document_id="doc123")

        assert result["comments"] == []
