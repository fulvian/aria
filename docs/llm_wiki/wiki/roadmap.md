---
title: Roadmap
sources:
  - docs/foundation/aria_foundation_blueprint.md §15
  - docs/foundation/aria_foundation_blueprint.md §18.G
last_updated: 2026-04-23
tier: 1
---

# Roadmap di Implementazione

## Fase 0 — Foundation (Completata: 2026-04-20)

**Obiettivo**: Ambiente ARIA isolato, bootstrap completo, zero logica agentica.

### Deliverable completati
- ✅ Struttura directory completa
- ✅ Launcher `bin/aria` funzionante con isolamento KiloCode
- ✅ `.aria/kilocode/` configurato (kilo.json, mcp.json, agents, skills)
- ✅ `pyproject.toml` + `uv.lock` con dipendenze Phase 0
- ✅ Skeleton `src/aria/` con moduli stub
- ✅ SOPS+age baseline configurato
- ✅ API keys crittografate (8 Tavily, 7 Firecrawl, Brave, Exa, SerpAPI, GitHub)
- ✅ SQLite 3.51.3 da source
- ✅ Systemd unit templates
- ✅ Scripts operativi (bootstrap.sh, backup.sh, restore.sh, install_systemd.sh, smoke_db.sh)
- ✅ Schema SQLite completo
- ✅ Quality gates passati
- ✅ ADR-0001, ADR-0002 creati

## Fase 1 — MVP (Implementazione completata, in verifica: 2026-04-21)

**Obiettivo**: ARIA operativa su Telegram con Search-Agent + Workspace-Agent + memoria.

### Sprint 1.1 — Credential Manager & Memoria (Completato)
- `src/aria/credentials/` completo (SOPS+age, keyring, circuit breaker)
- `src/aria/memory/episodic.py` (SQLite WAL + FTS5)
- `src/aria/memory/clm.py` (compaction)
- `aria-memory` MCP server esposto

### Sprint 1.2 — Scheduler & Gateway Telegram (Completato)
- `src/aria/scheduler/` completo (SQLite store, cron/oneshot, budget/policy gates, HITL, DLQ)
- systemd `aria-scheduler.service` installato
- `src/aria/gateway/telegram_adapter.py` operativo
- HITL via Telegram funzionante

### Sprint 1.3 — ARIA-Conductor & Search-Agent (Completato)
- Agent definitions in `.aria/kilocode/agents/`
- Skills: `deep-research`, `planning-with-files`, `pdf-extract`
- Router Python + 6 provider (Tavily, Brave, Firecrawl, Exa, SearXNG, SerpAPI)
- MCP wrappers (FastMCP 3.x)
- Prompt injection mitigation (ADR-0006)
- 45/45 tests passing

### Sprint 1.4 — Workspace-Agent (Implementato, in verifica)
- `google_workspace_mcp` configurato
- OAuth PKCE setup (`scripts/oauth_first_setup.py`)
- Skills: `triage-email`, `calendar-orchestration`, `doc-draft`
- Wrapper script per Google Workspace
- ADR-0003 (OAuth), ADR-0010 (runtime credentials)

### Criteri di uscita Fase 1 (da verificare)
- [ ] p95 recall memoria < 250ms
- [ ] DLQ rate < 2% su 7 giorni
- [ ] HITL timeout rate < 5%
- [ ] Provider degradation rate < 15%
- [ ] Scheduler success rate > 98%

## Fase 2 — Maturazione (4-6 sprint, ~8-12 settimane)

- Memoria Tier 3: grafo associativo (NER + relazioni)
- LLM routing deterministico
- Canali aggiuntivi: Slack, WebUI Tauri
- MCP Gateway: riduzione tool bloat
- Nuovi sub-agenti: Finance-Agent, Health-Agent, Research-Academic
- Playwright per browser automation
- Observability dashboard: Grafana locale

## Fase 3 — Scale (6-12 mesi)

- Multi-utente / multi-tenant con RBAC
- Dashboard WebUI completa
- Extension marketplace
- Fine-tuning procedurale (opzionale)
- Enterprise hardening (SBOM, SLSA)

*source: `docs/foundation/aria_foundation_blueprint.md` §15, §18.G*

## Vedi anche

- [[architecture]] — Architettura attuale
- [[adrs]] — Decisioni architetturali
- [[quality-gates]] — Quality gates
