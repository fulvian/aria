# Task Plan: Debug Completo Trader-Agent

**Goal**: Effettuare debug completo del trader-agent basato sul report di analisi `docs/analysis/trader_agent_session_analysis_2026-05-03.md`, seguendo AGENTS.md, LLM Wiki, e Context7.

**Score attuale**: 4/14 obblighi architetturali soddisfatti (31%)
**Target**: Identificare tutte le root cause e produrre raccomandazioni implementative verificabili.

## Fasi

| Phase | Descrizione | Stato |
|-------|-------------|-------|
| 0 | Session recovery & workspace assessment | ✅ COMPLETE |
| 1 | Deep analysis — source documents | ✅ COMPLETE |
| 2 | RCA #1 — FMP MCP disabilitato (HTTP/SSE transport) | 🔴 IN PROGRESS |
| 3 | RCA #2 — KiloCode `task` vs ARIA `spawn-subagent` | ⏳ PENDING |
| 4 | RCA #3 — Runtime proxy usage verification | ⏳ PENDING |
| 5 | RCA #4 — Standardizzazione output Trading Brief | ⏳ PENDING |
| 6 | Intent classification, skill pipeline, wiki_update, trace_id | ⏳ PENDING |
| 7 | Report finale di debug con raccomandazioni implementative | ⏳ PENDING |
| 8 | LLM Wiki maintenance | ⏳ PENDING |

## Decisioni Architetturali

| Decisione | Status | Note |
|-----------|--------|------|
| Backend filtering via `_tool_server_name` | ✅ CORRETTO | Nomi con hyphen funzionano; nomi con underscore (google_workspace) no |
| Proxy middleware two-pass flow | ✅ CORRETTO | `_caller_id` re-injected e stripped correttamente |
| Broker lazy resolution | ✅ CORRETTO | `resolve_server_from_tool` longest-prefix matching OK |
| Capability matrix per trader-agent | ⚠️ DA VERIFICARE | `_*` wildcard funzionanti, ma `financial-modeling-prep-mcp_*` e `helium-mcp_*` disabilitati |

## Dipendenze

- `docs/analysis/trader_agent_session_analysis_2026-05-03.md` — report di analisi
- `docs/llm_wiki/wiki/trader-agent.md` — wiki pagina
- `docs/llm_wiki/wiki/mcp-proxy.md` — proxy contract
- `docs/llm_wiki/wiki/agent-coordination.md` — L1 coordination
- `.aria/kilocode/agents/trader-agent.md` — prompt agente
- `src/aria/mcp/proxy/server.py` — proxy server
- `src/aria/mcp/proxy/broker.py` — lazy backend broker
- `src/aria/mcp/proxy/middleware.py` — capability middleware
- `.aria/config/agent_capability_matrix.yaml` — capability matrix
- `.aria/config/mcp_catalog.yaml` — catalog backend MCP
