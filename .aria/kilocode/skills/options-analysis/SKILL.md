---
name: options-analysis
version: 1.0.0
description: Catene opzioni, grecs, strategie base, prob ITM, IV rank, volatility surface
trigger-keywords: [options, opzioni, strike, expiration, call, put, IV, Greeks, delta, gamma, theta, vega, ITM, OTM]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - aria-memory__wiki_update_tool
  - aria-memory__wiki_recall_tool
  - sequential-thinking__*
max-tokens: 50000
estimated-cost-eur: 0.10
---

# Options Analysis Skill

## Obiettivo

Analizzare catene di opzioni: prezzi, grecs, strategie, prob ITM,
IV rank, volatility surface.

## Tool disponibili

| Fonte | Tool | Dati |
|-------|------|------|
| helium-mcp | `get_top_trading_strategies` | AI-ranked options strategies |
| helium-mcp | `get_option_price` | ML fair-value per contract |
| helium-mcp | `get_ticker` | IV rank, volatility surface |
| financial-modeling-prep-mcp | Option chain tools | Strike, expiration, volume, OI |

## Pipeline

### Fase 1 — IV Analysis
1. Recupera IV rank e volatility surface
2. Compare current IV vs historical IV
3. Identify IV compression/expansion

### Fase 2 — Options Chain
1. Estrai chain per scadenza più rilevante
2. Identifica key strikes (ATM, nearest strikes)
3. Analizza volume e open interest

### Fase 3 — Greeks Analysis
1. Calculate or retrieve Delta, Gamma, Theta, Vega
2. Assess exposure and risk
3. Identify gamma/theta risk zones

### Fase 4 — Strategy Generation
1. Use `get_top_trading_strategies` per AI-ranked setups
2. Evaluate short vol vs long vol strategies
3. Calculate probability-weighted outcomes

### Fase 5 — Prob ITM
1. Calculate probability of ITM based on IV and time
2. Compare fair value vs market price
3. Assess intrinsic vs extrinsic value

## Regole operative

1. **Usa SEMPRE il proxy** con `_caller_id: "trader-agent"`
2. Usa `helium-mcp` come fonte primaria per AI options pricing
3. Usa `financial-modeling-prep-mcp` per chain data
4. **Disclaimer obbligatorio** su ogni output

## Esempio proxy call

```python
aria-mcp-proxy__call_tool("call_tool", {
    "name": "helium-mcp/get_ticker",
    "arguments": {"ticker": "AAPL"},
    "_caller_id": "trader-agent"
})
```

## Output strutturato

```
# Options Analysis: <TICKER>

## IV Rank & Surface
<IV rank: XX%, IV percentile: XX%>
<Surface shape: normal/inverted/flat>

## Near-Term Chain (<30 DTE)
| Strike | Type | Delta | Gamma | Theta | Vega | Vol |
|--------|------|-------|-------|-------|------|-----|
...

## Key Levels
<ATM strike, key strikes per scadenza>

## AI-Ranked Strategies
<top long vol / short vol setups>

## Prob ITM Assessment
<fair value vs market, probability metrics>

## Risk Assessment
<max loss zones, assignment risk>
```