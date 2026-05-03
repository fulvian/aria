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

## Proxy invocation
Tutte le chiamate ai backend MCP passano dal proxy con `_caller_id: "traveller-agent"`.

## Pipeline

### 1. Location resolution
Ottieni coordinate della destinazione e trova aeroporti vicini:
```
name: "osm-mcp__geocode_address"
arguments: {"address": "<città, paese>"}
```

Poi trova aeroporti (via Amadeus se disponibile, via OSM altrimenti):
```
name: "aria-amadeus-mcp__nearest_airport"
arguments: {"latitude": <lat>, "longitude": <lon>}
```
Oppure:
```
name: "aria-amadeus-mcp__locations_search"
arguments: {"keyword": "<città>", "sub_type": "AIRPORT"}
```

### 2. Ricerca voli
```
name: "aria-amadeus-mcp__flight_offers_search"
arguments: {
  "origin_location_code": "<IATA>",
  "destination_location_code": "<IATA>",
  "departure_date": "<YYYY-MM-DD>",
  "return_date": "<YYYY-MM-DD>",  # opzionale
  "adults": <numero>,
  "travel_class": "ECONOMY",  # opzionale
  "currency_code": "EUR",  # opzionale
  "max_results": 5,  # opzionale
  "non_stop": true  # opzionale
}
```

### 3. Stato volo (se richiesto)
```
name: "aria-amadeus-mcp__flight_status"
arguments: {
  "carrier_code": "<IATA>",
  "flight_number": "<numero>",
  "scheduled_departure_date": "<YYYY-MM-DD>"
}
```

### 4. Route optimization (opzionale)
Se serve pianificare spostamenti via terra tra più punti:
```
name: "osm-mcp__get_route_directions"
arguments: {
  "start_lat": <lat>,
  "start_lon": <lon>,
  "end_lat": <lat>,
  "end_lon": <lon>,
  "mode": "car"  # o "cycling", "walking"
}
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
