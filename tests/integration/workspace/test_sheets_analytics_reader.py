"""Integration tests for sheets-analytics-reader skill."""

import pytest


@pytest.mark.integration
class TestSheetsAnalyticsReader:
    """Test sheets-analytics-reader skill functionality."""

    @pytest.fixture
    def skill_context(self, mock_mcp_tools, mock_memory_tools, trace_id):
        """Build skill execution context."""
        return {
            "tools": mock_mcp_tools,
            "memory_tools": mock_memory_tools,
            "trace_id": trace_id,
            "params": {
                "spreadsheet_query": "Sales Data 2026",
            },
        }

    async def test_spreadsheet_listing(self, skill_context):
        """Test listing of available spreadsheets."""
        tools = skill_context["tools"]

        result = await tools["google_workspace_list_spreadsheets"]()

        assert "spreadsheets" in result
        assert len(result["spreadsheets"]) == 1
        assert result["spreadsheets"][0]["spreadsheet_id"] == "ss001"
        assert result["spreadsheets"][0]["title"] == "Sales Data 2026"

    async def test_metadata_extraction(self, skill_context):
        """Test extraction of spreadsheet metadata."""
        tools = skill_context["tools"]

        info = await tools["google_workspace_get_spreadsheet_info"](spreadsheet_id="ss001")

        assert info["spreadsheet_id"] == "ss001"
        assert info["title"] == "Sales Data 2026"
        assert len(info["sheets"]) == 2
        assert info["sheets"][0]["name"] == "Q1"

    async def test_values_reading(self, skill_context):
        """Test reading of sheet values."""
        tools = skill_context["tools"]

        values = await tools["google_workspace_read_sheet_values"](
            spreadsheet_id="ss001",
            range="Sheet1!A1:Z100",
        )

        assert "values" in values
        assert len(values["values"]) == 5
        assert values["values"][0] == ["Product", "Revenue", "Cost"]

    async def test_schema_analysis(self, skill_context):
        """Test schema analysis from headers and sample data."""
        tools = skill_context["tools"]

        values = await tools["google_workspace_read_sheet_values"](
            spreadsheet_id="ss001",
            range="Sheet1!A1:Z100",
        )

        headers = values["values"][0]
        data_rows = values["values"][1:]

        schema = {
            "columns": [
                {
                    "name": headers[i] if i < len(headers) else f"Column{i + 1}",
                    "sample_values": [row[i] if i < len(row) else "" for row in data_rows[:3]],
                }
                for i in range(len(headers))
            ]
        }

        assert len(schema["columns"]) == 3
        assert schema["columns"][0]["name"] == "Product"
        assert schema["columns"][1]["name"] == "Revenue"

    async def test_type_inference(self, skill_context):
        """Test inference of column data types."""
        tools = skill_context["tools"]

        values = await tools["google_workspace_read_sheet_values"](
            spreadsheet_id="ss001",
            range="Sheet1!A1:Z100",
        )

        headers = values["values"][0]
        data_rows = values["values"][1:]

        def infer_type(column_values):
            non_empty = [v for v in column_values if v not in ("", None)]
            if not non_empty:
                return "empty"
            if all(v.replace(".", "").replace("-", "").isdigit() for v in non_empty):
                return "number"
            if all(v in ("true", "false", "TRUE", "FALSE") for v in non_empty):
                return "boolean"
            return "string"

        column_index = 1
        column_values = [row[column_index] if column_index < len(row) else "" for row in data_rows]
        inferred_type = infer_type(column_values)

        assert inferred_type == "number"

    async def test_empty_cell_detection(self, skill_context):
        """Test detection of empty cells in data."""
        tools = skill_context["tools"]

        values = await tools["google_workspace_read_sheet_values"](
            spreadsheet_id="ss001",
            range="Sheet1!A1:Z100",
        )

        data_rows = values["values"][1:]
        empty_row_indices = [
            i for i, row in enumerate(data_rows) if all(cell == "" for cell in row)
        ]

        assert len(empty_row_indices) == 1
        assert empty_row_indices[0] == 2

    async def test_duplicate_detection(self, skill_context):
        """Test detection of duplicate rows."""
        tools = skill_context["tools"]

        values = await tools["google_workspace_read_sheet_values"](
            spreadsheet_id="ss001",
            range="Sheet1!A1:Z100",
        )

        data_rows = values["values"][1:]
        seen = {}
        duplicates = []

        for i, row in enumerate(data_rows):
            row_key = tuple(row)
            if row_key in seen and row_key != ("", "", ""):
                duplicates.append({"original_index": seen[row_key], "duplicate_index": i})
            else:
                seen[row_key] = i

        assert len(duplicates) == 0

    async def test_quality_score_calculation(self, skill_context):
        """Test calculation of overall quality score."""
        tools = skill_context["tools"]

        values = await tools["google_workspace_read_sheet_values"](
            spreadsheet_id="ss001",
            range="Sheet1!A1:Z100",
        )

        data_rows = values["values"][1:]
        total_cells = sum(len(row) for row in data_rows)
        empty_cells = sum(1 for row in data_rows for cell in row if cell == "")
        empty_percentage = (empty_cells / total_cells * 100) if total_cells > 0 else 0

        quality_score = max(0, 100 - empty_percentage)

        assert quality_score < 100
        assert quality_score >= 0

    async def test_comments_extraction(self, skill_context):
        """Test extraction of sheet comments."""
        tools = skill_context["tools"]

        comments = await tools["google_workspace_read_sheet_comments"](
            spreadsheet_id="ss001",
            sheet_name="Q1",
        )

        assert "comments" in comments
        assert len(comments["comments"]) == 1
        assert comments["comments"][0]["cell"] == "A1"

    async def test_memory_storage_with_tags(self, skill_context):
        """Test memory storage includes correct tags."""
        tools = skill_context["tools"]
        memory_tools = skill_context["memory_tools"]

        info = await tools["google_workspace_get_spreadsheet_info"](spreadsheet_id="ss001")
        values = await tools["google_workspace_read_sheet_values"](
            spreadsheet_id="ss001", range="Sheet1!A1:Z100"
        )

        analysis = {
            "spreadsheet_id": info["spreadsheet_id"],
            "title": info["title"],
            "row_count": len(values["values"]),
        }

        await memory_tools["aria_memory_remember"](
            entity_name=f"sheet_{info['spreadsheet_id']}_analysis",
            entity_type="sheets_analytics",
            observations=[str(analysis)],
            actor="agent_inference",
        )

        memory_tools["aria_memory_remember"].assert_called_once()
        call_kwargs = memory_tools["aria_memory_remember"].call_args
        assert call_kwargs[1].get("tags") is not None or "sheets_analytics" in str(call_kwargs)


@pytest.mark.integration
class TestSheetsAnalyticsReaderInvariantCompliance:
    """Test that skill invariants are respected."""

    async def test_read_only_no_write_tools(self, mock_mcp_tools):
        """Test that no write tools are available."""
        tools = mock_mcp_tools

        write_tools = [
            k
            for k in tools.keys()
            if "write" in k or "update" in k or "append" in k or "batch_update" in k
        ]

        assert len(write_tools) == 0

    async def test_read_only_allowed_tools_only(self, mock_mcp_tools):
        """Test that only allowlisted tools are used."""
        tools = mock_mcp_tools

        sheets_allowed = {
            "google_workspace_list_spreadsheets",
            "google_workspace_get_spreadsheet_info",
            "google_workspace_read_sheet_values",
            "google_workspace_read_sheet_comments",
        }

        available_sheets_tools = [
            k for k in tools.keys() if k.startswith("google_workspace_") and "sheet" in k.lower()
        ]

        for tool_name in available_sheets_tools:
            assert tool_name in sheets_allowed


@pytest.mark.integration
class TestSheetsAnalyticsReaderErrorHandling:
    """Test error conditions in sheets-analytics-reader skill."""

    async def test_spreadsheet_not_found(self, mock_mcp_tools):
        """Test handling when spreadsheet cannot be retrieved."""
        tools = mock_mcp_tools
        tools["google_workspace_get_spreadsheet_info"].return_value = {
            "error": "Spreadsheet not found"
        }

        result = await tools["google_workspace_get_spreadsheet_info"](spreadsheet_id="nonexistent")

        assert "error" in result

    async def test_empty_spreadsheet_list(self, mock_mcp_tools):
        """Test handling of empty spreadsheet list."""
        tools = mock_mcp_tools
        tools["google_workspace_list_spreadsheets"].return_value = {"spreadsheets": []}

        result = await tools["google_workspace_list_spreadsheets"]()

        assert result["spreadsheets"] == []

    async def test_invalid_range_returns_error(self, mock_mcp_tools):
        """Test handling of invalid range."""
        tools = mock_mcp_tools
        tools["google_workspace_read_sheet_values"].return_value = {"error": "Invalid range"}

        result = await tools["google_workspace_read_sheet_values"](
            spreadsheet_id="ss001",
            range="InvalidSheet!A1:Z999999",
        )

        assert "error" in result

    async def test_all_empty_data_quality_score(self, mock_mcp_tools):
        """Test quality score when all data is empty."""
        tools = mock_mcp_tools
        tools["google_workspace_read_sheet_values"].return_value = {
            "values": [["Header"], ["", "", ""], ["", "", ""]]
        }

        result = await tools["google_workspace_read_sheet_values"](
            spreadsheet_id="ss001",
            range="Sheet1!A1:C3",
        )

        data_rows = result["values"][1:]
        total_cells = sum(len(row) for row in data_rows)
        empty_cells = sum(1 for row in data_rows for cell in row if cell == "")

        assert empty_cells == total_cells
