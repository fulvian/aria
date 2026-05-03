# Trader-Agent

**Status**: Active ✅ v1.4
**Last Updated**: 2026-05-02T09:18
**Branch**: current working tree

## Overview

`trader-agent` è il 4° sub-agente di dominio verticale di ARIA, specializzato in analisi finanziaria. È un **consulente di analisi**, NON un execution bot — non esegue trading reale, non fornisce consulenza finanziaria legale, e richiede HITL per raccomandazioni formali.

## Architettura di appartenenza

```
utente
  └─→ aria-conductor (orchestrator primario)
       ├─→ search-agent     (ricerca web generica)
       ├─→ productivity-agent (document workflow)
       ├─→ workspace-agent (Google Workspace — transitional)
       └─→ trader-agent      (NUOVO — analisi finanziaria)
```

## MCP Stack

Tutti i backend passano attraverso `aria-mcp-proxy` (NON in `mcp.json`).

### Backend abilitati (stdio — accessibili ora)

| MCP Server | Transport | Auth | Tool Count | Source |
|------------|-----------|------|------------|--------|
| **financekit-mcp** | stdio (uvx) | keyless | 12+ | `uvx --from financekit-mcp financekit` |
| **mcp-fredapi** | stdio (Python) | FRED_API_KEY | 3 | `/home/fulvio/coding/mcp-fredapi/` |
| **alpaca-mcp** | stdio (Python) | ALPACA_API_KEY/SECRET | 22+ | `/home/fulvio/coding/alpaca-mcp/` |

### Backend disabilitati (HTTP/SSE — Phase 2)

| MCP Server | Transport | Auth | Tool Count | Note |
|------------|-----------|------|------------|------|
| **financial-modeling-prep-mcp** | HTTP/SSE | API key | 253+ | Disabilitato — richiede estensione proxy HTTP |
| **helium-mcp** | HTTP/streamable | API key | 9 | Disabilitato — richiede estensione proxy HTTP |

### Credential Pipeline

```
SOPS api-keys.enc.yaml → CredentialManager.get(${VAR}) / .env fallback → CredentialInjector → subprocess env
```

- `FRED_API_KEY`: SOPS provider `fred` + `.env` fallback
- `ALPACA_API_KEY` + `ALPACA_API_SECRET`: SOPS provider `alpaca` (mode: paper) + `.env` fallback
- `financekit-mcp`: keyless, nessuna credenziale
- **Fix 2026-05-02**: il proxy crashava in boot perché `CredentialInjector` chiamava `CredentialManager.get(var)` ma il facade non esponeva `get()`. Ora il bridge esiste e registra alias env-style per i secret decryptati.

## Capability Matrix

Vedi `.aria/config/agent_capability_matrix.yaml` per la configurazione completa.

```yaml
name: trader-agent
type: worker
max_spawn_depth: 0  # Leaf agent
intent_categories:
  - finance.stock-analysis
  - finance.options-analysis
  - finance.macro-analysis
  - finance.sentiment
  - finance.crypto
  - finance.commodity
  - finance.comparison
  - finance.brief
hitl_triggers:
  - trading_recommendation_formal
  - exposure_gt_50k
  - asset_with_significant_exposure
```

## Skills (7)

| Skill | Version | Descrizione |
|-------|---------|-------------|
| `trading-analysis` | 1.0.0 | Orchestratore: ticker/asset → analisi multi-dimensionale → synthesis |
| `fundamental-analysis` | 1.0.0 | Earnings, statements, DCF, analyst estimates |
| `technical-analysis` | 1.0.0 | RSI, MACD, SMA/EMA, Bollinger, pattern, support/resistance |
| `macro-intelligence` | 1.0.0 | FRED, tassi, inflazione, NFP, GDP, correlazioni |
| `sentiment-analysis` | 1.0.0 | News scoring, bias, social sentiment aggregation |
| `options-analysis` | 1.0.0 | Catene opzioni, grecs, strategie, prob ITM |
| `crypto-analysis` | 1.0.0 | On-chain, DEX, funding rates, whale tracking |

## Proxy Invocation

Tutte le operazioni passano tramite `aria-mcp-proxy` con `_caller_id: "trader-agent"`.
Usa SEMPRE il formato `server_tool` (doppio underscore).

### Nota runtime Kilo

Nel runtime Kilo i tool del proxy possono apparire nella tool list come alias a underscore singolo:
- `aria-mcp-proxy_search_tools`
- `aria-mcp-proxy_call_tool`

Sono alias runtime dei nomi canonici documentati nel prompt/config (`aria-mcp-proxy_search_tools` / `aria-mcp-proxy_call_tool`).

### Nota `call_tool` / caller identity

Il proxy effettua due passaggi middleware quando un agente usa `call_tool`:
1. passaggio sintetico su `call_tool`
2. passaggio reale sul tool backend selezionato

Per questo `_caller_id` deve sopravvivere al passaggio 1 e venire rimosso solo
immediatamente prima della chiamata finale al backend. Questo bug è stato corretto
in v1.4 dopo una regressione reale sul trader-agent.

### Nota schema crypto

- `financekit-mcp_crypto_search` → risolve nome/simbolo in CoinGecko ID
- `financekit-mcp_crypto_price` → richiede `coin` (es. `bitcoin`, `ethereum`), **non** `symbol`
- `financekit-mcp_technical_analysis` → per crypto usa ticker stile Yahoo Finance (`BTC-USD`, `ETH-USD`)
- In caso di dubbio, la source of truth dei parametri è sempre `search_tools` → `inputSchema`

```python
# Discovery
aria-mcp-proxy_search_tools({"query": "stock quote", "_caller_id": "trader-agent"})

# Esecuzione
aria-mcp-proxy_call_tool({
    "name": "financekit-mcp_get_stock_data",
    "arguments": {"symbol": "AAPL"},
    "_caller_id": "trader-agent"
})
```

## Boundary e Non-Obiettivi

- **NON** esegue trading reale — consulente di analisi
- **NON** fornisce consulenza finanziaria legale
- **NON** gestisce wallet crypto o account exchange write
- **NON** fa execution — HITL richiesto per operazioni costose
- Tutte le raccomandazioni includono **disclaimer obbligatorio**

## Output Attesi

- **Trading Brief**: TL;DR → Context → Analysis → Risk → Recommendation
- **Ticker Comparison**: tabella comparativa multi-asset
- **Macro Dashboard**: sintesi indicatori macro chiave
- **Options Chain Analysis**: analisi catena opzioni con grecs
- **Sentiment Report**: news + social aggregated score

## HITL Triggers

- Richiesta esplicita di "trading recommendation" formale
- Analisi su asset con exposure > 50k€
- Operazioni che cambiano stato persistente

## Wiki Pages

| Page Kind | Azione | Frequenza |
|-----------|--------|-----------|
| `trading-brief` | CREATE on-demand | Ogni analisi richiesta |
| `ticker-<symbol>` | UPDATE/CREATE | Analisi ripetute su stesso ticker |
| `macro-snapshot` | CREATE | Dashboard macro periodiche |
| `lesson` | CREATE (HITL) | Regole apprese da risultati trading |

## Fonte di Verità

- Piano: `docs/plans/agents/trader_agent_foundation_plan.md`
- ADR: `docs/foundation/decisions/ADR-00XX-trader-agent-introduction.md`
- Protocollo: `docs/protocols/protocollo_creazione_agenti.md`
- Skill tree: `.aria/kilocode/skills/{trading-analysis,fundamental-analysis,technical-analysis,macro-intelligence,sentiment-analysis,options-analysis,crypto-analysis}/SKILL.md`
