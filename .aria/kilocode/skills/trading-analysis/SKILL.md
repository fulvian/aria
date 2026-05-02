---
name: trading-analysis
version: 1.0.0
description: Orchestratore principale — riceve ticker/asset → analisi multi-dimensionale (fondamentale, tecnica, macro, sentiment) → synthesis con trading brief strutturato
trigger-keywords: [trading, analisi, ticker, asset, stock, ETF, borsa, mercato, quotazione, prezzo]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - aria-memory__wiki_update_tool
  - aria-memory__wiki_recall_tool
  - hitl-queue__ask
  - sequential-thinking__*
max-tokens: 80000
estimated-cost-eur: 0.15
---

# Trading Analysis Skill

## Obiettivo

Orchestrare un'analisi finanziaria multi-dimensionale su uno o più ticker/asset
e produrre un Trading Brief strutturato.

## Pipeline di analisi

### Fase 1 — Input e intent classification
1. Identifica il tipo di richiesta:
   - `finance.stock-analysis` — analisi singolo/multiple stock/ETF
   - `finance.options-analysis` — catene opzioni, strategie, grecs
   - `finance.macro-analysis` — indicatori macroeconomici
   - `finance.sentiment` — news + social sentiment
   - `finance.crypto` — crypto/DeFi analysis
   - `finance.commodity` — commodity futures
   - `finance.comparison` — comparazione multi-asset
   - `finance.brief` — trading brief strutturato

2. Recupera contesto storico: `wiki_recall_tool(query=<ticker + context>)`
3. Se l'utente richiede esplicitamente il salvataggio, prepara `wiki_update_tool` alla fine

### Fase 2 — Analisi multi-dimensionale
Per ogni dimensione appropriata, chiama i tool dei MCP finanziari via proxy:

**Fondamentale** (financial-modeling-prep-mcp):
- Quote attuale, variazioni, volume, P/E, market cap
- Financial statements (income, balance sheet, cash flow)
- Analyst estimates e target price
- DCF e ratio di valutazione

**Tecnica** (financekit-mcp):
- RSI(14), MACD, Bollinger Bands
- SMA/EMA (50, 200)
- Pattern detection (Golden Cross, Death Cross)
- Support/resistance levels

**Macro** (mcp-fredapi):
- Treasury yields (2Y, 10Y, 30Y)
- CPI, PPI, NFP, GDP
- Federal Reserve policy indicators

**Sentiment** (helium-mcp):
- News score e bias analysis
- Social sentiment aggregation
- Source credibility assessment

**Options** (helium-mcp, financial-modeling-prep-mcp):
- IV rank, volatility surface
- Option chain analysis
- Prob ITM, Greeks

**Crypto** (financekit-mcp, financial-modeling-prep-mcp):
- Price, market cap, 24h change
- Funding rates, whale tracking

### Fase 3 — Synthesis
Combina le analisi dimensionali in un Trading Brief strutturato:

```
# Trading Brief: <TICKER>

## TL;DR
<1-2 frasi di sintesi>

## Context
<Situazione attuale e driver principali>

## Analysis
### Fondamentale
<Risultati analisi fondamentale>
### Tecnica
<Segnali tecnici con indicatori>
### Macro
<Contesto macro rilevante>
### Sentiment
<News e social sentiment>

## Risk
<Rischi identificati>

## Recommendation
<Raccomandazione strutturata>
---
⚠️ DISCLAIMER: Le informazioni prodotte da questo agente sono per scopi
di analisi e ricerca ONLY. Non costituiscono consulenza finanziaria,
sollecitazione all'investimento, o raccomandazione di trading.
Tutti gli investimenti comportano rischio. Consulta un professionista
qualificato prima di prendere decisioni di investimento.
---
```

## Regole operative

1. **Usa SEMPRE il proxy** (`aria-mcp-proxy__search_tools` / `aria-mcp-proxy__call_tool`)
   con `_caller_id: "trader-agent"`
2. **Nessun tool nativo host** (`Read`, `Write`, `Glob`) per operazioni finanziarie
3. **HITL** per raccomandazioni formali o analisi > 50k token
4. **Disclaimer obbligatorio** su ogni output con raccomandazione
5. **Wiki update** solo se l'utente richiede esplicitamente il salvataggio

## Esempio di chiamata proxy

```python
# Discovery
aria-mcp-proxy__search_tools({"query": "stock quote financial data", "_caller_id": "trader-agent"})

# Esecuzione
aria-mcp-proxy__call_tool({
    "name": "financekit-mcp__get_stock_data",
    "arguments": {"symbol": "AAPL"},
    "_caller_id": "trader-agent"
})
```

> **Nota backend**: I backend attualmente abilitati via proxy sono `financekit-mcp`, `mcp-fredapi` e `alpaca-mcp` (stdio).
> `financial-modeling-prep-mcp` e `helium-mcp` sono HTTP/SSE, attualmente disabilitati (Phase 2).
> Quando disponibile, usa `financial-modeling-prep-mcp__<tool>` per dati fondamentali estesi.