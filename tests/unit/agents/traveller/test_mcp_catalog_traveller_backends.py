"""Static checks on MCP catalog entries for traveller-agent backends.

Verifica che:
- entry airbnb esiste con domain: travel, owner_agent: traveller-agent
- entry osm-mcp esiste con auth_mode: keyless (OpenStreetMap, free, no API key)
- entry aria-amadeus-mcp esiste con transport: stdio, source_of_truth wrapper
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CATALOG = Path(".aria/config/mcp_catalog.yaml")


@pytest.fixture(scope="module")
def servers() -> list[dict]:
    return yaml.safe_load(CATALOG.read_text(encoding="utf-8"))["servers"]


def _by_name(servers, name):
    by_name = {s["name"]: s for s in servers}
    assert name in by_name, f"server {name} missing from catalog"
    return by_name[name]


class TestMCPCatalogAirbnb:
    """Airbnb MCP server (@openbnb/mcp-server-airbnb)."""

    def test_airbnb_present(self, servers):
        s = _by_name(servers, "airbnb")
        assert s["domain"] == "travel"
        assert s["owner_agent"] == "traveller-agent"
        assert s["lifecycle"] == "enabled"
        assert s["transport"] == "stdio"
        assert s["auth_mode"] == "keyless"
        assert s["cost_class"] == "free"
        assert "airbnb_search" in s["expected_tools"]
        assert "airbnb_listing_details" in s["expected_tools"]


class TestMCPCatalogOsmMcp:
    """OpenStreetMap MCP server (@jagan-shanmugam/open-streetmap-mcp)."""

    def test_osm_mcp_present(self, servers):
        s = _by_name(servers, "osm-mcp")
        assert s["domain"] == "travel"
        assert s["owner_agent"] == "traveller-agent"
        assert s["lifecycle"] == "enabled"
        assert s["transport"] == "stdio"
        assert s["auth_mode"] == "keyless"
        assert s["cost_class"] == "free"

    def test_osm_mcp_expected_tools(self, servers):
        s = _by_name(servers, "osm-mcp")
        tools = s["expected_tools"]
        core_tools = [
            "geocode_address",
            "reverse_geocode",
            "find_nearby_places",
            "get_route_directions",
            "search_category",
            "explore_area",
        ]
        for tool in core_tools:
            assert tool in tools, f"osm-mcp missing expected tool: {tool}"


class TestMCPCatalogAriaAmadeus:
    """ARIA Amadeus MCP server (locale FastMCP)."""

    def test_aria_amadeus_mcp_present(self, servers):
        s = _by_name(servers, "aria-amadeus-mcp")
        assert s["domain"] == "travel"
        assert s["owner_agent"] == "traveller-agent"
        # lifecycle is shadow until wrapper script is created in Fase 3
        assert s["lifecycle"] in ("shadow", "enabled"), "aria-amadeus-mcp lifecycle"
        assert s["transport"] == "stdio"
        assert s["auth_mode"] == "api_key"
        assert s["cost_class"] == "free"

    def test_aria_amadeus_expected_tools(self, servers):
        s = _by_name(servers, "aria-amadeus-mcp")
        tools = s["expected_tools"]
        core_tools = [
            "flight_offers_search",
            "hotel_offers_search",
            "hotel_list_by_geocode",
            "locations_search",
            "nearest_airport",
            "flight_status",
        ]
        for tool in core_tools:
            assert tool in tools, f"aria-amadeus-mcp missing expected tool: {tool}"

    def test_aria_amadeus_has_env_vars(self, servers):
        s = _by_name(servers, "aria-amadeus-mcp")
        env = s.get("env", {})
        assert "AMADEUS_CLIENT_ID" in env
        assert "AMADEUS_CLIENT_SECRET" in env

    def test_aria_amadeus_has_wrapper_script(self, servers):
        s = _by_name(servers, "aria-amadeus-mcp")
        sot = s.get("source_of_truth", "")
        assert "wrapper" in sot.lower() or "scripts/" in sot
