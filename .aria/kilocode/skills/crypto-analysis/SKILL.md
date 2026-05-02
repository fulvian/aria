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

| Fonte | Tool | Dati | Parametri chiave |
|-------|------|------|-------------------|
| financekit-mcp | `crypto_search` | Cerca coin per nome/symbol → restituisce CoinGecko ID | `query` (nome o simbolo) |
| financekit-mcp | `crypto_price` | Price, market cap, 24h change, ATH | `coin` (CoinGecko ID, es. "bitcoin") |
| financekit-mcp | `crypto_trending` | Top trending coins | — |
| financekit-mcp | `crypto_top_coins` | Top N by market cap | `limit` |
| financekit-mcp | `crypto_technical_analysis` | RSI, MACD, Bollinger su crypto | `symbol` (ticker: `BTC-USD`, `ETH-USD`) |
| helium-mcp | `get_ticker` | BTC, ETH con bull/bear case | — |
| financial-modeling-prep-mcp | Crypto data | Extended crypto coverage | — |

> **⚠️ IMPORTANTE**: I nomi dei tool nel runtime usano underscore singolo
> (es. `financekit-mcp_crypto_price`), non doppio. Controlla sempre `search_tools`
> per i nomi effettivi disponibili e usa il formato restituito dalla discovery.

## Pipeline

### Fase 0 — Symbol Resolution (OBBLIGATORIO)
**NON passare direttamente un symbol/ticker a `crypto_price`.** Il parametro `coin`
richiede il **CoinGecko ID** (es. "bitcoin", "ethereum"), NON il simbolo ("BTC").

```
Se l'input è un symbol/nome (es. "BTC", "bitcoin", "ethereum"):
  1. search_tools("crypto search", _caller_id="trader-agent")
  2. call_tool("financekit-mcp_crypto_search", {query: "BTC"}, _caller_id="trader-agent")
  3. Estrai il campo `id` dal risultato → questo è il `coin` per crypto_price
```

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
6. **Schema-first**: usa SEMPRE `search_tools` per verificare i parametri
   effettivi dei tool backend. NON assumere parametri basandoti su vecchie
   versioni o supposizioni. Il campo `inputSchema` restituito da search_tools
   è la source of truth.
7. **crypto_price** richiede `coin` (CoinGecko ID, es. "bitcoin"), NON `symbol`.
   Se hai solo il simbolo, usa `crypto_search` prima per ottenere l'ID.
8. **crypto_technical_analysis** accetta ticker in formato Yahoo Finance
   (es. `BTC-USD`, `ETH-USD`), NON CoinGecko ID.

## Esempio proxy call

Nel runtime Kilo i tool del proxy possono apparire come alias
`aria-mcp-proxy_search_tools` / `aria-mcp-proxy_call_tool`.

```python
# Discovery — verifica sempre i nomi effettivi dei tool
aria-mcp-proxy__search_tools({"query": "crypto price search technical analysis", "_caller_id": "trader-agent"})

# Step 1: Risolvi symbol → CoinGecko ID (OBBLIGATORIO prima di crypto_price)
aria-mcp-proxy__call_tool({
    "name": "financekit-mcp_crypto_search",
    "arguments": {"query": "BTC"},
    "_caller_id": "trader-agent"
})
# Risultato contiene id="bitcoin" → usare come parametro `coin`

# Step 2: Prezzo con CoinGecko ID (NON symbol)
aria-mcp-proxy__call_tool({
    "name": "financekit-mcp_crypto_price",
    "arguments": {"coin": "bitcoin"},
    "_caller_id": "trader-agent"
})

# Step 3: Analisi tecnica con ticker formato Yahoo (BTC-USD, ETH-USD)
aria-mcp-proxy__call_tool({
    "name": "financekit-mcp_technical_analysis",
    "arguments": {"symbol": "BTC-USD"},
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
