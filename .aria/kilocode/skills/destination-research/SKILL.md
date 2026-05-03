---
name: destination-research
version: 1.0.0
description: Ricerca destinazioni — clima, posizione, info pratiche, valuta, fuso orario, cultura, visti. Usa osm-mcp per geocoding e POI, aria-memory per preferenze utente.
trigger-keywords: [destinazione, meta, città, dove andare, clima, visto, cultura, fuso orario]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - aria-memory__wiki_recall_tool
  - aria-memory__wiki_update_tool
  - sequential-thinking__*
max-tokens: 30000
estimated-cost-eur: 0.01
---

# Destination Research Skill

## Obiettivo
Ricercare informazioni su una destinazione turistica: coordinate, clima,
info pratiche (valuta, lingua, fuso orario), requisiti visto, cultura locale.

## Proxy invocation
Tutte le chiamate ai backend MCP passano dal proxy con `_caller_id: "traveller-agent"`:

```
aria-mcp-proxy__call_tool(
  name="call_tool",
  arguments={
    "name": "<server__tool>",
    "arguments": {<parametri>},
    "_caller_id": "traveller-agent"
  }
)
```

## Pipeline

### 1. Recall preferenze utente
Sempre all'inizio: `aria-memory__wiki_recall_tool(query="<destinazione> travel preferences")`.
Recupera preferenze persistenti (es. "preferisco voli diretti", "compagnia preferita Lufthansa").

### 2. Geocoding destinazione
Usa `osm-mcp__geocode_address` via proxy per ottenere coordinate della destinazione:
```
name: "osm-mcp__geocode_address"
arguments: {"address": "<città, paese>"}
```

### 3. Informazioni pratiche
Usa `osm-mcp__explore_area` via proxy per esplorare la zona:
```
name: "osm-mcp__explore_area"
arguments: {"latitude": <lat>, "longitude": <lon>, "radius": 5000}
```
Interpreta i risultati per estrarre info su ristoranti, attrazioni, servizi.

### 4. Arricchimento
Se l'utente chiede informazioni non coperte da OSM (visti, sicurezza, eventi
politici), spawna `search-agent` (max depth 1) con goal specifico.

## Output atteso

```
## Destinazione: <Nome>
- **Posizione**: <coordinate, paese, regione>
- **Clima**: <temperatura media, stagione consigliata>
- **Valuta**: <nome, simbolo>
- **Lingua**: <lingua/e principali>
- **Fuso orario**: <UTC offset>
- **Visto**: <requisiti per cittadini IT>
- **Info pratiche**: <corrente elettrica, propina, sicurezza>
```

## Limiti
- OSM non ha dati clima/valuta/visti — usa conoscenza propria o search-agent
- Non inventare coordinate: usa sempre osm-mcp__geocode_address
- Non salvare automaticamente in wiki — solo su richiesta utente
