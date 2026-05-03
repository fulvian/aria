---
name: itinerary-building
version: 1.0.0
description: Costruzione itinerario giorno-per-giorno con waypoint optimization. Compone osm-mcp e attività pre-calcolate per produrre percorso ottimizzato.
trigger-keywords: [itinerario, programma di viaggio, giorno per giorno, percorso, waypoint, ottimizzazione percorso, cosa fare giorno]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - sequential-thinking__*
max-tokens: 40000
estimated-cost-eur: 0.02
---

# Itinerary Building Skill

## Obiettivo
Costruire un itinerario giorno-per-giorno ottimizzato per una destinazione,
combinando trasporto, alloggio, attività e ristoranti in una sequenza logica
con waypoint ottimizzati.

## ⚠️ REGOLA: DEVI chiamare tool, non descrivere
Chiama OGNI tool elencato. Non pianificare astrattamente.

## Proxy invocation pattern
```
aria-mcp-proxy__call_tool(name="<server>__<tool>", arguments={
  <parametri>,
  "_caller_id": "traveller-agent"
})
```

## Pipeline — CHIAMATA OBBLIGATORIA

### 1. Raccolta ingredienti — DEVI chiamare osm-mcp__geocode_address
Prima di costruire l'itinerario, DEVI avere coordinate reali:
```
aria-mcp-proxy__call_tool(name="osm-mcp__geocode_address", arguments={
  "address": "<città>",
  "_caller_id": "traveller-agent"
})
```

### 2. Route optimization (se multi-waypoint) — DEVI chiamare
```
aria-mcp-proxy__call_tool(name="osm-mcp__get_route_directions", arguments={
  "start_lat": <lat>, "start_lon": <lon>,
  "end_lat": <lat>, "end_lon": <lon>,
  "mode": "walking",
  "_caller_id": "traveller-agent"
})
```

### 3. Meeting point (se richiesto) — DEVI chiamare
```
aria-mcp-proxy__call_tool(name="osm-mcp__suggest_meeting_point", arguments={
  "locations": [
    {"latitude": <lat1>, "longitude": <lon1>},
    {"latitude": <lat2>, "longitude": <lon2>}
  ],
  "category": "cafe",
  "limit": 3,
  "_caller_id": "traveller-agent"
})
```

### 4. Sintesi
Produci itinerario strutturato:

```
## Itinerario: <Nome Viaggio>

### Giorno 1 — <Titolo giorno>
**Tema**: <cultura/relax/avventura...>

| Ora | Attività | Luogo | Note |
|-----|----------|-------|------|
| 09:00 | Colazione | ... | ... |
| 10:00 | Visita ... | ... | ... |
| 13:00 | Pranzo | ... | ... |
| 15:00 | ... | ... | ... |
| 20:00 | Cena | ... | ... |

**Spostamenti**: <mezzo suggerito, tempi>
**Budget giorno**: ~XX€

### Giorno 2
...
```

## Regole
- Ogni giorno deve avere un tema/un'area geografica
- Non mettere più di 3-4 attività principali al giorno
- Includere tempi di spostamento tra waypoint
- Considerare orari di apertura (basati su conoscenza generale)
- Bilanciare attività intensive e momenti di relax
- Se la città è grande, raggruppa attività per zona
