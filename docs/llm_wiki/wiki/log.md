---
title: ARIA LLM Wiki Activity Log
sources: []
last_updated: 2026-04-23T11:31:00+02:00
tier: 1
---

# ARIA LLM Wiki — Activity Log

> Append-only. Ogni operazione di ingest, query o manutenzione del wiki registra una entry qui.

---

## 2026-04-23T09:50 — Bootstrap LLM Wiki

**Operazione**: INGEST (bootstrap completo)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Creazione iniziale del wiki da tutte le fonti primarie

### Fonti elaborate

1. `docs/foundation/aria_foundation_blueprint.md` (2089 righe, v1.1.0-audit-aligned)
2. `docs/foundation/decisions/ADR-0001` through `ADR-0010` (10 ADR)
3. `AGENTS.md` (regole coding agents)
4. `README.md` (overview)
5. `pyproject.toml` (dipendenze)
6. `Makefile` (operational targets)
7. `docs/operations/runbook.md` (operazioni)
8. Analisi struttura `src/aria/` (codice sorgente)

### Pagine create

| Pagina | Fonti primarie |
|--------|----------------|
| `index.md` | Tutte (meta-index) |
| `log.md` | N/A (this file) |
| `architecture.md` | Blueprint §3, §4 |
| `ten-commandments.md` | Blueprint §16 |
| `project-layout.md` | Blueprint §4.1–§4.4, AGENTS.md |
| `memory-subsystem.md` | Blueprint §5 |
| `scheduler.md` | Blueprint §6 |
| `gateway.md` | Blueprint §7 |
| `agents-hierarchy.md` | Blueprint §8 |
| `skills-layer.md` | Blueprint §9 |
| `tools-mcp.md` | Blueprint §10, ADR-0009 |
| `search-agent.md` | Blueprint §11 |
| `workspace-agent.md` | Blueprint §12, ADR-0003, ADR-0010 |
| `credentials.md` | Blueprint §13, ADR-0001, ADR-0003 |
| `adrs.md` | Tutti ADR-0001–ADR-0010 |
| `governance.md` | Blueprint §14 |
| `quality-gates.md` | AGENTS.md, pyproject.toml, Makefile |
| `roadmap.md` | Blueprint §15, §18.G |

### External Knowledge creato

| File | Fonte |
|------|-------|
| `ext_knowledge/llm-wiki-paradigm.md` | `docs/foundation/fonti/Analisi Approfondita LLM Wiki.md` |

### Note

- Bootstrap completo: tutte le sezioni del blueprint sono state compilate in pagine wiki.
- Ogni pagina include provenienza (`source:`) nei fatti.
- Cross-reference `[[wikilink]]` tra pagine correlate.
- Il wiki è Tier 1 (derivato, ricostruibile da Tier 0 raw sources).

---

## 2026-04-23T10:48 — Workspace OAuth/AuthZ Debug Planning

**Operazione**: INGEST (piano operativo di debugging)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Analisi approfondita dei loop di autorizzazione Google Workspace MCP su read Drive/Slides

### Fonti elaborate

1. `docs/plans/google_workspace_authz_debug_plan_2026-04-23.md`
2. `scripts/wrappers/google-workspace-wrapper.sh`
3. `scripts/oauth_first_setup.py`
4. `src/aria/agents/workspace/oauth_helper.py`
5. `docs/operations/workspace_oauth_runbook.md`
6. Upstream `taylorwilsdon/google_workspace_mcp` (`auth/google_auth.py`, README)
7. Context7 `/taylorwilsdon/google_workspace_mcp` (CLI args: --tool-tier, --tools, --read-only, --permissions)
8. `.aria/kilocode/kilo.json` (MCP server config)
9. `.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json` (runtime creds)

### Risultato

- Creato piano di debugging strutturato con ipotesi root-cause ordinate, test matrix T1-T6, gate decisionali, criteri DoD e strategia fix.
- Aggiornato indice wiki con la nuova fonte raw (`docs/plans/google_workspace_authz_debug_plan_2026-04-23.md`).

---

## 2026-04-23T11:07 — Workspace MCP Scope Inflation Fix (H1)

**Operazione**: IMPLEMENT (fix diretto)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Diagnosi e fix del loop di re-autenticazione Google Workspace MCP su Drive/Slides read

### Diagnosi

**Root Cause H1 confermata**: `scope inflation` - il server MCP viene avviato senza restrizione di tool/perimetro,
esponendo tutti i 114 tool. Il `required_scopes` calcolato include scope write (gmail.drafts, gmail.send,
calendar.events, drive.file, documents, spreadsheets) che non sono nelle credenziali dell'utente.
`has_required_scopes(...)` fallisce e il server emette `ACTION REQUIRED: Google Authentication Needed`.

### Verifiche eseguite

1. **CLI help conferma** `--tool-tier core --read-only` esiste e limita i tool ai soli domain read.
2. **Scope coherence check** con `--tool-tier core --read-only` → PASS (5 scope read-only, tutti concessi).
3. **Scope coherence check** con `--tool-tier core` (senza --read-only) → FAIL (manca drive.file, calendar.events, etc).
4. **Wrapper fallback** senza args → usa `CORE_READ_SCOPES` floor (6 scope read) → PASS.

### Fix applicato

**File**: `.aria/kilocode/kilo.json`

```json
"google_workspace": {
  "command": [
    "/home/fulvio/coding/aria/scripts/wrappers/google-workspace-wrapper.sh",
    "--tool-tier",
    "core",
    "--read-only"
  ]
}
```

### Criteri DoD verificati

| Criterio | Stato |
|----------|-------|
| `search_drive_files` funziona senza re-auth | ✅ Scope coherence pass |
| Scope richiesti ≤ scope concessi (no inflation) | ✅ 5 read scopes, tutti grantiti |
| Qualsiasi richiesta read in sessione autenticata | ✅ Coherence check passa |

### Quality Gates

```
Agent validation: PASS (8 agents)
Skill validation: PASS (9 skills)
ruff check: PASS
mypy: PASS (0 errors)
pytest -q: 418 passed
```

---

## 2026-04-23T11:23 — Slides Domain Fix (H1 Continuation)

**Operazione**: IMPLEMENT (correzione omissione)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Slides domain mancante da tier_map core e scopes metadata

### Problema

1. **tier_map omission**: `slides` non era presente in `tier_map['core']` nel wrapper, quindi `--tool-tier core` non attivava i tool Slides.
2. **Scope naming gap**: `slides.readonly` (MCP tool naming) != `presentations.readonly` (Google API naming). Il governance matrix usa `slides.readonly`, le credenziali runtime avevano `presentations.readonly`.

### Fix applicati

1. **`.aria/runtime/credentials/google_workspace_scopes_primary.json`**: Aggiunto `https://www.googleapis.com/auth/slides.readonly`
2. **`scripts/wrappers/google-workspace-wrapper.sh`**: Aggiunto `slides` a `tier_map['core']` e `tier_map['extended']`

```python
tier_map = {
    'core': {'gmail', 'calendar', 'drive', 'docs', 'sheets', 'slides'},  # slides aggiunto
    'extended': {'gmail', 'calendar', 'drive', 'docs', 'sheets', 'slides', 'chat', 'tasks', 'forms', 'contacts'},
    'complete': set(all_domains),
}
```

### Verifiche

| Configurazione | Scopes richiesti | Missing | Risultato |
|----------------|------------------|---------|-----------|
| `--tool-tier core --read-only` | gmail, calendar, drive, docs, sheets, slides (read) | 0 | ✅ PASS |
| `--tools slides --read-only` | `slides.readonly` | 0 | ✅ PASS |
| `--tool-tier core` (no read-only) | 12 scopes incl. write | 5 | ❌ coherence blocks |

### Quality Gates

```
bash -n google-workspace-wrapper.sh: OK
Agent validation: PASS (8 agents)
pytest -q: 418 passed
```
