---
name: macro-intelligence
version: 1.0.0
description: Dati macroeconomici — FRED, tassi, inflazione, NFP, GDP, PMI, correlazioni
trigger-keywords: [macro, FRED, tassi, inflation, CPI, PPI, NFP, GDP, PMI, Treasury, yield, Fed, recessione]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy_search_tools
  - aria-mcp-proxy_call_tool
  - aria-memory_wiki_update_tool
  - aria-memory_wiki_recall_tool
  - sequential-thinking_*
max-tokens: 50000
estimated-cost-eur: 0.05
---

# Macro Intelligence Skill

## Obiettivo

Monitorare e analizzare il contesto macroeconomico: tassi, inflazione,
occupazione, crescita, e il loro impatto sui mercati.

## Serie FRED disponibili (via mcp-fredapi)

| Serie | Descrizione | Frequenza |
|-------|-------------|-----------|
| DGS2, DGS5, DGS10, DGS30 | Treasury yields | Giornaliera |
| CPIAUCSL | Consumer Price Index | Mensile |
| PCECTPI | PCE Price Index | Mensile |
| UNRATE | Unemployment Rate | Mensile |
| PAYEMS | Nonfarm Payrolls | Mensile |
| GDPPOT, GDPC1 | GDP | Trimestrale |
| AHEP | Avg Hourly Earnings | Mensile |
| INDPRO | Industrial Production | Mensile |
| UMichCSI | Consumer Sentiment | Mensile |
| TEDRATE | TED Spread | Giornaliera |

## Pipeline

### Fase 1 — Treasury Yield Curve
Analizza la curva dei rendimenti:
- 2Y, 5Y, 10Y, 30Y yields
- Spread 2Y-10Y (recession predictor)
- Yield curve shape (normal, flat, inverted)

### Fase 2 — Inflation Metrics
- CPI YoY, MoM
- PCE YoY, MoM
- Core vs Headline
- Inflation expectations (breakeven)

### Fase 3 — Labor Market
- NFP (Nonfarm Payrolls)
- Unemployment rate
- Average hourly earnings
- Labor force participation

### Fase 4 — Growth Indicators
- GDP growth rate
- Manufacturing PMI
- Consumer sentiment
- Industrial production

### Fase 5 — Cross-Asset Correlations
- Yield vs S&P 500
- Dollar vs commodities
- Credit spreads vs equities

## Regole operative

1. **Usa SEMPRE il proxy** con `_caller_id: "trader-agent"`
2. Usa `mcp-fredapi` come fonte primaria (gold standard macro)
3. **Disclaimer obbligatorio** su ogni output

## Esempio proxy call

Nel runtime Kilo i tool del proxy possono apparire come alias
`aria-mcp-proxy_search_tools` / `aria-mcp-proxy_call_tool`.

```python
# Discovery
aria-mcp-proxy_search_tools({"query": "FRED treasury yield CPI GDP macro", "_caller_id": "trader-agent"})

# Esecuzione — mcp-fredapi è enabled (stdio)
aria-mcp-proxy_call_tool({
    "name": "mcp-fredapi_get_fred_series_observations",
    "arguments": {"series_id": "DGS10", "sort_order": "desc", "limit": 30},
    "_caller_id": "trader-agent"
})
```

## Output strutturato

```
# Macro Dashboard

## Yield Curve
<2Y: X.XX%, 5Y: X.XX%, 10Y: X.XX%, 30Y: X.XX%>
<Curve shape: normal/flat/inverted>
<2Y-10Y spread: Xbp>

## Inflation
<CPI YoY: X.X%, PCE YoY: X.X%>
<Core: X.X%>

## Labor
<NFP: +XXXk, Unemployment: X.X%>
<AHE YoY: X.X%>

## Growth
<GDP: X.X%, PMI: XX.X>

## Market Impact
<key takeaways per markets>
```
