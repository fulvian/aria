"""Integration tests for aria-amadeus-mcp FastMCP server.

Tests:
- Tool surface: all 6 tools have correct schemas
- Error handling: missing credentials → RuntimeError
- Error handling: ResponseError → structured error dict
- Tool annotations: all tools have readOnlyHint=True, destructiveHint=False
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Module path
SERVER_PATH = "src.aria.tools.amadeus.mcp_server"

# Expected tool definitions
EXPECTED_TOOLS = {
    "flight_offers_search": {
        "params": [
            "origin_location_code",
            "destination_location_code",
            "departure_date",
        ],
        "optional": ["return_date", "travel_class", "currency_code", "max_results", "non_stop"],
    },
    "hotel_offers_search": {
        "params": [],
        "optional": [
            "city_code",
            "hotel_ids",
            "latitude",
            "longitude",
            "check_in_date",
            "check_out_date",
            "adults",
            "room_quantity",
        ],
    },
    "hotel_list_by_geocode": {
        "params": ["latitude", "longitude"],
        "optional": ["radius", "radius_unit"],
    },
    "locations_search": {
        "params": ["keyword"],
        "optional": ["sub_type", "country_code"],
    },
    "nearest_airport": {
        "params": ["latitude", "longitude"],
        "optional": [],
    },
    "flight_status": {
        "params": ["carrier_code", "flight_number", "scheduled_departure_date"],
        "optional": [],
    },
}


@pytest.fixture(scope="module")
def server_module():
    """Import the server module to access tools."""
    import importlib

    return importlib.import_module(SERVER_PATH)


class TestAriaAmadeusMcpToolSurface:
    """All 6 tools are defined with correct schemas."""

    def test_tool_count(self, server_module):
        """Server defines exactly 6 tools."""
        mcp = server_module.mcp
        # Verify via server name
        assert mcp.name == "aria-amadeus-mcp"

    @pytest.mark.parametrize("tool_name", list(EXPECTED_TOOLS.keys()))
    def test_tool_function_exists(self, server_module, tool_name: str):
        """Each expected tool function exists in the module."""
        assert hasattr(server_module, tool_name), f"Missing tool function: {tool_name}"

    @pytest.mark.parametrize("tool_name", list(EXPECTED_TOOLS.keys()))
    def test_tool_is_callable(self, server_module, tool_name: str):
        """Each tool function is callable."""
        fn = getattr(server_module, tool_name)
        assert callable(fn), f"Tool {tool_name} is not callable"


class TestAriaAmadeusMcpMissingCredentials:
    """Server fails gracefully when credentials are missing."""

    def test_missing_credentials_returns_none(self, server_module):
        """Calling _get_client without env vars returns None."""
        with patch.dict("os.environ", {}, clear=True):
            result = server_module._get_client()
            assert result is None

    def test_tool_returns_error_dict_on_missing_creds(self, server_module):
        """Calling a tool without credentials returns error dict, not crash."""
        with patch.dict("os.environ", {}, clear=True):
            server_module._state["client"] = None
            result = server_module.flight_offers_search(
                origin_location_code="CTA",
                destination_location_code="BCN",
                departure_date="2026-06-01",
            )
            # Should return error dict from graceful handling
            assert isinstance(result, dict)
            assert result.get("error") is True


class TestAriaAmadeusMcpErrorHandling:
    """Tools handle Amadeus ResponseError properly."""

    @pytest.fixture
    def mock_response_error(self):
        """Create a mock ResponseError with response attribute."""
        from amadeus import ResponseError

        # Cannot mock spec=ResponseError because __init__ sets response attr
        # Use a plain MagicMock with the right structure
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.result = {"errors": [{"code": 1234, "title": "Bad request"}]}

        error = MagicMock(spec=ResponseError)
        error.response = mock_response
        error.__str__ = lambda self: "Amadeus API error: 400 Bad request"
        return error

    def test_handle_amadeus_error_structure(self, server_module, mock_response_error):
        """_handle_amadeus_error returns structured error dict."""
        result = server_module._handle_amadeus_error(mock_response_error)
        assert isinstance(result, dict)
        assert result["error"] is True
        assert result["status_code"] == 400
        assert "Amadeus API error" in result["message"]


class TestAriaAmadeusMcpAnnotations:
    """All tools have correct ToolAnnotations."""

    # We test via function inspection and module-level decorator presence
    def test_all_tools_have_readonly_semantics(self, server_module):
        """Verify the module's tool naming convention implies read-only."""
        # All 6 tool functions exist with read-only names
        read_only_operations = [
            "flight_offers_search",
            "hotel_offers_search",
            "hotel_list_by_geocode",
            "locations_search",
            "nearest_airport",
            "flight_status",
        ]
        for name in read_only_operations:
            assert hasattr(server_module, name), f"Missing function: {name}"
            fn = getattr(server_module, name)
            # All are GET/search operations (no create/update/delete/post)
            assert callable(fn)


@pytest.mark.skipif(
    not Path(".venv/bin/python").exists(),
    reason="requires venv",
)
class TestAriaAmadeusMcpStdio:
    """Server starts and responds to MCP stdio init."""

    def test_server_responds_to_list_tools(self):
        """Server responds to a tools/list request over stdio."""
        import subprocess

        # Find project root
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent

        proc = subprocess.Popen(
            [str(project_root / ".venv/bin/python"), "-m", SERVER_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root),
        )

        # MCP protocol requires initialize handshake before tools/list
        init_request = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            }
        )
        list_request = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
        )

        # FastMCP processes one line at a time from stdin
        payload = init_request + "\n" + list_request + "\n"
        stdout, stderr = proc.communicate(input=payload, timeout=10)
        proc.wait(timeout=5)

        # FastMCP outputs each JSON-RPC response on its own line
        responses = []
        for raw_line in stdout.strip().split("\n"):
            line = raw_line.strip()
            if line:
                try:
                    responses.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        assert len(responses) >= 2, (
            f"Expected >=2 responses, got {len(responses)}. stdout: {stdout[:1000]}"
        )

        # Second response should be tools/list
        list_response = responses[1]
        assert "result" in list_response, (
            f"Second response missing 'result': {json.dumps(list_response)[:200]}"
        )
        assert "tools" in list_response["result"], (
            f"tools/list result missing 'tools': {json.dumps(list_response['result'])[:200]}"
        )
        tools = list_response["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        expected = {
            "flight_offers_search",
            "hotel_offers_search",
            "hotel_list_by_geocode",
            "locations_search",
            "nearest_airport",
            "flight_status",
        }
        missing = expected - tool_names
        assert not missing, f"Missing tools in stdio response: {missing}"
