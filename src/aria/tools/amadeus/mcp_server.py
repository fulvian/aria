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
import time
from typing import TYPE_CHECKING, Any, cast

from amadeus import Client, ResponseError
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

if TYPE_CHECKING:
    from collections.abc import Callable

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

# ── Quota / circuit breaker ───────────────────────────────────────────────────

_FREE_TIER_LIMIT = 2000  # Amadeus free tier calls per month
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_SYSTEMIC_INTERNAL_ERROR_CODE = 38189
_SYSTEMIC_FAILURE_THRESHOLD = 2
_SYSTEMIC_QUARANTINE_SECONDS = 300
_MAX_RETRIES = 1

_state: dict[str, Any] = {
    "client": None,
    "call_count": 0,
    "quota_warning_emitted": False,
    "quarantined": False,
    "service_failure_count": 0,
    "service_quarantined_until": 0.0,
}


def _check_quota() -> dict[str, Any] | None:
    """Check Amadeus free tier quota.

    Returns an error dict if quota exceeded or warning info.
    Must be called before each tool invocation.
    """
    service_quarantined_until = float(_state.get("service_quarantined_until", 0.0))
    now = time.time()
    if service_quarantined_until > now:
        remaining_s = int(service_quarantined_until - now)
        return {
            "error": True,
            "status_code": 503,
            "retryable": False,
            "provider": "aria-amadeus-mcp",
            "reason": "upstream_service_quarantined",
            "fallback_hint": "Usa Booking o search-agent finché Amadeus resta in quarantena.",
            "message": (
                "Amadeus test environment in persistent internal-error state. "
                "Backend temporaneamente quarantinato per evitare retry inutili."
            ),
            "details": {"retry_after_seconds": remaining_s},
        }

    if _state["quarantined"] or _state["call_count"] >= _FREE_TIER_LIMIT:
        _state["quarantined"] = True
        return {
            "error": True,
            "status_code": 429,
            "retryable": False,
            "provider": "aria-amadeus-mcp",
            "reason": "local_quota_exhausted",
            "fallback_hint": "Usa Booking o search-agent per proseguire.",
            "message": (
                "Amadeus API quota esaurita per questo mese. "
                "Il backend è in auto-quarantine fino al prossimo ciclo di fatturazione."
            ),
            "details": {
                "call_count": _state["call_count"],
                "limit": _FREE_TIER_LIMIT,
            },
        }

    return None


def _record_api_call() -> dict[str, Any] | None:
    """Track an actual outbound Amadeus API call attempt."""
    _state["call_count"] += 1
    used = _state["call_count"]
    pct = (used / _FREE_TIER_LIMIT) * 100

    if pct >= 100:
        _state["quarantined"] = True
        return {
            "error": True,
            "status_code": 429,
            "retryable": False,
            "provider": "aria-amadeus-mcp",
            "reason": "local_quota_exhausted",
            "fallback_hint": "Usa Booking o search-agent per proseguire.",
            "message": "Amadeus API quota esaurita (100%). Auto-quarantine attivata.",
            "details": {"call_count": used, "limit": _FREE_TIER_LIMIT},
        }

    if pct >= 90 and not _state["quota_warning_emitted"]:
        _state["quota_warning_emitted"] = True
        # Soft warning: quota near limit
        import logging

        logging.warning(
            "Amadeus quota near limit: %d/%d (%.0f%%)",
            used,
            _FREE_TIER_LIMIT,
            pct,
        )

    return None


def _reset_quota() -> None:
    """Reset quota counters (e.g. monthly cycle)."""
    _state["call_count"] = 0
    _state["quota_warning_emitted"] = False
    _state["quarantined"] = False
    _state["service_failure_count"] = 0
    _state["service_quarantined_until"] = 0.0


# ── Client ────────────────────────────────────────────────────────────────────


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


def _extract_status_code(error: ResponseError) -> int:
    """Extract the HTTP status code from an Amadeus ResponseError."""
    status = 500
    if hasattr(error, "response") and error.response is not None:
        status = getattr(error.response, "status_code", 500)
    return status


def _retry_delay_seconds(error: ResponseError) -> float:
    """Best-effort retry delay for retryable Amadeus failures."""
    headers = getattr(getattr(error, "response", None), "headers", None) or {}
    retry_after = headers.get("Retry-After") or headers.get("retry-after")
    if retry_after is not None:
        try:
            return max(0.0, min(float(retry_after), 2.0))
        except (TypeError, ValueError):
            pass
    return 1.0


def _extract_error_code(error: ResponseError) -> int | None:
    """Extract provider-specific error code from an Amadeus ResponseError."""
    result = getattr(getattr(error, "response", None), "result", None)
    errors = result.get("errors") if isinstance(result, dict) else None
    first = errors[0] if isinstance(errors, list) and errors else None
    code = first.get("code") if isinstance(first, dict) else None
    return code if isinstance(code, int) else None


def _handle_amadeus_error(
    error: ResponseError,
    *,
    fallback_hint: str,
) -> dict[str, Any]:
    """Convert Amadeus ResponseError to a structured error dict."""
    status = _extract_status_code(error)
    error_code = _extract_error_code(error)
    details = None
    if hasattr(error, "response") and error.response is not None:
        details = getattr(error.response, "result", None)
    retryable = status in _RETRYABLE_STATUS_CODES and error_code != _SYSTEMIC_INTERNAL_ERROR_CODE
    reason = "upstream_rate_limited" if status == 429 else "upstream_error"
    if status < 500 and status != 429:
        reason = "request_error"
    if error_code == _SYSTEMIC_INTERNAL_ERROR_CODE:
        reason = "upstream_internal_error"
    return {
        "error": True,
        "status_code": status,
        "retryable": retryable,
        "provider": "aria-amadeus-mcp",
        "reason": reason,
        "fallback_hint": fallback_hint,
        "message": str(error),
        "details": details,
    }


def _record_service_failure(error: ResponseError) -> None:
    """Track systemic upstream failures and quarantine the backend if needed."""
    if _extract_error_code(error) != _SYSTEMIC_INTERNAL_ERROR_CODE:
        return
    failures = int(_state.get("service_failure_count", 0)) + 1
    _state["service_failure_count"] = failures
    if failures >= _SYSTEMIC_FAILURE_THRESHOLD:
        _state["service_quarantined_until"] = time.time() + _SYSTEMIC_QUARANTINE_SECONDS


def _clear_service_failure_state() -> None:
    """Clear systemic failure counters after a successful upstream call."""
    _state["service_failure_count"] = 0
    _state["service_quarantined_until"] = 0.0


def _missing_credentials_error() -> dict[str, Any]:
    """Return a structured error for missing credentials."""
    return {
        "error": True,
        "status_code": 401,
        "message": (
            "Amadeus credentials not configured. "
            "Set AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET env vars."
        ),
        "retryable": False,
        "provider": "aria-amadeus-mcp",
        "reason": "missing_credentials",
        "fallback_hint": "Usa Booking o search-agent per proseguire.",
        "details": None,
    }


def _execute_amadeus_call(
    request: Callable[[], list[dict[str, Any]]],
    *,
    fallback_hint: str,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Execute an Amadeus request with lightweight retry and structured fallback."""
    quota_err = _check_quota()
    if quota_err:
        return quota_err

    last_error: ResponseError | None = None
    for attempt in range(_MAX_RETRIES + 1):
        quota_err = _record_api_call()
        if quota_err:
            return quota_err
        try:
            result = request()
            _clear_service_failure_state()
            return result
        except ResponseError as error:
            last_error = error
            _record_service_failure(error)
            status = _extract_status_code(error)
            if _extract_error_code(error) == _SYSTEMIC_INTERNAL_ERROR_CODE:
                break
            if status not in _RETRYABLE_STATUS_CODES or attempt >= _MAX_RETRIES:
                break
            time.sleep(_retry_delay_seconds(error))

    assert last_error is not None
    return _handle_amadeus_error(last_error, fallback_hint=fallback_hint)


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

    return _execute_amadeus_call(
        lambda: amadeus.shopping.flight_offers_search.get(**params).data,
        fallback_hint="Usa search-agent per fallback voli grounded se Amadeus resta instabile.",
    )


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
    fallback_hint = "Usa Booking o Airbnb se Amadeus hotel offers resta instabile."

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

            def request() -> list[dict[str, Any]]:
                return cast(
                    "list[dict[str, Any]]",
                    amadeus.shopping.hotel_offers_search.get(**params).data,
                )

        elif city_code and check_in_date and check_out_date:
            params = _hotel_params()
            params["cityCode"] = city_code

            def request() -> list[dict[str, Any]]:
                return cast(
                    "list[dict[str, Any]]",
                    amadeus.shopping.hotel_offers_search.get(**params).data,
                )

        elif latitude is not None and longitude is not None:
            hotels = _execute_amadeus_call(
                lambda: (
                    amadeus.reference_data.locations.hotels.by_geocode.get(
                        latitude=latitude,
                        longitude=longitude,
                    ).data
                ),
                fallback_hint="Prova hotel_offers_search con city_code o usa Booking/Airbnb.",
            )
            if isinstance(hotels, dict):
                return hotels
            if not hotels:
                return {"error": True, "message": "No hotels found at this location"}
            params = _hotel_params()
            h_ids = [h["hotelId"] for h in hotels[:5]]
            params["hotelIds"] = ",".join(h_ids)

            def request() -> list[dict[str, Any]]:
                return cast(
                    "list[dict[str, Any]]",
                    amadeus.shopping.hotel_offers_search.get(**params).data,
                )

        else:
            return {
                "error": True,
                "message": (
                    "Provide at least one of: city_code (+ check_in/out dates), "
                    "hotel_ids, or latitude+longitude."
                ),
            }
        return _execute_amadeus_call(request, fallback_hint=fallback_hint)
    except ResponseError as e:
        return _handle_amadeus_error(
            e,
            fallback_hint="Prova hotel_offers_search con city_code o usa Booking/Airbnb.",
        )


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

    params: dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
    }
    if radius is not None:
        params["radius"] = radius
    if radius_unit:
        params["radiusUnit"] = radius_unit

    return _execute_amadeus_call(
        lambda: amadeus.reference_data.locations.hotels.by_geocode.get(**params).data,
        fallback_hint="Prova hotel_offers_search con city_code o usa Booking/Airbnb.",
    )


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

    return _execute_amadeus_call(
        lambda: amadeus.reference_data.locations.get(**params).data,
        fallback_hint="Usa search-agent se locations_search non restituisce aeroporti utili.",
    )


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

    return _execute_amadeus_call(
        lambda: (
            amadeus.reference_data.locations.airports.get(
                latitude=latitude,
                longitude=longitude,
            ).data
        ),
        fallback_hint="Prova locations_search con la città o usa search-agent per fallback voli.",
    )


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

    return _execute_amadeus_call(
        lambda: (
            amadeus.schedule.flights.get(
                carrierCode=carrier_code,
                flightNumber=flight_number,
                scheduledDepartureDate=scheduled_departure_date,
            ).data
        ),
        fallback_hint="Riprova più tardi o usa search-agent solo per verifica status grounded.",
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
