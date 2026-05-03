"""aria-amadeus-mcp: FastMCP server wrapping Amadeus Self-Service API.

6 read-only tools for travel planning:
flight offers, hotel search, locations, flight status.
All tools are readOnlyHint=True, destructiveHint=False.

Usage:
    python -m aria.tools.amadeus.mcp_server

Requires env vars:
    AMADEUS_CLIENT_ID
    AMADEUS_CLIENT_SECRET
"""

from __future__ import annotations

import os
from typing import Any

from amadeus import Client, ResponseError
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

# ── Server setup ──────────────────────────────────────────────────────────────

mcp = FastMCP(
    "aria-amadeus-mcp",
    instructions=(
        "ARIA travel data provider via Amadeus Self-Service API. "
        "All tools are read-only — no bookings, no fare locking. "
        "Free tier: ~2000 API calls per month. "
        "Use flight_offers_search for flight comparisons, "
        "hotel_offers_search for accommodation, "
        "and locations_search for airport/city lookup."
    ),
)

# ── Client ────────────────────────────────────────────────────────────────────

_state: dict[str, Client | None] = {"client": None}


def _get_client() -> Client | None:
    """Lazy-initialized Amadeus client from env vars.

    Returns None if credentials are missing — tools handle this gracefully.
    """
    client = _state["client"]
    if client is None:
        client_id = os.environ.get("AMADEUS_CLIENT_ID")
        client_secret = os.environ.get("AMADEUS_CLIENT_SECRET")
        if not client_id or not client_secret:
            return None
        client = Client(client_id=client_id, client_secret=client_secret)
        _state["client"] = client
    return client


# ── Tool helpers ──────────────────────────────────────────────────────────────


def _handle_amadeus_error(error: ResponseError) -> dict[str, Any]:
    """Convert Amadeus ResponseError to a structured error dict."""
    status = 500
    details = None
    if hasattr(error, "response") and error.response is not None:
        status = getattr(error.response, "status_code", 500)
        details = getattr(error.response, "result", None)
    return {
        "error": True,
        "status_code": status,
        "message": str(error),
        "details": details,
    }


def _missing_credentials_error() -> dict[str, Any]:
    """Return a structured error for missing credentials."""
    return {
        "error": True,
        "status_code": 401,
        "message": (
            "Amadeus credentials not configured. "
            "Set AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET env vars."
        ),
        "details": None,
    }


# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool(
    annotations=ToolAnnotations(
        title="Flight Offers Search",
        readOnlyHint=True,
        destructiveHint=False,
    )
)
def flight_offers_search(
    origin_location_code: str,
    destination_location_code: str,
    departure_date: str,
    return_date: str | None = None,
    adults: int = 1,
    travel_class: str | None = None,
    currency_code: str | None = None,
    max_results: int | None = None,
    non_stop: bool | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Search for flight offers between two cities.

    Args:
        origin_location_code: IATA code of origin airport/city (e.g. 'CTA' for Catania).
        destination_location_code: IATA code of destination (e.g. 'BCN' for Barcelona).
        departure_date: Departure date in YYYY-MM-DD format.
        return_date: Optional return date for round trips (YYYY-MM-DD).
        adults: Number of adult passengers (default 1).
        travel_class: Optional cabin class ('ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST').
        currency_code: Currency for pricing (e.g. 'EUR').
        max_results: Maximum number of flight offers to return.
        non_stop: If True, only return direct/non-stop flights.

    Returns:
        List of flight offers with pricing, schedule and availability details.
    """
    amadeus = _get_client()
    if amadeus is None:
        return _missing_credentials_error()
    try:
        params: dict[str, Any] = {
            "originLocationCode": origin_location_code,
            "destinationLocationCode": destination_location_code,
            "departureDate": departure_date,
            "adults": adults,
        }
        if return_date:
            params["returnDate"] = return_date
        if travel_class:
            params["travelClass"] = travel_class
        if currency_code:
            params["currencyCode"] = currency_code
        if max_results is not None:
            params["max"] = max_results
        if non_stop is not None:
            params["nonStop"] = "true" if non_stop else "false"

        response = amadeus.shopping.flight_offers_search.get(**params)
        return response.data  # type: ignore[no-any-return]
    except ResponseError as e:
        return _handle_amadeus_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Hotel Offers Search",
        readOnlyHint=True,
        destructiveHint=False,
    )
)
def hotel_offers_search(
    city_code: str | None = None,
    hotel_ids: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    check_in_date: str | None = None,
    check_out_date: str | None = None,
    adults: int = 1,
    room_quantity: int | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Search for hotel offers by city, hotel IDs, or geolocation.

    Args:
        city_code: IATA city code (e.g. 'PAR' for Paris). Alternative to hotel_ids/lat-lon.
        hotel_ids: Comma-separated Amadeus hotel IDs. Alternative to city_code/geocode.
        latitude: Latitude for geolocation search.
        longitude: Longitude for geolocation search.
        check_in_date: Check-in date YYYY-MM-DD.
        check_out_date: Check-out date YYYY-MM-DD.
        adults: Number of adult guests.
        room_quantity: Number of rooms requested.

    Returns:
        List of hotel offers with rates and availability.
    """
    amadeus = _get_client()
    if amadeus is None:
        return _missing_credentials_error()

    # Build common search params
    def _hotel_params() -> dict[str, Any]:
        p: dict[str, Any] = {"adults": adults}
        if check_in_date:
            p["checkInDate"] = check_in_date
        if check_out_date:
            p["checkOutDate"] = check_out_date
        if room_quantity is not None:
            p["roomQuantity"] = room_quantity
        return p

    try:
        if hotel_ids:
            params = _hotel_params()
            params["hotelIds"] = hotel_ids
            response = amadeus.shopping.hotel_offers_search.get(**params)
        elif city_code and check_in_date and check_out_date:
            params = _hotel_params()
            params["cityCode"] = city_code
            response = amadeus.shopping.hotel_offers_search.get(**params)
        elif latitude is not None and longitude is not None:
            hotels_resp = amadeus.reference_data.locations.hotels.by_geocode.get(
                latitude=latitude,
                longitude=longitude,
            )
            hotels = hotels_resp.data
            if not hotels:
                return {"error": True, "message": "No hotels found at this location"}
            params = _hotel_params()
            h_ids = [h["hotelId"] for h in hotels[:5]]
            params["hotelIds"] = ",".join(h_ids)
            response = amadeus.shopping.hotel_offers_search.get(**params)
        else:
            return {
                "error": True,
                "message": (
                    "Provide at least one of: city_code (+ check_in/out dates), "
                    "hotel_ids, or latitude+longitude."
                ),
            }
        return response.data  # type: ignore[no-any-return]
    except ResponseError as e:
        return _handle_amadeus_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Hotel List by Geocode",
        readOnlyHint=True,
        destructiveHint=False,
    )
)
def hotel_list_by_geocode(
    latitude: float,
    longitude: float,
    radius: int | None = None,
    radius_unit: str | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """List hotels near a geographic coordinate.

    Args:
        latitude: Latitude of the location.
        longitude: Longitude of the location.
        radius: Search radius (default unit is KM).
        radius_unit: Unit for radius ('KM' or 'MILES').

    Returns:
        List of hotels with IDs, names, and distances.
    """
    amadeus = _get_client()
    if amadeus is None:
        return _missing_credentials_error()
    try:
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
        }
        if radius is not None:
            params["radius"] = radius
        if radius_unit:
            params["radiusUnit"] = radius_unit

        response = amadeus.reference_data.locations.hotels.by_geocode.get(**params)
        return response.data  # type: ignore[no-any-return]
    except ResponseError as e:
        return _handle_amadeus_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Locations Search",
        readOnlyHint=True,
        destructiveHint=False,
    )
)
def locations_search(
    keyword: str,
    sub_type: str = "AIRPORT",
    country_code: str | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Search for airports, cities, or points of interest by keyword.

    Use this to find IATA codes for cities and airports.

    Args:
        keyword: Search text (e.g. 'Catania', 'Lon' for London airports).
        sub_type: Type of location — 'AIRPORT', 'CITY', or 'ANY'.
        country_code: Optional ISO country code filter (e.g. 'IT').

    Returns:
        List of matching locations with IATA codes, names, and coordinates.
    """
    amadeus = _get_client()
    if amadeus is None:
        return _missing_credentials_error()
    try:
        from amadeus import Location

        # Map string sub_type to Amadeus Location constant
        type_map = {
            "AIRPORT": Location.AIRPORT,
            "CITY": Location.CITY,
            "ANY": Location.ANY,
        }
        st = type_map.get(sub_type.upper(), Location.ANY)

        params: dict[str, Any] = {
            "keyword": keyword,
            "subType": st,
        }
        if country_code:
            params["countryCode"] = country_code

        response = amadeus.reference_data.locations.get(**params)
        return response.data  # type: ignore[no-any-return]
    except ResponseError as e:
        return _handle_amadeus_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Nearest Airport",
        readOnlyHint=True,
        destructiveHint=False,
    )
)
def nearest_airport(
    latitude: float,
    longitude: float,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Find the nearest airport(s) to a geographic location.

    Args:
        latitude: Latitude of the location.
        longitude: Longitude of the location.

    Returns:
        List of nearest airports with IATA codes and distances.
    """
    amadeus = _get_client()
    if amadeus is None:
        return _missing_credentials_error()
    try:
        response = amadeus.reference_data.locations.airports.get(
            latitude=latitude,
            longitude=longitude,
        )
        return response.data  # type: ignore[no-any-return]
    except ResponseError as e:
        return _handle_amadeus_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Flight Status",
        readOnlyHint=True,
        destructiveHint=False,
    )
)
def flight_status(
    carrier_code: str,
    flight_number: str,
    scheduled_departure_date: str,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Get real-time status of a specific flight.

    Args:
        carrier_code: IATA airline code (e.g. 'AZ' for ITA Airways, 'FR' for Ryanair).
        flight_number: Flight number (e.g. '1678').
        scheduled_departure_date: Scheduled departure date YYYY-MM-DD.

    Returns:
        Flight status data including delays, gate, terminal, and status updates.
    """
    amadeus = _get_client()
    if amadeus is None:
        return _missing_credentials_error()
    try:
        response = amadeus.schedule.flights.get(
            carrierCode=carrier_code,
            flightNumber=flight_number,
            scheduledDepartureDate=scheduled_departure_date,
        )
        return response.data  # type: ignore[no-any-return]
    except ResponseError as e:
        return _handle_amadeus_error(e)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
