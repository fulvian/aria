# Findings: Debug Completo Trader-Agent

## 1. Panoramica Fonti Analizzate

| Fonte | Tipo | Scopo |
|-------|------|-------|
| `docs/analysis/trader_agent_session_analysis_2026-05-03.md` | Report analisi | Gap analysis della sessione reale |
| `docs/llm_wiki/wiki/trader-agent.md` v1.4 | Wiki | Stato attuale e gap noti |
| `docs/llm_wiki/wiki/mcp-proxy.md` | Wiki | Contratto proxy, naming, fasi implementazione |
| `docs/llm_wiki/wiki/agent-coordination.md` | Wiki | Sistema L1: HandoffRequest, ContextEnvelope, SpawnValidator |
| `docs/llm_wiki/wiki/observability.md` | Wiki | Tracciamento trace_id, metriche, eventi |
| `.aria/kilocode/agents/trader-agent.md` (267 linee) | Prompt agente | Istruzioni, tool, frontmatter |
| `.aria/kilocode/agents/aria-conductor.md` | Prompt conductor | Dispatch rules, spawn-subagent usage |
| `.aria/config/agent_capability_matrix.yaml` | Config | allowed_tools, delegation, hitl_triggers |
| `.aria/config/mcp_catalog.yaml` | Catalog | Backend finanziari e relativi stati |
| `.aria/kilocode/mcp.json` | Config | 2 entries: aria-memory + aria-mcp-proxy |
| `src/aria/mcp/proxy/server.py` | Source | build_proxy, _tool_server_name, _load_backends |
| `src/aria/mcp/proxy/broker.py` | Source | LazyBackendBroker, resolve_server_from_tool |
| `src/aria/mcp/proxy/middleware.py` | Source | CapabilityMatrixMiddleware, fail-closed, _caller_id |
| `src/aria/agents/coordination/registry.py` | Source | YamlCapabilityRegistry, wildcard matching |
| `src/aria/agents/coordination/spawn.py` | Source | spawn_subagent_validated validator |
| `src/aria/agents/coordination/handoff.py` | Source | HandoffRequest Pydantic model |
| `tests/unit/mcp/proxy/test_broker.py` | Tests | 63 unit test broker + middleware |
| `tests/unit/mcp/proxy/test_middleware.py` | Tests | Two-pass flow, _caller_id propagation |
| `.aria/kilocode/skills/trading-analysis/SKILL.md` | Skill | Orchestratore pipeline analisi |
| `.aria/kilocode/skills/fundamental-analysis/SKILL.md` | Skill | Analisi fondamentale |

---

## 2. RCA #1: FMP MCP Disabilitato (HTTP/SSE)

### Stato attuale

| Backend | Trasporto | Stato | Tool | Catalogo |
|---------|-----------|-------|------|----------|
| `financekit-mcp` | stdio (uvx) | ✅ ENABLED | 12+ | `mcp_catalog.yaml` |
| `mcp-fredapi` | stdio (Python) | ✅ ENABLED | 3 | `mcp_catalog.yaml` |
| `alpaca-mcp` | stdio (Python) | ✅ ENABLED | 22+ | `mcp_catalog.yaml` |
| `financial-modeling-prep-mcp` | HTTP/SSE | ❌ DISABLED | 253+ | `mcp_catalog.yaml lifecycle: disabled` |
| `helium-mcp` | HTTP/streamable | ❌ DISABLED | 9 | `mcp_catalog.yaml lifecycle: disabled` |

### Root cause

`financial-modeling-prep-mcp` e `helium-mcp` usano trasporto HTTP/SSE. Il proxy (`aria-mcp-proxy`) usa esclusivamente trasporto `stdio` per le connessioni backend. La funzione `LazyBackendBroker._get_or_create()` chiama `create_proxy()` di FastMCP che supporta solo configurazioni `mcpServers` stdio.

### Impatto

- **FMP MCP**: 253+ tool fondamentali/tecnici non accessibili. Le abilità `fundamental-analysis` e `technical-analysis` nei loro SKILL.md citano FMP come fonte primaria, ma non è disponibile.
- **Helium MCP**: News/sentiment/options non accessibili. Le abilità `sentiment-analysis` e `options-analysis` nei loro SKILL.md citano Helium come fonte primaria, ma non è disponibile.
- **Copertura effettiva**: Solo il 30% circa della copertura dati finanziaria desiderata è disponibile.

### Fix potenziali

1. **Wrapper stdio**: Creare script wrapper che traduce HTTP/SSE in stdio (es. `financial-modeling-prep-wrapper.sh`)
2. **FastMCP update**: Verificare se FastMCP supporta già HTTP/SSE nativamente
3. **mcp-gateway**: Usare `mcp-gateway` come intermediario HTTP→stdio
4. **Dual proxy**: Proxy separato per HTTP/SSE backends

### Verifica Context7

Da verificare: FastMCP supporta trasporto HTTP/SSE per `create_proxy`?

---

## 3. RCA #2: KiloCode `task` vs ARIA `spawn-subagent`

### Meccanismo di dispatch attuale

Il conductor usa `spawn-subagent` (tool nativo) per delegare ai sub-agenti. Il formato attuale del payload non include `HandoffRequest` validato:

```json
{
  "goal": "task description",
  "constraints": "vincoli (opzionale)",
  "required_output": "formato atteso (opzionale)",
  "timeout": 120,
  "trace_id": "trace_<descrizione>"
}
```

### Cosa prevede l'architettura L1

```python
class HandoffRequest(BaseModel):
    goal: str = Field(..., max_length=500)
    constraints: str | None = None
    required_output: str | None = None
    timeout_seconds: int = Field(default=120, ge=10, le=300)
    trace_id: str
    parent_agent: str
    spawn_depth: int = Field(default=1, ge=1, le=2)
    envelope_ref: str | None = None
```

Il validator `spawn_subagent_validated()` esiste ma **NON viene chiamato** perché non è integrato nel flusso del conductor. Il conductor invoca direttamente `spawn-subagent` tool senza passare dalla validazione ARIA.

### Problema critico: visibilità tool proxy in sub-sessione

La domanda centrale è: **quando il conductor spawna il trader-agent tramite KiloCode, il sub-agente vede i tool del proxy (`aria-mcp-proxy_search_tools` / `aria-mcp-proxy_call_tool`)?**

Evidenze:
- `mcp.json` ha `aria-mcp-proxy` configurato
- `trader-agent.md` frontmatter dichiara `mcp-dependencies: [aria-mcp-proxy, aria-memory]`
- I tool `aria-mcp-proxy_search_tools` e `aria-mcp-proxy_call_tool` sono elencati in `allowed-tools`
- **Tuttavia**: La sessione reale mostra ZERO chiamate proxy

Ipotesi diagnostica:
1. **Strangling**: I tool proxy sono VISIBILI ma il modello LLM non li chiama (preferisce conoscenza interna)
2. **Invisibilità**: I tool proxy NON sono visibili nella tool list del sub-agente KiloCode
3. **Timeout**: Il sub-agent tenta chiamate proxy che vanno in timeout (620.5s di latenza supporta questa ipotesi)

### `_tool_server_name()` verification

```python
_tool_server_name("financekit-mcp_*")  → "financekit-mcp" ✅ (hyphen ok)
_tool_server_name("google_workspace_*") → "google" ❌ (underscore in server name!)
```

BUG CONFERMATO: `_tool_server_name()` per `google_workspace_*` estrae `"google"` invece di `"google_workspace"`. Questo causa **backends filtrati erroneamente** quando `ARIA_CALLER_ID` è impostato.

Per il trader-agent non è un problema (nomi senza underscore), ma per productivity-agent/workspace-agent è un bug attivo.

---

## 4. RCA #3: Verifica Runtime Uso Proxy

### Stato attuale

- `CapabilityMatrixMiddleware` verifica che i tool chiamati siano nella `allowed_tools` dell'agente
- Il middleware è **fail-closed**: se l'identità chiamante è assente, nega tool non sintetici
- **Non esiste** un meccanismo che verifichi se l'agente ha effettivamente chiamato `search_tools`/`call_tool`

### Gap

Il prompt dice "usa il proxy per tutte le operazioni finanziarie" ma:
1. L'agente può produrre output senza chiamare alcun tool
2. Non c'è un guard runtime che obblighi l'uso del proxy
3. Il conductor non verifica la presenza di chiamate proxy nell'output dell'agente

### Impatto

L'agente produce analisi basate su conoscenza LLM (dati non live), passando inosservato.

---

## 5. Proxy Middleware Flow Corretto

Dopo l'analisi del codice, il flusso a due passaggi del middleware è confermato corretto:

```
Pass 1: LLM → call_tool({name: "financekit-mcp_...", arguments: {_caller_id: "trader-agent"}})
  → Middleware: estrae _caller_id, re-inietta in arguments nidificati
  → _call_tool(): _strip_caller_id() rimuove _caller_id
  → broker.call(server, tool, clean_args)

Pass 2: broker → FastMCP.create_proxy(single-backend)
  → Chiama tool backend senza _caller_id (già rimosso)
```

Questo flusso è corretto e testato (`test_middleware.py` → `test_two_pass_call_tool_preserves_caller_into_backend_pass`).

---

## 6. Gap Aggiuntivi Scoperti

### Gap A.1: Conductor non passa `trace_id` strutturato

Il conductor usa `"trace_id": "trace_<descrizione>"` (stringa informale) invece di UUIDv7. Questo viola L4 (observability.md §2).

### Gap A.2: Skill pipeline mai attivata

7 skills esistono (`trading-analysis`, `fundamental-analysis`, `technical-analysis`, `macro-intelligence`, `sentiment-analysis`, `options-analysis`, `crypto-analysis`) ma non vengono mai caricate dal trader-agent. Il prompt del trader-agent non dice di caricarli, e il meccanismo `required-skills` nel frontmatter non è supportato dal runtime KiloCode.

### Gap A.3: Capability matrix `mcp-dependencies` non risolte dal conductor per `spawn-subagent`

Il conductor ha `mcp-dependencies: [aria-memory, aria-mcp-proxy]`, ma quando spawna trader-agent, non c'è garanzia che `aria-mcp-proxy` sia esposto al sub-agente.

### Gap A.4: `wiki_update_tool` chiamato dal conductor, non dal trader-agent

Il conductor esegue `wiki_update_tool` al termine della sessione, violando il principio che ogni agente gestisce la propria persistenza (GAP #7).

---

## 7. Conformità Backend Finanziari

### Backend abilitati

| Backend | Tool principali | API Key | Coverage |
|---------|----------------|---------|----------|
| `financekit-mcp` | stock_price, stock_quote, technical_analysis, crypto_*, etf_info, market_indices, treasury_rates | keyless | Free, 12+ tool |
| `mcp-fredapi` | get_fred_series_observations, get_fred_series_search, get_fred_series_info | FRED_API_KEY (SOPS) | Macro (tassi, CPI, NFP) |
| `alpaca-mcp` | get_stock_bars, get_stock_quote, get_stock_snapshot, get_option_chain, get_crypto_*, get_news | ALPACA_API_KEY (SOPS) | Market data, opzioni, news |

### Backend disabilitati

| Backend | Tool | Coverage mancante |
|---------|------|-------------------|
| `financial-modeling-prep-mcp` ⛔ | 253+ tool | Financial statements, DCF, analyst estimates, stock screener, rating, price target |
| `helium-mcp` ⛔ | 9 tool | News sentiment, bias analysis, options pricing, AI strategy |

### Copertura effettiva con backends ENABLED

| Dimensione analisi | Backend | Copertura |
|-------------------|---------|-----------|
| Quote prezzi stock/ETF | financekit-mcp + alpaca-mcp | ✅ OK |
| Dati storici | alpaca-mcp (bars) | ✅ OK |
| Analisi tecnica (RSI, MACD, SMA) | financekit-mcp (technical_analysis) | ✅ OK |
| Dati macro (tassi, CPI, GDP) | mcp-fredapi | ✅ OK |
| Crypto | financekit-mcp (crypto_*) | ✅ OK |
| Financial statements | ❌ NESSUNO (FMP disabilitato) | ❌ GAP |
| DCF, analyst estimates | ❌ NESSUNO (FMP disabilitato) | ❌ GAP |
| News sentiment | ❌ NESSUNO (Helium disabilitato) | ❌ GAP |
| Options chain/analysis | alpaca-mcp (parziale) | ⚠️ Parziale |
| Stock screener | ❌ NESSUNO (FMP disabilitato) | ❌ GAP |
| Rating/price target | ❌ NESSUNO (FMP disabilitato) | ❌ GAP |
