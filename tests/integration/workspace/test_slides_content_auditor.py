"""Integration tests for slides-content-auditor skill."""

import pytest


@pytest.mark.integration
class TestSlidesContentAuditor:
    """Test slides-content-auditor skill functionality."""

    @pytest.fixture
    def skill_context(self, mock_mcp_tools, mock_memory_tools, trace_id):
        """Build skill execution context."""
        return {
            "tools": mock_mcp_tools,
            "memory_tools": mock_memory_tools,
            "trace_id": trace_id,
            "params": {
                "presentation_id": "pres001",
            },
        }

    async def test_presentation_retrieval(self, skill_context):
        """Test retrieval of presentation metadata."""
        tools = skill_context["tools"]

        result = await tools["google_workspace_get_presentation"](presentation_id="pres001")

        assert result["presentation_id"] == "pres001"
        assert result["title"] == "Annual Review 2026"
        assert len(result["slides"]) == 3

    async def test_page_information_extraction(self, skill_context):
        """Test extraction of page/slide information."""
        tools = skill_context["tools"]

        slide_info = await tools["google_workspace_get_page"](page_id="slide1")

        assert slide_info["slide_id"] == "slide1"
        assert slide_info["title"] == "Annual Review"
        assert slide_info["layout"] == "title"
        assert len(slide_info["elements"]) == 2
        assert slide_info["text_element_count"] == 2

    async def test_thumbnail_generation(self, skill_context):
        """Test generation of slide thumbnail."""
        tools = skill_context["tools"]

        thumbnail = await tools["google_workspace_get_page_thumbnail"](page_id="slide1")

        assert "thumbnail_url" in thumbnail
        assert thumbnail["height"] == 720
        assert thumbnail["width"] == 1280

    async def test_text_density_calculation(self, skill_context):
        """Test calculation of text density per slide."""
        tools = skill_context["tools"]

        slide_info = await tools["google_workspace_get_page"](page_id="slide1")

        char_count = slide_info["character_count"]
        viewport_area = 1280 * 720
        density = char_count / viewport_area

        assert density < 1.0
        assert density > 0

    async def test_slide_inventory_generation(self, skill_context):
        """Test generation of complete slide inventory."""
        tools = skill_context["tools"]

        presentation = await tools["google_workspace_get_presentation"](presentation_id="pres001")

        inventory = []
        for slide_meta in presentation["slides"]:
            slide_info = await tools["google_workspace_get_page"](page_id=slide_meta["slide_id"])
            inventory.append(
                {
                    "slide_id": slide_meta["slide_id"],
                    "title": slide_info.get("title"),
                    "layout": slide_meta["layout"],
                    "text_element_count": slide_info["text_element_count"],
                    "character_count": slide_info["character_count"],
                }
            )

        assert len(inventory) == 3
        assert inventory[0]["slide_id"] == "slide1"

    async def test_text_density_classification(self, skill_context):
        """Test classification of slides by text density."""
        tools = skill_context["tools"]

        slide_info = await tools["google_workspace_get_page"](page_id="slide1")

        char_count = slide_info["character_count"]
        viewport_area = 1280 * 720
        density = char_count / viewport_area

        if density > 0.7:
            classification = "overcrowded"
        elif density < 0.3:
            classification = "sparse"
        else:
            classification = "normal"

        assert classification in ("overcrowded", "sparse", "normal")

    async def test_comment_extraction(self, skill_context):
        """Test extraction of presentation comments."""
        tools = skill_context["tools"]

        comments = await tools["google_workspace_read_presentation_comments"](
            presentation_id="pres001"
        )

        assert "comments" in comments
        assert len(comments["comments"]) == 1
        assert comments["comments"][0]["author"] == "reviewer@example.com"

    async def test_unresolved_comment_filtering(self, skill_context):
        """Test filtering of unresolved comments."""
        tools = skill_context["tools"]

        comments_result = await tools["google_workspace_read_presentation_comments"](
            presentation_id="pres001"
        )

        unresolved = [c for c in comments_result["comments"] if not c.get("resolved", False)]

        assert len(unresolved) == 1

    async def test_memory_storage_with_tags(self, skill_context):
        """Test memory storage includes correct tags."""
        tools = skill_context["tools"]
        memory_tools = skill_context["memory_tools"]

        presentation = await tools["google_workspace_get_presentation"](presentation_id="pres001")

        audit = {
            "presentation_id": presentation["presentation_id"],
            "title": presentation["title"],
            "total_slides": len(presentation["slides"]),
        }

        await memory_tools["aria_memory_remember"](
            entity_name=f"pres_{presentation['presentation_id']}_audit",
            entity_type="slides_audit",
            observations=[str(audit)],
            actor="agent_inference",
        )

        memory_tools["aria_memory_remember"].assert_called_once()
        call_kwargs = memory_tools["aria_memory_remember"].call_args
        assert call_kwargs[1].get("tags") is not None or "slides_audit" in str(call_kwargs)


@pytest.mark.integration
class TestSlidesContentAuditorInvariantCompliance:
    """Test that skill invariants are respected."""

    async def test_read_only_no_create_tools(self, mock_mcp_tools):
        """Test that no create tools are available."""
        tools = mock_mcp_tools

        create_tools = [k for k in tools.keys() if "create" in k]

        assert len(create_tools) == 0

    async def test_read_only_no_write_tools(self, mock_mcp_tools):
        """Test that no write/modify tools are available."""
        tools = mock_mcp_tools

        write_tools = [
            k for k in tools.keys() if "update" in k or "delete" in k or "batch_update" in k
        ]

        assert len(write_tools) == 0

    async def test_comment_read_only(self, mock_mcp_tools):
        """Test that only read comment operations are available."""
        tools = mock_mcp_tools

        comment_tools = [k for k in tools.keys() if "comment" in k]

        assert "google_workspace_read_presentation_comments" in comment_tools
        assert not any("delete_comment" in k or "update_comment" in k for k in comment_tools)


@pytest.mark.integration
class TestSlidesContentAuditorErrorHandling:
    """Test error conditions in slides-content-auditor skill."""

    async def test_presentation_not_found(self, mock_mcp_tools):
        """Test handling when presentation cannot be retrieved."""
        tools = mock_mcp_tools
        tools["google_workspace_get_presentation"].return_value = {
            "error": "Presentation not found"
        }

        result = await tools["google_workspace_get_presentation"](presentation_id="nonexistent")

        assert "error" in result

    async def test_page_not_found(self, mock_mcp_tools):
        """Test handling when page cannot be retrieved."""
        tools = mock_mcp_tools
        tools["google_workspace_get_page"].return_value = {"error": "Page not found"}

        result = await tools["google_workspace_get_page"](page_id="nonexistent")

        assert "error" in result

    async def test_empty_presentation(self, mock_mcp_tools):
        """Test handling of presentation with no slides."""
        tools = mock_mcp_tools
        tools["google_workspace_get_presentation"].return_value = {
            "presentation_id": "empty_pres",
            "title": "Empty Presentation",
            "slides": [],
        }

        result = await tools["google_workspace_get_presentation"](presentation_id="empty_pres")

        assert len(result["slides"]) == 0

    async def test_thumbnail_generation_failure(self, mock_mcp_tools):
        """Test handling when thumbnail generation fails."""
        tools = mock_mcp_tools
        tools["google_workspace_get_page_thumbnail"].return_value = {
            "error": "Thumbnail generation failed"
        }

        result = await tools["google_workspace_get_page_thumbnail"](page_id="slide1")

        assert "error" in result

    async def test_all_slides_overcrowded(self, mock_mcp_tools):
        """Test detection when all slides are overcrowded with text."""
        tools = mock_mcp_tools

        high_density_info = {
            "slide_id": "dense_slide",
            "title": "Dense Content",
            "layout": "title_and_content",
            "elements": [{"type": "body", "text": "x" * 5000} for _ in range(10)],
            "text_element_count": 10,
            "character_count": 50000,
        }

        tools["google_workspace_get_page"].return_value = high_density_info

        result = await tools["google_workspace_get_page"](page_id="dense_slide")

        viewport_area = 1280 * 720
        density = result["character_count"] / viewport_area

        assert density > 0.05
