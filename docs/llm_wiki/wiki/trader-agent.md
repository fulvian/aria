# Trader-Agent

**Status**: Active ✅ v1.1
**Last Updated**: 2026-05-02T02:22
**Branch**: `fix/trader-agent-recovery`

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

| MCP Server | Transport | Stato | Auth | Tool Count | Source |
|------------|-----------|-------|------|------------|--------|
| **financekit-mcp** | stdio (uvx) | ✅ enabled | keyless | 12+ | `uvx --from financekit-mcp financekit` |
| **mcp-fredapi** | stdio (Python) | ✅ enabled | FRED_API_KEY | 3 | `/home/fulvio/coding/mcp-fredapi/` |
| **alpaca-mcp** | stdio (Python) | ✅ enabled | ALPACA_API_KEY/SECRET | 22+ | `/home/fulvio/coding/alpaca-mcp/` |
| **financial-modeling-prep-mcp** | HTTP/SSE | ❌ disabled | API key | 253+ | Phase 2 (proxy HTTP extension) |
| **helium-mcp** | HTTP/streamable | ❌ disabled | API key | 9 | Phase 2 (proxy HTTP extension) |

### Credential Pipeline

```
SOPS api-keys.enc.yaml → .env (gitignored) → CredentialInjector (${VAR}) → subprocess env
```

- `FRED_API_KEY`: SOPS provider `fred` + `.env` fallback
- `ALPACA_API_KEY` + `ALPACA_API_SECRET`: SOPS provider `alpaca` (mode: paper) + `.env` fallback
- `financekit-mcp`: keyless, nessuna credenziale

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

Tutte le operazioni passano tramite `aria-mcp-proxy` con `_caller_id: "trader-agent"`:

```python
# Discovery
aria-mcp-proxy__call_tool("search_tools", {"query": "stock quote", "_caller_id": "trader-agent"})

# Esecuzione
aria-mcp-proxy__call_tool("call_tool", {
    "name": "financial-modeling-prep-mcp/get_stock_data",
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