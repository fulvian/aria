# Report di Debug Completo: Trader-Agent

**Data debug:** 2026-05-03  
**Branch:** `fix/trader-agent-recovery`  
**Source analisi:** `docs/analysis/trader_agent_session_analysis_2026-05-03.md`  
**Documenti consultati:** LLM Wiki (7 pagine), prompt agente (2), codice sorgente (10 files), test (2 suites), configurazioni (3 files), Context7/FastMCP docs

---

## Indice

1. [Executive Summary](#1-executive-summary)
2. [Bug Trovati](#2-bug-trovati)
3. [Root Cause Analysis Dettagliata](#3-root-cause-analysis-dettagliata)
4. [Fix Plan Priorizzato](#4-fix-plan-priorizzato)
5. [Roadmap Implementativa](#5-roadmap-implementativa)
6. [Appendice: Test di Verifica](#6-appendice-test-di-verifica)

---

## 1. Executive Summary

L'analisi approfondita del trader-agent ha identificato **6 bug attivi** e **8 gap architetturali** che collettivamente spiegano lo score di conformità del 31%. Il debug ha richiesto l'analisi di 25+ file tra codice, configurazioni, test e documentazione, oltre alla verifica Context7 delle capacità di FastMCP.

### I 3 bug più critici

| # | Bug | File | Impatto | Fix |
|---|-----|------|---------|-----|
| **B1** | `to_mcp_entry()` ignora `transport` field | `catalog.py:76-82` | HTTP/SSE backends (FMP, Helium) NON possono MAI essere usati anche se abilitati | ~2h |
| **B2** | `_tool_server_name()` split errato per server con underscore | `server.py:147-152` | `google_workspace_*` → server `"google"` ❌, backends filtrati erroneamente con `ARIA_CALLER_ID` | ~30min |
| **B3** | `spawn_subagent_validated()` mai integrato nel flusso | `spawn.py` / `aria-conductor.md` | Tutto il layer L1 bypassato: no HandoffRequest, no ContextEnvelope, no trace_id, no depth guard | ~3h |

### Score di scoperta

| Metrica | Valore |
|---------|--------|
| Bug attivi nel codice | **6** (3 critici, 2 medi, 1 minore) |
| Gap architetturali | **8** (da report analisi originale) |
| Fix con verifica Context7 | **2** (FastMCP create_proxy HTTP/SSE, RemoteMCPServer) |
| Backend che funzionano | **3/5** (financekit-mcp, mcp-fredapi, alpaca-mcp) |
| Backend riparabili con fix B1 | **+2** (FMP 253+ tool, Helium 9 tool) |

---

## 2. Bug Trovati

### 🔴 B1 — `BackendSpec.to_mcp_entry()` ignora HTTP transport (CRITICAL)

**File**: `src/aria/mcp/proxy/catalog.py:76-82`  
**Scoperto da**: Analisi codice + Context7 FastMCP docs

```python
def to_mcp_entry(self) -> dict[str, Any]:
    entry: dict[str, Any] = {"command": self.command, "args": list(self.args)}
    if self.env:
        entry["env"] = dict(self.env)
    return entry  # ← IGNORA self.transport!
```

**Problema**: Il metodo genera SOLO entry `command+args` (stdio), anche per backends con `transport: http`. FastMCP `create_proxy` supporta nativamente HTTP/SSE con formato `url+transport`, ma `to_mcp_entry()` non lo produce mai.

**Evidenza Context7**: FastMCP supporta:
- `{"mcpServers": {"s": {"url": "...", "transport": "http"}}}` — per HTTP
- `{"mcpServers": {"s": {"command": "...", "args": [...]}}}` — per stdio

**Impatto**: `financial-modeling-prep-mcp` (253+ tool) e `helium-mcp` (9 tool) non possono funzionare anche se abilitati. Il fix permette di usarli senza wrapper stdio.

**Fix**:
```python
def to_mcp_entry(self) -> dict[str, Any]:
    if self.transport == "http" or self.transport == "sse":
        # For HTTP/SSE backends, use url + transport format
        return {"url": self.source_of_truth, "transport": self.transport}
    entry: dict[str, Any] = {"command": self.command, "args": list(self.args)}
    if self.env:
        entry["env"] = dict(self.env)
    return entry
```

**Nota**: Richiede anche l'aggiunta di un campo `url` opzionale in `BackendSpec`, o l'uso di `source_of_truth` come URL per backends HTTP (Helium già ha URL in source_of_truth). Per FMP, serve il comando `npx fmp-mcp` — che avvia un server HTTP su localhost — quindi serve definire l'URL.

---

### 🔴 B2 — `_tool_server_name()` split errato per underscore (CRITICAL per productivity-agent)

**File**: `src/aria/mcp/proxy/server.py:147-152`  
**Scoperto da**: Simulazione Python dello split logic

```python
def _tool_server_name(tool_name: str) -> str | None:
    if "_" in cleaned:
        return cleaned.split("_", 1)[0] or None  # ← split al PRIMO underscore!
```

**Problema**: Per server names con underscore (es. `google_workspace`), lo split estrae solo il prefisso prima del primo underscore:
- `google_workspace_*` → `"google"` ❌ (dovrebbe essere `"google_workspace"`)
- `google-workspace_*` → `"google-workspace"` ✅ (hyphen funziona)

**Impatto**: Quando `ARIA_CALLER_ID` è impostato, backends con underscore nel nome vengono filtrati erroneamente. Colpisce `productivity-agent`/`workspace-agent` (google_workspace), NON il trader-agent (nomi con hyphen).

**Fix**: Usare longest-prefix matching simile a `resolve_server_from_tool()` in `broker.py`:

```python
@staticmethod
def _tool_server_name(tool_name: str, known_servers: set[str] | None = None) -> str | None:
    cleaned = tool_name.strip()
    if not cleaned or cleaned in DIRECT_SERVER_ALLOWLIST:
        return None
    if "_" in cleaned:
        if known_servers:
            # Try longest-prefix matching (handles underscores in server names)
            idx = 0
            while (idx := cleaned.find("_", idx)) != -1:
                candidate = cleaned[:idx]
                if candidate in known_servers:
                    return candidate
                idx += 1
        return cleaned.split("_", 1)[0] or None
    return None
```

**Sforzo**: 30 minuti

---

### 🔴 B3 — `spawn_subagent_validated()` mai integrato (CRITICAL)

**File**: `src/aria/agents/coordination/spawn.py` / `.aria/kilocode/agents/aria-conductor.md`  
**Scoperto da**: Analisi flusso dispatch nel report analisi (GAP #6)

**Problema**: Il conductor usa direttamente il tool `spawn-subagent` di KiloCode senza passare dalla validazione ARIA. La funzione `spawn_subagent_validated()` esiste ma NON viene mai chiamata.

**Conseguenze**:
1. **Nessun HandoffRequest validato** — payload free-form, no Pydantic validation
2. **Nessun ContextEnvelope** — wiki pages non propagate al sub-agente
3. **Nessun trace_id UUIDv7** — `"trace_id": "trace_<desc>"` (informale)
4. **Nessun depth guard** — spawn_depth non validato
5. **Nessun evento metrics** — `aria_agent_spawn_total` non emesso
6. **Nessuna validazione registry** — delegation non verificata

**Fix**: Integrare `spawn_subagent_validated()` nel conduttore PRIMA della chiamata `spawn-subagent`:

```python
# 1. Validate via ARIA layer
result = await spawn_subagent_validated(
    target_agent="trader-agent",
    handoff_request=HandoffRequest(
        goal="analisi portafoglio ETF",
        trace_id=str(uuid7()),  # ← UUIDv7
        parent_agent="aria-conductor",
        spawn_depth=1,
    ),
    registry=YamlCapabilityRegistry(),
)
if not result.success:
    raise RuntimeError(f"Spawn validation failed: {result.error}")

# 2. Actual spawn (now validated)
spawn-subagent({...})
```

**Sforzo**: 3 ore (integrare validator nel prompt del conductor + test)

---

### 🟡 B4 — Nessun guard runtime per proxy usage (HIGH)

**File**: Prompt `aria-conductor.md` / Nuovo meccanismo  
**Scoperto da**: Report analisi GAP #1 (nessuna chiamata proxy non rilevata)

**Problema**: Il trader-agent produce analisi senza chiamare MAI il proxy e nessun meccanismo lo rileva. Il middleware è fail-closed (blocca tool non autorizzati) ma non può obbligare l'agente a fare chiamate.

**Fix proposto**: Aggiungere nel conductor un guard post-analisi:

```python
# Dopo spawn-subagent, se output contiene metriche finanziarie
# ma tool proxy non sono stati chiamati, warning esplicito
if has_financial_metrics(agent_output) and not has_proxy_calls(session_log):
    output += "\n\n⚠️ **WARNING**: Questa analisi non contiene dati live da MCP proxy. "
    output += "I dati finanziari potrebbero non essere aggiornati."
```

**Sforzo**: 2 giorni (richiede parsing output + session log correlation)

---

### 🟡 B5 — Intent classification saltata (HIGH)

**File**: Prompt `trader-agent.md §108-117`  
**Scoperto da**: Report analisi GAP #3

**Problema**: Il prompt richiede esplicitamente intent classification (8 categorie: `finance.stock-analysis`, `finance.brief`, ecc.) ma l'agente salta completamente questa fase.

**Fix**: Inserire intent classification come **hard gate** — prima riga dell'output deve essere `Intent: finance.<categoria>`:

```
📋 Intent Classification
Intent: finance.brief + finance.comparison
Tickers: [QQQ, SPY, GLD, SCHD]
[...]
```

**Sforzo**: 30 minuti (modifica prompt)

---

### 🟡 B6 — 7 skills MAI caricate (HIGH)

**File**: `.aria/kilocode/skills/*/SKILL.md`  
**Scoperto da**: Report analisi GAP #5

**Problema**: 7 skills finanziarie esistono su filesystem ma non vengono MAI caricate. Il sistema `required-skills` nel frontmatter del prompt trader-agent non è supportato dal runtime KiloCode.

**Fix**: Aggiungere nel prompt del trader-agent un passaggio obbligatorio:

```
## Skill Loading (OBBlIGATORIO)

Prima di iniziare l'analisi, carica le skill rilevanti usando l'apposito tool.
Per analisi multi-dimensionale, carica:
- trading-analysis (orchestratore)
- fundamental-analysis (se analisi fondamentali)
- technical-analysis (se analisi tecnica)
- macro-intelligence (se contesto macro)
- sentiment-analysis (se news/social)
```

**Sforzo**: 1 ora (modifica prompt + test)

---

### 🟢 B7 — wiki_update fatto dal conductor (MEDIUM)

**File**: Flusso conductor → trader-agent  
**Scoperto da**: Report analisi GAP #7

**Problema**: Il conductor esegue `wiki_update_tool` invece del trader-agent. Questo viola il principio di persistenza attore-aware. Inoltre, il conductor ha scritto pagine wiki per flussi non conformi (dati non live).

**Fix**: Il trader-agent deve chiamare `wiki_update_tool` alla fine del proprio turno. Il conductor non deve fare wiki_update per conto del trader-agent.

### 🟢 B8 — Nessun trace_id UUIDv7 (MEDIUM)

**File**: `aria-conductor.md` (formato trace_id)  
**Scoperto da**: Report analisi GAP #8

**Problema**: Il conductor usa `"trace_id": "trace_<descrizione>"` (stringa informale). L'architettura L4 richiede UUIDv7 per correlazione eventi end-to-end.

**Fix**:
```python
import uuid

trace_id = str(uuid.uuid4())  # o uuid7() se disponibile
```

**Sforzo**: 30 minuti

---

## 3. Root Cause Analysis Dettagliata

### RCA #1 — Backend MCP insufficienti

**Catena causale**:

```
to_mcp_entry() ignora transport:self.transport  →  HTTP backends non possono funzionare
  →  FMP (253 tool) + Helium (9 tool) disabilitati
  →  trader-agent ha COPERTURA DATI INSUFFICIENTE:
      - No financial statements, DCF, analyst estimates
      - No news sentiment, bias analysis
      - No options analysis avanzata
  →  agente produce analisi basate su conoscenza LLM (non live)
```

**Fix**: B1 (to_mcp_entry HTTP support) + abilitare backends nel catalogo.

### RCA #2 — Dispatch non conforme ad ARIA

**Catena causale**:

```
conductor usa spawn-subagent KiloCode diretto  →  bypassa spawn_subagent_validated()
  →  no HandoffRequest  →  no ContextEnvelope  →  no trace_id
  →  sub-agente non riceve contesto strutturato
  →  sub-agente opera in "modalità isolata"
  →  agente non ha visibilità/esigenza di chiamare proxy
```

**Fix**: B3 (integrare spawn_subagent_validated + HandoffRequest).

### RCA #3 — Nessuna verifica runtime

```
prompt dice "usa il proxy"  →  nessun enforcement runtime
  →  agente ignora chiamate proxy (preferisce conoscenza interna)
  →  output senza dati live passa inosservato
  →  conductor non rileva anomalia
```

**Fix**: B4 (guard runtime nel conductor).

### RCA #4 — Output non standardizzato

```
template Trading Brief definito nel prompt  →  non validato
  →  agente produce formato ad-hoc
  →  output non parsabile, non confrontabile
  →  validazione automatica impossibile
```

**Fix**: Template obbligatorio con marcatori parsabili + validazione post-analisi.

---

## 4. Fix Plan Priorizzato

### P0 — Immediati (questa sessione)

| ID | Bug | Difficoltà | Rischio | Dipendenze |
|----|-----|------------|---------|------------|
| B1 | `to_mcp_entry()` HTTP support | Media | Basso — `transport` già parsato, solo to_mcp_entry da aggiornare + test | Nessuna |
| B2 | `_tool_server_name()` underscore | Bassa | Basso — modifica localizzata | Nessuna |

### P1 — Breve termine (prossima sessione)

| ID | Bug | Difficoltà | Rischio | Dipendenze |
|----|-----|------------|---------|------------|
| B3 | spawn_subagent_validated integration | Alta | Medio — modifica prompt conductor + flusso dispatch | B2 (per completezza) |
| B4 | Runtime proxy guard | Medio-Alta | Medio — richiede parsing output agente | B1 (proxy deve funzionare prima) |
| B6 | Skill loading | Media | Basso — solo modifica prompt | Nessuna |

### P2 — Medio termine

| ID | Bug | Difficoltà | Rischio | Dipendenze |
|----|-----|------------|---------|------------|
| B5 | Intent classification hard gate | Bassa | Basso | Nessuna |
| B7 | wiki_update actor correction | Bassa | Basso | Nessuna |
| B8 | trace_id UUIDv7 | Bassa | Basso | Nessuna |

---

## 5. Roadmap Implementativa

### Sprint 1 (Fix infrastrutturali — questo sprint)

```
B1 ──── to_mcp_entry() HTTP support (2h)
  └── Abilitare FMP MCP e Helium MCP in mcp_catalog.yaml (15min)
  └── Test: proxy call_tool → HTTP backend
B2 ──── _tool_server_name() underscore fix (30min)
  └── Test: _allowed_server_names per google_workspace
```

**Risultato**: +2 backend finanziari attivi (FMP 253 tool + Helium 9 tool).  
**Copertura dati**: da 30% a ~85%.

### Sprint 2 (Orchestrazione — prossimo sprint)

```
B3 ──── Integrazione spawn_subagent_validated (3h)
  └── HandoffRequest nel prompt conductor
  └── trace_id UUIDv7
  └── ContextEnvelope propagation
  └── Test: validazione delegation + depth guard
B4 ──── Runtime proxy guard (2h)
  └── Verifica presenza chiamate proxy nell'output
```

**Risultato**: Dispatch conforme all'architettura L1. Rilevazione dati non live.

### Sprint 3 (Prompt engineering — sprint successivo)

```
B5 ──── Intent classification hard gate (30min)
B6 ──── Skill loading instructions (1h)
B7 ──── wiki_update actor fix (30min)
B8 ──── trace_id UUIDv7 fix (30min)
```

**Risultato**: Prompt engineering completo. Output standardizzato.

---

## 6. Appendice: Test di Verifica

### Test esistenti (✅ passano)

| Suite | Count | Stato |
|-------|-------|-------|
| `tests/unit/mcp/proxy/test_broker.py` | 15 | ✅ PASS |
| `tests/unit/mcp/proxy/test_middleware.py` | 12 | ✅ PASS |

### Nuovi test da aggiungere

| Test | Cosa Verifica |
|------|---------------|
| `test_to_mcp_entry_http_transport` | `to_mcp_entry()` produce `{"url": ..., "transport": "http"}` per `transport: http` |
| `test_to_mcp_entry_stdio_transport` | `to_mcp_entry()` produce `{"command": ..., "args": ...}` per `transport: stdio` |
| `test_tool_server_name_underscore` | `_tool_server_name("google_workspace_*")` → `"google_workspace"` |
| `test_tool_server_name_hyphen` | `_tool_server_name("financekit-mcp_*")` → `"financekit-mcp"` |
| `test_spawn_validator_integration` | `spawn_subagent_validated()` accetta HandoffRequest valido |
| `test_spawn_validator_rejects_invalid` | HandoffRequest senza `trace_id` → errore |
| `test_proxy_http_backend_e2e` | `call_tool` su backend HTTP via proxy (FMP) |

---

## Appendice A: Mappa dei File Modificati

| File | Bug | Tipo modifica |
|------|-----|---------------|
| `src/aria/mcp/proxy/catalog.py` | B1 | Aggiungere campo `url` + fix `to_mcp_entry()` |
| `src/aria/mcp/proxy/server.py` | B2 | Fix `_tool_server_name()` con longest-prefix |
| `.aria/kilocode/agents/aria-conductor.md` | B3 | Integrare HandoffRequest + spawn_subagent_validated |
| `.aria/config/mcp_catalog.yaml` | B1 | `financial-modeling-prep-mcp` lifecycle: enabled + URL |
| `.aria/config/mcp_catalog.yaml` | B1 | `helium-mcp` lifecycle: enabled |
| `.aria/kilocode/agents/trader-agent.md` | B5, B6 | Intent classification gate + skill loading |
| Nuovo: conductor guard | B4 | Post-analisi proxy call verification |
| Nuovo: trace_id utility | B8 | UUIDv7 generation helper |

---

*Report generato da Master Orchestrator il 2026-05-03T11:45*
*Basato su analisi di 25+ file, conferme Context7 FastMCP, e report analisi sessione originale.*
