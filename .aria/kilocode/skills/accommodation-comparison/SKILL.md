---
name: accommodation-comparison
version: 1.0.0
description: Confronto multi-OTA di alloggi — Airbnb, Amadeus hotel, Booking. Compone tool airbnb, aria-amadeus-mcp e booking via proxy MCP.
trigger-keywords: [hotel, alloggio, airbnb, booking, casa vacanze, b&b, confronto alloggi, dove dormire]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - sequential-thinking__*
max-tokens: 40000
estimated-cost-eur: 0.02
---

# Accommodation Comparison Skill

## Obiettivo
Confrontare opzioni alloggio su più OTA (Airbnb, Amadeus hotel GDS, Booking)
per una destinazione, date e numero ospiti specifici. Produrre tabella
comparativa con prezzi, voti, posizione e link.

## ⚠️ REGOLA: DEVI chiamare tool, non descrivere
Chiama OGNI tool elencato sotto in sequenza. Usa SEMPRE il pattern esatto.

## Proxy invocation pattern
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "<server>__<tool>",
  "arguments": {<parametri>},
  "_caller_id": "traveller-agent"
})
```

## Pipeline — CHIAMATA OBBLIGATORIA

### 1. Geocoding destinazione — DEVI chiamare
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "osm-mcp__geocode_address",
  "arguments": {"address": "<nome città, paese>"},
  "_caller_id": "traveller-agent"
})
```

### 2. Ricerca Airbnb — DEVI chiamare
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "airbnb__airbnb_search",
  "arguments": {
    "location": "<città>",
    "checkIn": "<YYYY-MM-DD>",
    "checkOut": "<YYYY-MM-DD>",
    "adults": <numero>
  },
  "_caller_id": "traveller-agent"
})
```
Poi arricchisci top 3 con `airbnb__airbnb_listing_details`.

### 3. Ricerca Hotel Amadeus — DEVI chiamare
Prima hotel list per geocode:
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "aria-amadeus-mcp__hotel_list_by_geocode",
  "arguments": {"latitude": <lat>, "longitude": <lon>},
  "_caller_id": "traveller-agent"
})
```
Poi cerca offerte per i primi hotel:
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "aria-amadeus-mcp__hotel_offers_search",
  "arguments": {
    "hotel_ids": "<id1,id2>",
    "check_in_date": "<YYYY-MM-DD>",
    "check_out_date": "<YYYY-MM-DD>",
    "adults": <numero>
  },
  "_caller_id": "traveller-agent"
})
```

### 4. Ricerca Booking (se enabled — gated)
Usa lo stesso pattern con `booking__search_hotels` via proxy.

### 5. Sintesi comparativa
Combina risultati in tabella:

| Provider | Nome | Prezzo/notte | Voto | Posizione | Link |
|----------|------|-------------|------|-----------|------|
| Airbnb | ... | ... | ... | ... | [link](#) |
| Amadeus | ... | ... | ... | ... | [link](#) |
| Booking | ... | ... | ... | ... | [link](#) |

## Degraded mode
- Airbnb down → confronta solo Amadeus + Booking
- Amadeus down → confronta solo Airbnb + Booking
- Booking down → confronta solo Airbnb + Amadeus (Booking è gated)
- Tutti down → "Backend alloggi non disponibili"

## Output atteso

```
## Alloggio a <Destinazione>

### Top 3 confronto

| Provider | Alloggio | €/notte | Voto | Persone | Link |
|----------|----------|---------|------|---------|------|
| Airbnb | ... | ... | ... | ... | [Vedi](#) |
| Amadeus | ... | ... | ... | ... | [Vedi](#) |
```

Include disclaimer obbligatorio: "Nessuna prenotazione eseguita."
