---
name: transport-planning
version: 1.0.0
description: Pianificazione trasporti — voli, aeroporti, transfer, itinerari. Compone tool aria-amadeus-mcp e osm-mcp via proxy MCP. Read-only MVP (nessun booking).
trigger-keywords: [volo, voli, aereo, compagnia aerea, aeroporto, treno, transfer, noleggio auto, biglietto]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - sequential-thinking__*
max-tokens: 30000
estimated-cost-eur: 0.02
---

# Transport Planning Skill

## Obiettivo
Pianificare trasporto per un viaggio: ricerca voli, individuazione aeroporti
vicini, confronto opzioni di trasporto. Read-only: nessun booking eseguito.

## ⚠️ REGOLA: CHIAMARE tool via proxy, non descrivere
DEVI chiamare TUTTI i tool elencati nella pipeline, in ordine.
Non saltare passi. Usa il pattern ESATTO qui sotto per ogni chiamata.

## Proxy invocation pattern
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "<server>__<tool>",
  "arguments": {<parametri>},
  "_caller_id": "traveller-agent"
})
```

## Pipeline — CHIAMATA OBBLIGATORIA

### 1. Location resolution — DEVI chiamare questi tool
Ottieni coordinate della destinazione e trova aeroporti vicini:
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "osm-mcp__geocode_address",
  "arguments": {"address": "<città, paese>"},
  "_caller_id": "traveller-agent"
})
```

Poi trova aeroporti (via Amadeus):
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "aria-amadeus-mcp__nearest_airport",
  "arguments": {"latitude": <lat>, "longitude": <lon>},
  "_caller_id": "traveller-agent"
})
```
Oppure:
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "aria-amadeus-mcp__locations_search",
  "arguments": {"keyword": "<città>", "sub_type": "AIRPORT"},
  "_caller_id": "traveller-agent"
})
```

### 2. Ricerca voli — DEVI chiamare
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "aria-amadeus-mcp__flight_offers_search",
  "arguments": {
    "origin_location_code": "<IATA>",
    "destination_location_code": "<IATA>",
    "departure_date": "<YYYY-MM-DD>",
    "adults": <numero>
  },
  "_caller_id": "traveller-agent"
})
```

### 3. Stato volo (se richiesto) — DEVI chiamare
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "aria-amadeus-mcp__flight_status",
  "arguments": {
    "carrier_code": "<IATA>",
    "flight_number": "<numero>",
    "scheduled_departure_date": "<YYYY-MM-DD>"
  },
  "_caller_id": "traveller-agent"
})
```

### 4. Route optimization (se richiesto) — DEVI chiamare
```
aria-mcp-proxy__call_tool(name="call_tool", arguments={
  "name": "osm-mcp__get_route_directions",
  "arguments": {
    "start_lat": <lat>, "start_lon": <lon>,
    "end_lat": <lat>, "end_lon": <lon>,
    "mode": "car"
  },
  "_caller_id": "traveller-agent"
})
```

### 5. Sintesi
Produci tabella comparativa:

| Opzione | Dettagli | Prezzo | Durata | Link |
|---------|----------|--------|--------|------|
| Volo AZ1678 | CTA→BCN diretto | ~120€ | 2h | [Prenota](#) |
| ... | ... | ... | ... | ... |

## Output atteso

```
## Trasporto: <Origine> → <Destinazione>

### Voli disponibili
| Compagnia | Volo | Partenza | Arrivo | Durata | Prezzo | Scali |
|-----------|------|----------|--------|--------|--------|-------|
| ... | ... | ... | ... | ... | ... | ... |

### Alternative (treno/auto)
...

### Stato voli (se richiesto)
...
```

## Limiti
- Voli: solo Amadeus free tier (2K/mese). Monitorare quota.
- Nessun booking live: solo ricerca e link.
- Treni/auto non coperti da Amadeus MVP. Se richiesti, segnalare limite.
- Amadeus non copre low-cost (Ryanair/Wizz). Se richiesti, spawnare search-agent.
