# Traveller Agent — Backend Setup

> **Scopo**: Registrazione e configurazione dei backend MCP per il traveller-agent.
> **Stato**: ✅ Fase 2 completata
> **Owner**: Fulvio Ventura
> **Creato**: 2026-05-03
> **Source**: `docs/plans/agents/traveller_agent_plan.md` §Fase 2

## Backend registrati

| Backend | Tipo | Auth | Costo | Stato |
|---------|------|------|-------|-------|
| `airbnb` | `@openbnb/mcp-server-airbnb` (npx) | keyless | gratuito | ✅ enabled |
| `osm-mcp` | `osm-mcp-server` (uvx) — OpenStreetMap | keyless | gratuito | ✅ enabled |
| `aria-amadeus-mcp` | locale FastMCP (Python) | `AMADEUS_CLIENT_ID` + `AMADEUS_CLIENT_SECRET` | gratuito (2K/mese) | ⏳ shadow (Fase 3) |
| `booking` | `@striderlabs/mcp-booking` (npx, Playwright) | keyless | gratuito | ⏳ gated (Fase 5) |

## Dettaglio per backend

### Airbnb (`airbnb`)
- **Comando**: `npx -y @openbnb/mcp-server-airbnb`
- **Tool**: `airbnb_search`, `airbnb_listing_details`
- **Auth**: nessuna (scraping pubblico)
- **Config**: Nessuna configurazione richiesta

### OpenStreetMap MCP (`osm-mcp`)
- **Comando**: `uvx osm-mcp-server`
- **Tool**: 12 tool (geocoding, POI, routes, area exploration)
- **Auth**: nessuna (API pubbliche OpenStreetMap: Nominatim, Overpass, OSRM)
- **Config**: Nessuna configurazione richiesta
- **Note**: Sostituisce Google Maps Platform (che richiedeva billing account). 100% free, no API key.

### ARIA Amadeus MCP (`aria-amadeus-mcp`)
- **Comando**: `scripts/wrappers/aria-amadeus-wrapper.sh`
- **Tool**: 6 tool read-only (flight_offers_search, hotel_offers_search, ...)
- **Auth**: `AMADEUS_CLIENT_ID` + `AMADEUS_CLIENT_SECRET` (via SOPS `api-keys.enc.yaml`)
- **Credenziali**: Crittografate con SOPS+age
- **Stato**: Lifecycle `shadow` — server FastMCP da implementare in Fase 3

## Credenziali SOPS

Le credenziali Amadeus sono cifrate in:
`.aria/credentials/secrets/api-keys.enc.yaml`

```yaml
providers:
    amadeus:
        client_id: <plaintext>
        client_secret: <ENC[AES256_GCM,...]>
        free_tier_credits: 2000
        key_id: amadeus-primary
```

Per modificare: `sops .aria/credentials/secrets/api-keys.enc.yaml`

## Rollback

- **Disable backend**: impostare `lifecycle: disabled` nel catalog
- **Disable singolo tool**: modificare `expected_tools` nel catalog
- **Emergency**: `bin/aria start --emergency-direct` bypassa tutti i backend
