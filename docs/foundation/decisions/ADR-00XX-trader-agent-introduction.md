# ADR-00XX: Trader Agent — Financial Analysis Sub-Agent

**Status**: Proposed
**Date**: 2026-05-02
**Authors**: fulvio
**Related**: ADR-0008 (productivity-agent), ADR-0015 (FastMCP native proxy),
             ADR-00XX (trader-agent-introduction)

## Context

Blueprint §8 prevede che ARIA espanda i sub-agenti di dominio verticale.
L'utente richiede un agente esperto di finanza: stock, ETF, materie prime, crypto,
futures e derivati, con accesso a informazioni fondamentali, macroeconomiche e di
sentiment, capace di produrre analisi strutturate per decisioni di trading.

Il dominio trading è **autonomo e coerente**: analisi fondamentale + tecnica +
sentiment costituisce un ciclo chiuso, con skill e tool specificityhe proprie,
non overlapping con `search-agent` (web search generico) o `productivity-agent`
(document workflow).

## Decision

Introduzione `trader-agent` come 4° sub-agente operativo:

### Stack MCP (P8 Tool Priority Ladder)

| MCP Server | Tipo | Priorità | API Key | Tool Count |
|------------|------|----------|---------|------------|
| **Financial Modeling Prep MCP** | npm | PRIMARY | SÌ (free tier) | 253+ |
| **Helium MCP** | HTTP/SSE | PRIMARY | No | 9 |
| **mcp-fredapi (FRED)** | Python | PRIMARY | No (richiede key) | 1 |
| **financekit-mcp** | Python | SECONDARY | No | 12 |
| **Alpaca MCP** | npm | EXECUTION-only | SÌ | market data |

- **Nessun Python locale necessario** — tutti i requirement coperti dai MCP
- **Financial Modeling Prep MCP** è il cornerstone: 253+ tool che coprono
  stocks, ETF, options, futures, crypto, forex, commodities, macro, fundamentals,
  technicals, news, SEC, analyst estimates

### Boundary dell'agente

- **NON** esegue trading reale — consulente di analisi, non execution bot
- **NON** fornisce consulenza finanziaria legale — analisi strutturata
- **NON** gestisce wallet crypto o account exchange write
- **NON** fa execution — operazioni di trading richiedono HITL esplicito
- Tutte le raccomandazioni includono disclaimer obbligatorio

### Intent categories

- `finance.stock-analysis` — analisi singolo/multiple stock/ETF
- `finance.options-analysis` — catene opzioni, strategie, grecs
- `finance.macro-analysis` — indicatori macroeconomici
- `finance.sentiment` — news + social sentiment
- `finance.crypto` — crypto/DeFi analysis
- `finance.commodity` — commodity futures
- `finance.comparison` — comparazione multi-asset
- `finance.brief` — trading brief strutturato

### Skills (7 nuove)

| Skill | Version | Descrizione |
|-------|---------|-------------|
| `trading-analysis` | 1.0.0 | Orchestratore: ticker → analisi multi-dimensionale → synthesis |
| `fundamental-analysis` | 1.0.0 | Earnings, statements, DCF, analyst estimates |
| `technical-analysis` | 1.0.0 | Indicatori (RSI, MACD, SMA, EMA, BB), pattern, support/resistance |
| `macro-intelligence` | 1.0.0 | FRED, tassi, inflazione, correlazioni |
| `sentiment-analysis` | 1.0.0 | News scoring, bias, social sentiment aggregation |
| `options-analysis` | 1.0.0 | Catene opzioni, grecs, strategie base |
| `crypto-analysis` | 1.0.0 | On-chain, DEX, funding rates, whale tracking |

### HITL triggers

- Operazioni di write su exchange (disabilitato per ora)
- Analisi su asset con exposure > 50k€ (budget gate)
- Richiesta esplicita di "trading recommendation" come output formale
- Operazioni che cambiano stato (wiki write escluso — solo display)

## Consequences

**Positivi**:
- +1 nuovo dominio verticale (autonomo e coerente)
- MCP stack scelto per P8 ladder: tutti i requirement coperti da server maturi
- 253+ tool da FMP MCP come cornerstone
- 7 skill nuove per analisi multi-dimensionale
- Output strutturato (trading brief, ticker comparison, macro dashboard)

**Negativi**:
- Aumento complessità MCP ecosystem (+4 server)
- Dipendenza da API key esterne (FMP, Alpaca)
- Rischio di over-analysis senza actionability

## Alternatives considered

- **Yahoo Finance MCP**: molti server, non affidabili, rate-limiting Yahoo → REJECTED
- **Binance MCP / ccxt-mcp**: execution → out of scope per ora
- **Python locale per analysis**: MCP copre tutto, Python non necessario → REJECTED
- **Skill unica instead of 7**: ogni dimensione (fundamental, technical, macro,
  sentiment) richiede specializzazione → 7 skill separate per chiarezza

## References

- `docs/plans/agents/trader_agent_foundation_plan.md`
- Financial Modeling Prep: `/websites/site_financialmodelingprep_developer`
- Helium MCP: `github.com/connerlambden/helium-mcp`
- FRED API: `/websites/fred_stlouisfed_api_fred`
- FinanceKit MCP: `github.com/vdalhambra/financekit-mcp`
- TradingAgents (TauricResearch) — ispiratore per multi-agent trading framework
- Protocollo: `docs/protocols/protocollo_creazione_agenti.md`