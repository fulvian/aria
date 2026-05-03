"""ARIA Amadeus MCP — FastMCP wrapper for Amadeus Self-Service API.

Provides 6 read-only travel tools via FastMCP stdio server:
- flight_offers_search
- hotel_offers_search
- hotel_list_by_geocode
- locations_search
- nearest_airport
- flight_status

All tools are read-only (no booking/fare locking).
Free tier: 2000 calls/month.
"""
