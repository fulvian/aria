---
title: Agents Hierarchy
sources:
  - docs/foundation/aria_foundation_blueprint.md §8
  - docs/foundation/decisions/ADR-0009-kilo-agent-frontmatter-and-mcp-bin-resolution.md
last_updated: 2026-04-23
tier: 1
---

# Agents Hierarchy — Gerarchia Agenti

## Regola Strutturale (Inderogabile)

```
ORCHESTRATOR (ARIA-Conductor)
  └─> SUB-AGENT (search-agent, workspace-agent)
        └─> SKILL (deep-research, triage-email)
              └─> TOOL (MCP tool o script Python)
```

- L'orchestrator **non chiama tool** direttamente; delega a sub-agenti
- I sub-agenti **usano skill** per workflow complessi e tool per operazioni atomiche
- Le skill **non definiscono tool**; orchestrano tool esistenti

*source: `docs/foundation/aria_foundation_blueprint.md` §8.1*

## ARIA-Conductor (Orchestrator Primario)

**File**: `.aria/kilocode/agents/aria-conductor.md`

Ruolo: **dispatcher cognitivo**, entry point di ogni interazione. Classifica intent, pianifica, delega a sub-agenti via child sessions, sintetizza il risultato finale.

Capabilities:
- Leggere tutto l'albero memoria (ARIA-Memory MCP)
- Spawn child sessions (uno per sub-agente)
- Invocare skill `planning-with-files`
- **NO accesso diretto** a tool di ricerca web, Google Workspace, filesystem

### ADR-0009: Agent Frontmatter

Dopo il bug del REPL (conductor usava `websearch` built-in invece di delegare), gli agenti sono stati riscritti con solo chiavi Kilo valide:

```yaml
# aria-conductor.md frontmatter (pattern post-ADR-0009)
mode: primary
tools:
  websearch: false      # forza delegazione
  codesearch: false
  webfetch: false
permission:
  edit: deny
  bash: deny
  webfetch: deny
```

La negazione esplicita di `websearch`, `codesearch`, `webfetch` sul Conductor garantisce che l'LLM **deve** usare `task` per delegare ai sub-agenti (P8/P9).

*source: `docs/foundation/decisions/ADR-0009-kilo-agent-frontmatter-and-mcp-bin-resolution.md`*

## Sub-Agenti Operativi (MVP)

### Search-Agent

**File**: `.aria/kilocode/agents/search-agent.md`
**Tools**: Tavily, Firecrawl, Brave, Exa, SearXNG + ARIA-Memory
**Skills**: `deep-research`, `source-dedup`

### Workspace-Agent

**File**: `.aria/kilocode/agents/workspace-agent.md`
**Tools**: Google Workspace MCP (17 tool scoped, sotto limite P9 di 20) + ARIA-Memory
**Skills**: `triage-email`, `calendar-orchestration`, `doc-draft`

## Sub-Agenti di Sistema

Invisibili all'utente, invocati in automatico:

| Agent | Trigger | Funzione |
|-------|---------|----------|
| `compaction-agent` | Post-session + scheduler ogni 6h | CLM: distilla T0 → T1 |
| `summary-agent` | Fine sessione | Genera title + summary sessione |
| `memory-curator` | Cron giornaliero + on-demand | Review queue, promote/demote, oblio |
| `blueprint-keeper` | Cron settimanale (dom 10:00) | Scansione codice, divergenze, PR update |
| `security-auditor` | Cron settimanale | Audit permessi, scope, credential usage |

*source: `docs/foundation/aria_foundation_blueprint.md` §8.4*

## Tool Access Matrix

| Sub-Agent | aria-memory | tavily | firecrawl | brave | exa | searxng | google_* | filesystem | git | github |
|-----------|:-----------:|:------:|:---------:|:-----:|:---:|:-------:|:--------:|:----------:|:---:|:------:|
| aria-conductor | ✅ | | | | | | | | | |
| search-agent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | | | | |
| workspace-agent | ✅ | | | | | | ✅ | | | |
| compaction-agent | ✅ | | | | | | | | | |
| summary-agent | ✅ | | | | | | | | | |
| memory-curator | ✅ | | | | | | | | | |
| blueprint-keeper | ✅ | | | | | | | ✅ ro | ✅ | ✅ |
| security-auditor | ✅ | | | | | | | ✅ ro | ✅ | |

`ro = read only`. Ogni sub-agente ≤ 20 tool (P9).

*source: `docs/foundation/aria_foundation_blueprint.md` §8.5*

## Child Sessions

Ogni delega a un sub-agente avvia una **child session** KiloCode separata:
- Context window **non condivisa** con il Conductor
- Output serializzato come JSON: `{status, result, tokens_used, tools_invoked[]}`
- Timeout configurabile (default 10min)
- Transcript salvato in `sessions/children/<id>.json`

*source: `docs/foundation/aria_foundation_blueprint.md` §8.6*

## Vedi anche

- [[tools-mcp]] — Dettaglio MCP servers
- [[skills-layer]] — Skills workflow
- [[search-agent]] — Search-Agent dettaglio
- [[workspace-agent]] — Workspace-Agent dettaglio
