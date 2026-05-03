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

## Proxy invocation
Tutte le chiamate ai backend MCP passano dal proxy con `_caller_id: "traveller-agent"`.

## Pipeline

### 1. Raccolta ingredienti
Prima di costruire l'itinerario, assicurati di avere:
- **Destinazione** e coordinate (via osm-mcp__geocode_address)
- **Alloggi** (via accommodation-comparison skill)
- **Attività/ristoranti** (via activity-planning skill)
- **Trasporto** (via transport-planning skill)

### 2. Route optimization (se l'itinerario ha più punti)
Usa `osm-mcp__get_route_directions` per ottimizzare spostamenti tra waypoint:
```
name: "osm-mcp__get_route_directions"
arguments: {
  "start_lat": <lat>,
  "start_lon": <lon>,
  "end_lat": <lat>,
  "end_lon": <lon>,
  "mode": "walking"  # o "car", "cycling" a seconda della distanza
}
```

### 3. Costruzione giorno-per-giorno
Organizza le attività in ordine logico:
- **Mattina**: attività culturali/musei (aperti presto)
- **Pranzo**: ristorante nella zona
- **Pomeriggio**: tour/passeggiate/attività all'aperto
- **Sera**: cena + intrattenimento

Usa `osm-mcp__suggest_meeting_point` per trovare punti d'incontro ottimali:
```
name: "osm-mcp__suggest_meeting_point"
arguments: {
  "locations": [
    {"latitude": <lat1>, "longitude": <lon1>},
    {"latitude": <lat2>, "longitude": <lon2>}
  ],
  "category": "cafe",
  "limit": 3
}
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
