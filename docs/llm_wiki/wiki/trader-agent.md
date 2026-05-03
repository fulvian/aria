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

## Session Audit (2026-05-03)

Il 3 maggio 2026 è stata condotta un'analisi completa della prima sessione utente reale del trader-agent (portfolio analysis + rebalancing + stock picks). Risultati:

**Score architetturale: 4/14 obblighi soddisfatti (31%)**

### Gap principali identificati

| # | Gap | Gravità | Fix richiesto |
|---|---|---|---|
| 1 | Nessun uso del proxy MCP per dati live — dati prodotti da LLM knowledge, non da backends | 🔴 CRITICAL | P0.3: diagnosticare visibilità tool proxy in sub-sessione |
| 2 | FMP MCP (253+ tool, cornerstone) e Helium MCP disabilitati (HTTP/SSE Phase 2) | 🔴 CRITICAL | P0.1/P0.2: abilitare via wrapper stdio o mcp-gateway |
| 3 | Nessuna classificazione intent (Fase 1 del workflow saltata) | 🟡 HIGH | P1.4: hard gate nel prompt |
| 4 | Formato output non conforme al Trading Brief template | 🟡 HIGH | P1.5: template obbligatorio |
| 5 | Dispatch via `task` KiloCode, non `spawn-subagent` ARIA + HandoffRequest | 🟡 HIGH | P1.2: adottare coordinamento ARIA |
| 6 | wiki_update fatto dal conductor, non dal trader-agent | 🟡 HIGH | P1.3: correggere flusso |
| 7 | Nessuna propagazione trace_id | 🟡 HIGH | P2.3: strumento UUIDv7 |
| 8 | 620.5s di latenza per task singolo | 🟢 LOW | P2.1: audit performance |

### Report completo
`docs/analysis/trader_agent_session_analysis_2026-05-03.md`

### Debug completo (2026-05-03)

Il 3 maggio 2026 è stato condotto un debug completo del trader-agent basato sul report di analisi. Risultati:

**Bug trovati: 6** (3 critici, 2 medi, 1 minore)

| ID | Bug | File | Impatto | Priorità |
|----|-----|------|---------|----------|
| **B1** | `to_mcp_entry()` ignora `transport` field | `catalog.py:76-82` | HTTP/SSE backends (FMP 253+ tool, Helium) NON possono MAI funzionare | 🔴 P0 |
| **B2** | `_tool_server_name()` split errato per underscore | `server.py:147-152` | `google_workspace_*` → server `"google"` (solo productivity-agent) | 🔴 P0 |
| **B3** | `spawn_subagent_validated()` mai integrato | `spawn.py` / conductor prompt | Layer L1 bypassato: no HandoffRequest, no ContextEnvelope, no trace_id | 🔴 P1 |
| **B4** | Nessun guard runtime proxy usage | middleware / conductor | Agente produce analisi senza proxy, nessuno lo rileva | 🟡 P1 |
| **B5** | Intent classification saltata | prompt trader-agent | Fase 1 del workflow sempre ignorata | 🟡 P2 |
| **B6** | 7 skills MAI caricate | skill files / runtime | Skills esistono ma non vengono mai attivate | 🟡 P2 |

**Scoperta critica (Context7)**: FastMCP `create_proxy` **supporta nativamente HTTP/SSE** con formato `{"url": "...", "transport": "http"}`. Il fix B1 permette di abilitare FMP MCP e Helium MCP SENZA wrapper stdio, semplicemente correggendo `to_mcp_entry()`.

**Report completo**: `docs/debug/trader_agent_debug_report_2026-05-03.md`

### Lezioni per future iterazioni
1. I backend MCP cornerstone devono essere abilitati PRIMA di testare funzionalità avanzate
2. Il sub-agente KiloCode `task` bypassa tutto il layer L1 di coordinamento ARIA
3. Prompt engineering senza runtime enforcement è insufficiente per garantire uso proxy
4. Il template Trading Brief standardizzato deve essere parsabile e validabile
5. **Fix B1** (to_mcp_entry HTTP) è il prerequisito per qualsiasi analisi con dati live — senza FMP MCP, il trader-agent non ha copertura fondamentale

## Fonte di Verità

- Piano: `docs/plans/agents/trader_agent_foundation_plan.md`
- ADR: `docs/foundation/decisions/ADR-00XX-trader-agent-introduction.md`
- Protocollo: `docs/protocols/protocollo_creazione_agenti.md`
- Skill tree: `.aria/kilocode/skills/{trading-analysis,fundamental-analysis,technical-analysis,macro-intelligence,sentiment-analysis,options-analysis,crypto-analysis}/SKILL.md`
- Audit report: `docs/analysis/trader_agent_session_analysis_2026-05-03.md`
