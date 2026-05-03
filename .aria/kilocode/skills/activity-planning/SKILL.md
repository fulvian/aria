---
name: activity-planning
version: 1.0.0
description: Pianificazione attività — POI, ristoranti, attrazioni, eventi, tour. Usa osm-mcp per search_category e find_nearby_places.
trigger-keywords: [ristorante, ristoranti, attrazione, attrazioni, museo, monumento, tour, escursione, evento, cosa vedere, cosa fare, dove mangiare, cucina locale]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - sequential-thinking__*
max-tokens: 30000
estimated-cost-eur: 0.01
---

# Activity Planning Skill

## Obiettivo
Ricercare e raccomandare attività, ristoranti, attrazioni e punti di interesse
per una destinazione. Produrre lista strutturata con descrizione, posizione,
fascia di prezzo e link.

## Proxy invocation
Per discovery usa direttamente `aria-mcp-proxy__search_tools(query="...")`.

Tutte le chiamate ai backend MCP passano dal proxy con `_caller_id: "traveller-agent"` dentro `arguments`.

## Pipeline

### 1. Geocoding destinazione
```
aria-mcp-proxy__call_tool(name="osm-mcp__geocode_address", arguments={
  "address": "<città, paese>",
  "_caller_id": "traveller-agent"
})
```

### 2. Ricerca per categoria
Usa `osm-mcp__find_nearby_places` per trovare POI vicini:
```
aria-mcp-proxy__call_tool(name="osm-mcp__find_nearby_places", arguments={
  "latitude": <lat>,
  "longitude": <lon>,
  "radius": 1000,
  "category": "restaurant",
  "limit": 10,
  "_caller_id": "traveller-agent"
})
```

Categorie consigliate:
- `restaurant` — ristoranti
- `museum` — musei
- `monument` — monumenti
- `park` — parchi
- `shopping` — shopping
- `entertainment` — intrattenimento
- `cafe` — bar/caffè
- `nightlife` — vita notturna

Oppure usa `osm-mcp__search_category` per ricerca più mirata:
```
aria-mcp-proxy__call_tool(name="osm-mcp__search_category", arguments={
  "latitude": <lat>,
  "longitude": <lon>,
  "radius": 2000,
  "category": "ristorante",
  "limit": 5,
  "_caller_id": "traveller-agent"
})
```

### 3. Arricchimento (opzionale)
Se l'utente chiede dettagli specifici non coperti da OSM:
- Recensioni/prezzi: spawna `search-agent` (max depth 1)
- Eventi culturali: spawna `search-agent`

### 4. Sintesi
Produci lista raccomandata:

```
## Attività & Ristoranti a <Destinazione>

### 🍽️ Ristoranti consigliati
| Nome | Tipo | Fascia prezzo | Zona |
|------|------|--------------|------|
| ... | ... | €€-€€€ | ... |

### 🏛️ Attrazioni
| Nome | Tipo | Durata visita | Distanza |
|------|------|--------------|----------|
| ... | ... | ... | ... |
```

## Limiti
- OSM ha copertura POI buona ma non esaustiva
- OSM non ha recensioni/prezzi — usare search-agent se necessario
- Non inventare orari di apertura o costi non verificati
