# Progress: Debug Completo Trader-Agent

## Phase 0: Session Recovery ✅
- [x] Verificata struttura LLM Wiki
- [x] Letto `docs/llm_wiki/wiki/trader-agent.md` (v1.4)
- [x] Letto `docs/llm_wiki/wiki/mcp-proxy.md`
- [x] Letto `docs/llm_wiki/wiki/agent-coordination.md`
- [x] Letto `docs/llm_wiki/wiki/observability.md`
- [x] Letto report analisi `docs/analysis/trader_agent_session_analysis_2026-05-03.md`
- [x] Letto `.aria/kilocode/agents/trader-agent.md` (prompt)
- [x] Letto `.aria/kilocode/agents/aria-conductor.md` (prompt conductor)
- [x] Letto `.aria/config/agent_capability_matrix.yaml`
- [x] Letto `.aria/config/mcp_catalog.yaml`
- [x] Letto `.aria/kilocode/mcp.json`
- [x] Verificato stato git: branch `fix/trader-agent-recovery`
- [x] Verificato `.workflow/state.md`

## Phase 1: Deep Analysis ✅
- [x] Letto `src/aria/mcp/proxy/server.py` — build_proxy, _tool_server_name, _load_backends
- [x] Letto `src/aria/mcp/proxy/broker.py` — LazyBackendBroker, resolve_server_from_tool
- [x] Letto `src/aria/mcp/proxy/middleware.py` — CapabilityMatrixMiddleware
- [x] Letto `src/aria/mcp/proxy/catalog.py` — BackendSpec, load_backends, to_mcp_entry
- [x] Letto `src/aria/agents/coordination/registry.py` — YamlCapabilityRegistry
- [x] Letto `src/aria/agents/coordination/spawn.py` — spawn_subagent_validated
- [x] Letto `src/aria/agents/coordination/handoff.py` — HandoffRequest
- [x] Lette skills `trading-analysis/SKILL.md`, `fundamental-analysis/SKILL.md`
- [x] Letto test middleware + broker (63 test, ✅ tutti passano)
- [x] Verificato `_tool_server_name` con script Python — hyphens OK, underscores BUG
- [x] Verificato FastMCP create_proxy HTTP/SSE support via Context7 ✅

## Phase 2: RCA #1 — FMP MCP Disabilitato 🔴 IN PROGRESS
- [x] Identificato: `financial-modeling-prep-mcp` (253+ tool, HTTP/SSE, disabled)
- [x] Identificato: `helium-mcp` (9 tool, HTTP/streamable, disabled)
- [x] Verificato FastMCP create_proxy supporta HTTP/SSE via Context7 🎯
- [x] Scoperto: `BackendSpec.to_mcp_entry()` NON gestisce HTTP transport — solo stdio ❌
- [x] Scoperto: `load_backends()` filtra per `lifecycle: enabled` → disabilitati correttamente
- [x] Scoperto: `_get_or_create()` in broker usa `to_mcp_entry()` → non funziona per HTTP
- [ ] **FIX**: `to_mcp_entry()` deve generare `{"url": "...", "transport": "http"}` per HTTP backends
- [ ] **FIX**: Aggiungere campo `url` opzionale a `BackendSpec`
- [ ] **FIX**: Backend HTTP richiedono server running → wrapper startup o sidecar

## Phase 3: RCA #2 — KiloCode task vs ARIA spawn-subagent ⏳
- [x] Identificato: Conductor usa `spawn-subagent` tool nativo KiloCode
- [x] Identificato: `spawn_subagent_validated()` esiste MAI chiamato
- [x] Identificato: `HandoffRequest` definito ma MAI usato nel dispatch
- [x] Identificato: formatted payload non validato (no ContextEnvelope, no trace_id UUIDv7)
- [x] Identificato BUG: `_tool_server_name()` per `google_workspace_*` estrae `"google"` ❌
- [ ] **FIX**: Integrare `spawn_subagent_validated()` nel flusso del conductor
- [ ] **FIX**: Usare `HandoffRequest` con `trace_id` UUIDv7
- [ ] **FIX**: Propogare `ContextEnvelope` (wiki pages pre-caricate)

## Phase 4: RCA #3 — Runtime Proxy Usage Verification ⏳
- [x] Verificato: Middleware fail-closed per tool senza `_caller_id` ✅
- [x] Verificato: Two-pass flow corretto e testato ✅
- [x] Identificato: Nessun guard runtime che obblighi l'agente a chiamare il proxy ❌
- [ ] **FIX**: Aggiungere guard nel conductor (verifica presenza chiamate proxy nell'output)

## Phase 5: RCA #4 — Trading Brief Template ⏳
- [x] Identificato: Template definito nel prompt ma MAI validato
- [x] Verificato: Skill `trading-analysis/SKILL.md` definisce template identico
- [ ] **FIX**: Aggiungere validazione output post-analisi contro template

## Phase 6: Fix minori ⏳
- [x] Identificato: Intent classification saltata completamente
- [x] Identificato: 7 skills MAI caricate a runtime
- [x] Identificato: wiki_update fatto dal conductor, non dal trader-agent
- [x] Identificato: Nessun trace_id UUIDv7 propagato
- [ ] Fix per ognuno

## Phase 7: Report Finale ⏳
- [ ] Scrivere report completo di debug in `docs/debug/`
- [ ] Aggiornare findings.md con raccomandazioni implementative dettagliate

## Phase 8: LLM Wiki Maintenance ⏳
- [ ] Aggiornare `docs/llm_wiki/wiki/trader-agent.md` con debug findings
- [ ] Aggiornare `docs/llm_wiki/wiki/log.md` con entry debug 2026-05-03
- [ ] Aggiornare `docs/llm_wiki/wiki/mcp-proxy.md` con BUG `to_mcp_entry()`
- [ ] Aggiornare `docs/llm_wiki/wiki/index.md`
