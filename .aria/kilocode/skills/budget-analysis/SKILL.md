---
name: budget-analysis
version: 1.0.0
description: Analisi budget viaggio — stima costi per categoria (volo, alloggio, pasti, attività, trasporto locale) con breakdown giornaliero e totale.
trigger-keywords: [budget, costo, costi, quanto costa, preventivo, spesa, risparmiare, economia]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - sequential-thinking__*
max-tokens: 20000
estimated-cost-eur: 0.01
---

# Budget Analysis Skill

## Obiettivo
Stimare il costo complessivo di un viaggio, suddiviso per categorie di spesa.
Produrre breakdown chiaro con range di prezzo (economy/mid-range/lusso).

## ⚠️ REGOLA: DEVI ottenere PREZZI REALI via tool MCP
Non inventare prezzi. Chiama i tool per ottenere dati reali.

## Proxy invocation pattern
```
aria-mcp-proxy__call_tool(name="<server>__<tool>", arguments={
  <parametri>,
  "_caller_id": "traveller-agent"
})
```

## Pipeline — CHIAMATA OBBLIGATORIA

### 1. Raccolta costi REALI via tool MCP
DEVI chiamare questi tool per ottenere PREZZI VERI:
- **Voli**:
```
aria-mcp-proxy__call_tool(name="aria-amadeus-mcp__flight_offers_search", arguments={
  "origin_location_code": "<IATA>",
  "destination_location_code": "<IATA>",
  "departure_date": "<YYYY-MM-DD>",
  "adults": <numero>,
  "_caller_id": "traveller-agent"
})
```
- **Alloggi Airbnb**:
```
aria-mcp-proxy__call_tool(name="airbnb__airbnb_search", arguments={
  "location": "<città>",
  "checkIn": "<YYYY-MM-DD>",
  "checkOut": "<YYYY-MM-DD>",
  "adults": <numero>,
  "_caller_id": "traveller-agent"
})
```
- **Alloggi Hotel Amadeus**:
```
aria-mcp-proxy__call_tool(name="aria-amadeus-mcp__hotel_offers_search", arguments={
  "hotel_ids": "<id1,id2>",
  "check_in_date": "<YYYY-MM-DD>",
  "check_out_date": "<YYYY-MM-DD>",
  "adults": <numero>,
  "_caller_id": "traveller-agent"
})
```

### 2. Breakdown per categoria
Organizza in categorie standard:

| Categoria | Range giorno | Range totale | Note |
|-----------|-------------|-------------|------|
| 🛩️ Volo | — | XXX-XXX€ | Prezzo A/R da Amadeus |
| 🏨 Alloggio | XX-XX€ | XXX-XXX€ | Per notte × N notti |
| 🍝 Pasti | XX-XX€ | XXX-XXX€ | Colazione + pranzo + cena |
| 🎟️ Attività | X-XX€ | XX-XXX€ | Ingressi, tour, escursioni |
| 🚇 Trasporto locale | X-XX€ | XX-XXX€ | Bus, metro, taxi, transfer |
| 🛍️ Extra | XX-XX€ | XX-XXX€ | Shopping, souvenir, imprevisti |

### 3. Fasce di budget

| Fascia | Alloggio/notte | Pasti/giorno | Volo A/R (EU) | Volo A/R (inter) |
|--------|---------------|-------------|---------------|------------------|
| 🟢 Economy | <50€ | <30€ | <100€ | <400€ |
| 🟡 Mid-range | 50-120€ | 30-70€ | 100-250€ | 400-900€ |
| 🔴 Luxury | >120€ | >70€ | >250€ | >900€ |

### 4. Sintesi
Produci budget breakdown:

```
## Budget Viaggio: <Destinazione>

**Durata**: X notti / Y giorni
**Persone**: N
**Fascia**: Economy / Mid-range / Luxury

| Voce | Costo |
|------|-------|
| 🛩️ Volo A/R | XXX€ |
| 🏨 Alloggio (×N notti) | XXX€ |
| 🍝 Pasti (×Y giorni) | XXX€ |
| 🎟️ Attività | XXX€ |
| 🚇 Trasporto locale | XXX€ |
| 🛍️ Extra (10%) | XXX€ |
| **Totale** | **XXX€** |

### Confronto opzioni
| Opzione | Budget | Descrizione |
|---------|--------|-------------|
| Economy | XXX€ | ... |
| Mid-range | XXX€ | ... |
| Lusso | XXX€ | ... |

### Consigli risparmio
- <suggerimenti specifici per la destinazione>
```

## Limiti
- Voli e hotel: range da Amadeus free tier (prezzi potrebbero variare)
- Pasti/attività: stima basata su conoscenza generale, non su API reali
- Non includere spese impreviste oltre il 10% di buffer
- Disclaimer obbligatorio: "Stima indicativa — verifica prezzi sui provider"

## Degraded mode
- `flight_offers_search` → `429/5xx`: usa Booking/alloggi superstiti +
  `search-agent` per fallback voli grounded, marcando il costo voli come
  fallback web e non da MCP travel pricing.
- `airbnb_search` → `robots.txt`: escludi Airbnb e continua con Booking +
  Amadeus hotel se disponibili.
- `hotel_offers_search` non disponibile: costruisci budget parziale con Booking
  o Airbnb e dichiara chiaramente la copertura residua.
