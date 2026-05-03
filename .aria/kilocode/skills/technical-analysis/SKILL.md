---
name: technical-analysis
version: 1.0.0
description: Analisi tecnica — RSI, MACD, SMA, EMA, Bollinger Bands, pattern detection, support/resistance
trigger-keywords: [tecnica, technical, RSI, MACD, Bollinger, SMA, EMA, support, resistance, trend, pattern, candlestick]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy_search_tools
  - aria-mcp-proxy_call_tool
  - aria-memory_wiki_update_tool
  - aria-memory_wiki_recall_tool
  - sequential-thinking_*
max-tokens: 50000
estimated-cost-eur: 0.08
---

# Technical Analysis Skill

## Obiettivo

Condurre un'analisi tecnica completa su un asset: indicatori, pattern,
livelli di supporto/resistenza, trend analysis.

## Indicatori e tool mapping

| Indicatore | Fonte | Tool |
|------------|-------|------|
| RSI(14) | financekit-mcp | `technical_analysis` |
| MACD | financekit-mcp | `technical_analysis` |
| Bollinger Bands | financekit-mcp | `technical_analysis` |
| SMA/EMA | financekit-mcp | `technical_analysis` |
| ADX | financekit-mcp | `technical_analysis` |
| Stochastic | financekit-mcp | `technical_analysis` |
| ATR | financekit-mcp | `technical_analysis` |
| OBV | financekit-mcp | `technical_analysis` |
| Pattern detection | financekit-mcp | `technical_analysis` |

## Pipeline

### Fase 1 — Technical Analysis completo
Chiama `technical_analysis` per ottenere:
- RSI(14), MACD, Bollinger Bands
- SMA(50), SMA(200), EMA(12), EMA(26)
- ADX, Stochastic, ATR, OBV
- Pattern signals (Golden Cross, Death Cross, overbought/oversold)

### Fase 2 — Price History
Recupera dati storici per visualizzazione:
- OHLCV data (1D, 1W, 1M, 3M)
- Summary statistics (mean, std, min, max)

### Fase 3 — Signal Summary
Interpreta i segnali:
- **Bullish**: RSI < 30, MACD histogram positive, price > SMA50, Golden Cross
- **Bearish**: RSI > 70, MACD histogram negative, price < SMA50, Death Cross
- **Neutral**: price within Bollinger Bands, ADX < 25

### Fase 4 — Support/Resistance
Identifica livelli critici:
- 52-week high/low
- Recent support/resistance zones
- Trendlines significative

## Regole operative

1. **Usa SEMPRE il proxy** con `_caller_id: "trader-agent"`
2. Usa `financekit-mcp` come fonte primaria per indicatori
3. **Disclaimer obbligatorio** su ogni output

## Esempio proxy call

Nel runtime Kilo i tool del proxy possono apparire come alias
`aria-mcp-proxy_search_tools` / `aria-mcp-proxy_call_tool`.

```python
# Discovery
aria-mcp-proxy_search_tools({"query": "technical analysis RSI MACD indicators", "_caller_id": "trader-agent"})

# Esecuzione
aria-mcp-proxy_call_tool({
    "name": "financekit-mcp_technical_analysis",
    "arguments": {"symbol": "AAPL"},
    "_caller_id": "trader-agent"
})
```

## Output strutturato

```
# Technical Analysis: <TICKER>

## Price Overview
<current price, 52wk range>

## Indicatori
| Indicatore | Valore | Signal |
|------------|--------|--------|
| RSI(14) | XX | bullish/bearish/neutral |
| MACD | XX | bullish/bearish |
| Bollinger | XX | normal/overbought/oversold |
...

## Pattern Signals
<Golden Cross, Death Cross, etc.>

## Support/Resistance
| Livello | Type |
|---------|------|
| $XXX | Resistance |
| $XXX | Support |

## Trend Summary
<Overall signal: BUY/SELL/HOLD>
```
