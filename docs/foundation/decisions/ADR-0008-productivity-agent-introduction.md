# ADR-0008: Productivity Agent — Austere MVP Introduction

**Status**: Amended
**Date**: 2026-04-29 (amended 2026-05-01)
**Authors**: fulvio
**Related**: ADR-0006 (P10 divergence template), ADR-0015 (FastMCP native proxy)

## Context

Blueprint §15 prevede Fase 2 sub-agenti (Finance/Health/Research-Academic) ma
non `productivity-agent`. L'utente richiede orchestratore dedicato per
workflow consulente: ingestion office files locali, briefing multi-doc,
meeting prep, email drafting con stile dinamico.

La pianificazione dettagliata è avvenuta in due cicli di draft (DRAFT-1 → DRAFT-2)
con 13 Open Questions risolte dall'utente il 2026-04-29. Il piano implementativo
approvato è `docs/plans/agents/productivity_agent_foundation_plan.md`.

## Decision

Introduzione `productivity-agent` come 3° sub-agente operativo, scope austero:

- **1 MCP nuovo**: `markitdown-mcp` (Microsoft, MIT, Context7 benchmark 90.05, 119 code snippets, High reputation)
- **4 skill nuove**: `office-ingest@2.0.0`, `consultancy-brief@1.0.0`,
  `meeting-prep@1.0.0`, `email-draft@1.0.0`
- **Sprint 1** (3 skill): office-ingest, consultancy-brief, meeting-prep
- **Sprint 2** (1 skill): email-draft con dynamic style (Q7)
- **Boundary**: NO chiamata diretta google_workspace; delega a `workspace-agent`
  via spawn-subagent (pattern 2-hop, §8.6 blueprint)
- **HITL**: REPL locale via hitl-queue/ask (Q8), mai Telegram per productivity-agent
- **Niente OCR**, niente audio transcription, niente python-docx/pptx/openpyxl locali

## Decisioni utente acquisite (Open Questions Draft 2)

| # | Domanda | Risposta | Effetto |
|---|---------|----------|---------|
| Q1 | Boundary | **Opzione B (delega)** | Confermata architettura 2-hop |
| Q2 | Scope Fase 1a | **Sì — 3 skill** | office-ingest + consultancy-brief + meeting-prep |
| Q3 | OCR/scansioni | **No** | Niente docling/markitdown-ocr |
| Q4 | Output locale DOCX/PPTX | **No — solo Google Workspace** | Fase 2 ridefinita |
| Q5 | OCR immagini | **No** | Nessuna OPENAI_API_KEY |
| Q6 | Audio STT | **No** | meeting-transcribe rimosso da roadmap |
| Q7 | email-draft stile | **Sì, dinamico** | Niente lesson statica, discovery runtime |
| Q8 | HITL canale | **REPL locale** | No Telegram per productivity-agent |
| Q9 | Multi-cliente auto-tagging | **No** | Wiki client-<slug> solo on-demand |
| Q10 | Naming | **`productivity-agent`** | Confermato |
| Q11 | Obsidian/Notion KB | **Nessuna** | Niente plugin |
| Q12 | Microsoft 365 | **Rinviato** | Futuro ADR-0009 |
| Q13 | Tracked-changes contratti | **No** | Niente safe-docx |

## Consequences

- **Positivi**:
  - +1 MCP server (passa gate no-bloat: MIT, manutentore Microsoft, Context7 Bench 90, tool count 1, keyless, capability unica)
  - +3 skill in Sprint 1, +1 skill in Sprint 2
  - Deprecation `pdf-extract@1.0.0` → `office-ingest@2.0.0` (backward-compatible trigger keywords)
  - Update blueprint §8.3.3, §8.5, §9.5, §15
  - Niente bootstrap stile email statico (decisione utente Q7)
  - Fase 2 deliverable-agent userà solo Google Workspace API (decisione utente Q4), niente python-docx/pptx/openpyxl locali

- **Negativi**:
  - Aumento complessità MCP ecosystem (+1 server, 11 tool su 20 per productivity-agent)
  - Delega 2-hop aggiunge latenza (workspace-agent → productivity-agent → conductor)
  - email-draft style discovery ha costo runtime (gmail.search + analisi thread)
  - Dipendenza da markitdown-mcp per ingestion office files (single point of failure mitigato da fallback filesystem/read)
  - Deprecazione pdf-extract richiede aggiornamento skills esistenti

## Alternatives considered

- **Opzione A (assorbi workspace)**: unire productivity-agent con workspace-agent → rejected per breaking change e regression risk su flussi esistenti
- **Opzione C (overlap diretto google_workspace)**: productivity-agent tocca direttamente Gmail/Calendar → rejected: sfora P9 (tool count > 20), drift risk
- **Anthropic skills pptx/docx/xlsx**: cloud-only Claude API, non eseguibile in Kilo locale
- **safe-docx tracked-changes**: utente non fa review legali (Q13 = no)
- **docling tier 2**: PDF complessi non nel workflow utente (Q3 = no)
- **obsidian-mcp / easy-notion-mcp**: nessuna KB esterna usata (Q11 = nessuna)
- **ms-365-mcp / outlook**: rinviato (Q12 = rinviato)

## References

- `docs/plans/agents/productivity_agent_foundation_plan.md` (piano approvato)
- `docs/plans/agents/productivity_agent_plan_draf_1.md` (DRAFT-2 superseded)
- `docs/analysis/ricerca_mcp_produttività.md` (input ricerca)
- `docs/foundation/aria_foundation_blueprint.md` (§8.3, §8.5, §9.5, §15, §16)
- `github.com/microsoft/markitdown` — Context7 `/microsoft/markitdown` Bench 90.05

## Changelog

- 2026-04-29: Initial draft (Proposed)
- 2026-05-01: **Amendment — Hybrid capability-scoped model**. See §Amendment below.

## Amendment (2026-05-01): Hybrid capability-scoped convergence

### Context

The original ADR-0008 established `productivity-agent` and `workspace-agent` as
separate agents with strict MCP exclusivity: each MCP backend belongs to exactly
one agent. The MCP proxy (`aria-mcp-proxy`, ADR-0015) introduces a policy control
plane that makes this strict separation unnecessary for adjacent work domains.

### Decision

Adopt the **hybrid capability-scoped model**:

1. `productivity-agent` becomes the **single surviving unified work-domain agent**
   with direct proxy access to:
   - `markitdown-mcp` (office ingestion)
   - `filesystem` (local file operations)
   - `google_workspace` (Gmail, Calendar, Drive, Docs, Sheets, Slides)
   - `fetch` (URL deep scrape)
2. `workspace-agent` is downgraded to **transitional/compatibility** status.
   It will be deprecated and removed once all active flows migrate to
   `productivity-agent`.
3. Security is maintained via:
   - **Proxy fail-closed enforcement**: no caller identity → tool call denied
   - **Capability matrix scoping**: `google_workspace_*` is explicitly listed
     in `productivity-agent`'s allowed tools
   - **HITL**: destructive/external actions still require human approval
   - **Audit logging**: all proxy calls are logged with caller identity
4. Blueprint P9 evolves from "static exclusive tool ownership" to
   "scoped active capabilities per task/session".

### Rationale

- External best practice (Microsoft, IBM, Knostic, arXiv 2601.13671) supports
  capability-scoped sharing over strict tool exclusivity when a policy control
  plane exists.
- The proxy middleware provides per-request enforcement with `_caller_id`,
  making the original anti-overlap reasoning from ADR-0008 §Alternatives
  less relevant.
- The convergence reduces delegation overhead (eliminates 2-hop for common
  workflows like "read PDF + send via Gmail").

### Consequences

- `workspace-agent`'s original rationale (avoiding overlap with `productivity-agent`)
  is superseded. ADR-0008 §Alternatives "Opzione A (assorbi workspace)" is
  effectively adopted, but via policy scoping rather than direct code merge.
- The capability matrix YAML is the source of truth for which agent can call
  which backend. Frontmatter `allowed-tools` in agent prompts lists only
  synthetic proxy tools and direct MCP tools (memory, sequential-thinking).
