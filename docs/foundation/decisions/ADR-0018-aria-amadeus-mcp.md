# ADR-0018: Aria-Amadeus-MCP — Local FastMCP Wrapper for Amadeus Self-Service

**Status**: Implemented (F3)
**Date**: 2026-05-03
**Authors**: fulvio
**Related**: ADR-0017 (traveller-agent), ADR-0015 (proxy)

## Context

The `traveller-agent` (ADR-0017) requires access to flight and hotel
search data. Following the P8 hard gate decision ladder from the agent
foundation protocol, three options were evaluated:

1. **Existing mature MCP server**: Search for a public MCP server for
   Amadeus Self-Service API. **Result**: no mature MCP server exists for
   Amadeus. The only candidates were low-quality or unmaintained.
2. **Skill composing existing tools**: Evaluate if a skill can replace the
   need for Amadeus. **Result**: no existing MCP server provides flight
   search, hotel GDS data, flight status, or airport lookup. A dedicated
   wrapper is required.
3. **Local Python tool (MCP)**: Create a FastMCP server wrapping the
   official Amadeus Python SDK. **Selected**.

Additionally, Google Maps Platform (`@cablate/mcp-google-map`) was
evaluated for POI/geocoding/routes but **rejected** because it requires a
Google Cloud billing account (credit card), which the user was unable to
set up. Replaced with `osm-mcp-server` (OpenStreetMap-based, 100% free,
no API key, no billing).

## Decision

Create `aria-amadeus-mcp` as a local FastMCP server in
`src/aria/tools/amadeus/mcp_server.py`:

- **Runtime**: Python 3.11+, FastMCP, stdio transport
- **SDK**: `amadeus` Python package (v12.0.0), Context7 verified
  (`/amadeus4dev/amadeus-python`)
- **Credentials**: `AMADEUS_CLIENT_ID` + `AMADEUS_CLIENT_SECRET` from
  environment variables, injected via proxy `CredentialInjector` middleware
- **Storage**: SOPS+age encrypted in `.aria/credentials/secrets/api-keys.enc.yaml`
- **Free tier**: 2000 API calls/month
- **Lifecycle**: `enabled` (after Fase 3)

### Tool surface (6 tools, all read-only)

| Tool | Endpoint | Parameters |
|------|----------|------------|
| `flight_offers_search` | `shopping.flight_offers_search.get` | origin, destination, dates, adults, class, currency, max, nonStop |
| `hotel_offers_search` | `shopping.hotel_offers_search.get` | cityCode/hotelIds/lat-lon, checkIn/Out, adults, roomQty |
| `hotel_list_by_geocode` | `reference_data.locations.hotels.by_geocode.get` | lat, lon, radius |
| `locations_search` | `reference_data.locations.get` | keyword, subType (AIRPORT/CITY/ANY) |
| `nearest_airport` | `reference_data.locations.airports.get` | lat, lon |
| `flight_status` | `schedule.flights.get` | carrierCode, flightNumber, date |

All tools have `ToolAnnotations(readOnlyHint=True, destructiveHint=False)`.

### Excluded (out of scope MVP)

- `flight_orders_post` (booking)
- `hotel_orders_post` (booking)
- All write operations (require HITL + payment workflow, future ADR)

## Rationale

1. **No mature MCP alternative**: Verified via ecosystem research — no
   public MCP server for Amadeus Self-Service API exists (P8 step 1).
2. **SDK quality**: Amadeus Python SDK is first-class (Context7 score 47,
   dev guides 83.55). Verified via Context7 documentation.
3. **Credential security**: SOPS+age encryption matches existing ARIA
   credential pipeline (same as brave, exa, tavily providers).
4. **Proxy-compatible**: FastMCP server is MCP/proxy-compatible immediately.
   No promotion path needed.
5. **Quota safety**: Circuit breaker with auto-quarantine at 100% and
   warning at 90% of free tier (2000/month).

### Google Maps exclusion rationale

Google Maps Platform was evaluated via P8 step 1 (existing MCP available:
`@cablate/mcp-google-map`, 285⭐, 18 tools) but **excluded** due to:
- Requires Google Cloud billing account with credit card (blocking)
- Post-March 2025 pricing: per-SKU quotas, no more $200 free credit
- Cost risk: users reporting $0→$130/month increases
- Replaced with `osm-mcp-server`: 12 tools, 100% free, no auth, no billing

## Consequences

### Positive

- 6 read-only tools for flight, hotel, location, and status data
- All tools are safe (readOnlyHint=True, no booking capability)
- Error handling converts Amadeus ResponseError to structured dicts
- Missing credentials → structured 401 error (no crash)
- Quota monitoring prevents unexpected API costs

### Negative

- Limited to Amadeus free tier (2000 calls/month)
- Amadeus free tier does NOT include low-cost carriers (Ryanair, Wizz)
- No hotel booking, no flight booking in MVP
- No train/car rental data (out of scope for Amadeus Self-Service MVP)

### Mitigations

- _check_quota() with auto-quarantine at 100%
- Warning log at 90% usage
- Degraded mode: if Amadeus is down, traveller-agent works with
  Airbnb + Booking + OSM only
- Future: upgrade to Amadeus paid tier or add Skyscanner/Kiwi if needed

## References

- `src/aria/tools/amadeus/mcp_server.py` — FastMCP server (400+ lines)
- `scripts/wrappers/aria-amadeus-wrapper.sh` — wrapper script
- `.aria/config/mcp_catalog.yaml` — catalog entry (lifecycle: enabled)
- `.aria/credentials/secrets/api-keys.enc.yaml` — SOPS encrypted credentials
- `tests/integration/agents/traveller/test_aria_amadeus_mcp_server.py` — 18 tests
- `docs/operations/traveller-backend-setup.md` — backend setup docs
