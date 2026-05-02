---
name: crypto-analysis
version: 1.0.0
description: On-chain, DEX data, funding rates, whale tracking, crypto technicals
trigger-keywords: [crypto, bitcoin, BTC, ETH,ethereum, solana, DEX, on-chain, funding rate, whale, DeFi]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - aria-memory__wiki_update_tool
  - aria-memory__wiki_recall_tool
  - sequential-thinking__*
max-tokens: 50000
estimated-cost-eur: 0.08
---

# Crypto Analysis Skill

## Obiettivo

Analizzare asset crypto: price action, on-chain metrics, DeFi data,
funding rates, whale activity.

## Tool disponibili

| Fonte | Tool | Dati |
|-------|------|------|
| financekit-mcp | `crypto_price` | Price, market cap, 24h change, ATH |
| financekit-mcp | `crypto_trending` | Top trending coins |
| financekit-mcp | `crypto_search` | Find coins by name/symbol |
| financekit-mcp | `crypto_top_coins` | Top N by market cap |
| helium-mcp | `get_ticker` | BTC, ETH con bull/bear case |
| financial-modeling-prep-mcp | Crypto data | Extended crypto coverage |

## Pipeline

### Fase 1 — Price & Market Data
1. Recupera price attuale e metriche base
2. 24h/7d/30d change
3. Market cap, volume, ATH distance

### Fase 2 — Technicals
1. Apply same technical indicators as stocks
2. RSI, MACD, Bollinger Bands
3. Trend analysis

### Fase 3 — On-Chain (se disponible)
1. Funding rates (long/short equilibrium)
2. Exchange flows (in/out)
3. Whale activity indicators
4. DeFi TVL and metrics

### Fase 4 — Comparative Analysis
1. Compare vs Bitcoin dominance
2. Compare vs Ethererum (for alts)
3. Sector performance

## Regole operative

1. **Usa SEMPRE il proxy** con `_caller_id: "trader-agent"`
2. Usa `financekit-mcp` come fonte primaria
3. Usa `helium-mcp` per BTC/ETH analysis
4. Usa `financial-modeling-prep-mcp` per crypto extended data
5. **Disclaimer obbligatorio** su ogni output

## Esempio proxy call

```python
# Discovery
aria-mcp-proxy__search_tools({"query": "crypto price bitcoin ethereum market data", "_caller_id": "trader-agent"})

# Esecuzione
aria-mcp-proxy__call_tool({
    "name": "financekit-mcp__crypto_price",
    "arguments": {"symbol": "BTC"},
    "_caller_id": "trader-agent"
})
```

## Output strutturato

```
# Crypto Analysis: <SYMBOL>

## Price Overview
<Price: $XX,XXX, 24h: +X.X%>
<Market Cap: $X.XXB, Volume: $XXXM>
<ATH: $XXX,XXX (XX% from ATH)>

## Technicals
<RSI: XX, MACD: bullish/bearish>
<Trend: bullish/bearish/neutral>

## On-Chain Metrics
<funding rate, exchange flow, whale activity>

## Bitcoin/Ethereum Correlation
<correlation with BTC/ETH>

## Risk Assessment
<volatility, drawdown risk, liquidity>

## Overall Signal
<BUY/SELL/HOLD con confidence>
```