---
title: Skills Layer
sources:
  - docs/foundation/aria_foundation_blueprint.md §9
last_updated: 2026-04-23
tier: 1
---

# Skills Layer

## Formato SKILL.md

**Path**: `.aria/kilocode/skills/<skill-slug>/SKILL.md`

Ogni skill ha:
- Frontmatter YAML con metadata (name, version, description, trigger-keywords, allowed-tools, max-tokens)
- Body Markdown con obiettivo, procedura step-by-step, invarianti
- Directory opzionali: `scripts/`, `resources/`

### Esempio: deep-research

```yaml
name: deep-research
version: 1.0.0
description: Ricerca web approfondita multi-provider con deduplica e sintesi
trigger-keywords: [ricerca, search, approfondisci, analizza tema]
user-invocable: true
max-tokens: 50000
estimated-cost-eur: 0.10
```

Procedura:
1. Pianifica 3-7 sub-query diverse
2. Per ogni sub-query invoca il router (Tavily > Brave > Firecrawl > Exa)
3. Deduplica URL (Levenshtein + URL canonicalization)
4. Scrape top-N risultati
5. Classifica per rilevanza e data
6. Sintesi report: TL;DR, Findings, Open Questions, Sources
7. Salva in memoria con tag `research_report`

*source: `docs/foundation/aria_foundation_blueprint.md` §9.1*

## Progressive Disclosure

4 stadi canonici (pattern Anthropic Agent Skills):

1. **Advertise** (~100 token): solo `name` + `description` iniettati nel system prompt
2. **Load**: invocazione `load_skill(name)` → carica `SKILL.md` body
3. **Read resource**: `read_skill_resource(name, resource_id)` → carica file `resources/`
4. **Run script**: `run_skill_script(name, script_id, args)` → esegue sandbox script

MVP implementa stadi 1 e 2; stadi 3-4 se KiloCode li supporta nativamente.

*source: `docs/foundation/aria_foundation_blueprint.md` §9.2*

## Skills MVP

| Skill | Version | Categoria | Descrizione |
|-------|---------|-----------|-------------|
| `planning-with-files` | 1.0.0 | system | Pianificazione strutturata su file (task_plan.md, findings.md, progress.md) |
| `deep-research` | 1.0.0 | research | Ricerca multi-provider con dedup e sintesi |
| `pdf-extract` | 1.0.0 | ingest | PyMuPDF → testo + metadata |
| `triage-email` | 0.9.0 | workspace | Classifica Inbox per urgenza, genera digest |
| `calendar-orchestration` | 1.0.0 | workspace | Gestione disponibilità e creazione eventi |
| `doc-draft` | 1.0.0 | workspace | Drafting documenti Google |
| `memory-distillation` | 1.0.0 | memory | Invoca CLM su range/sessione |
| `hitl-queue` | 1.0.0 | system | Interfaccia gate HITL verso Telegram |
| `blueprint-keeper` | 1.0.0 | governance | Scansione codice vs blueprint, PR automatica |

*source: `docs/foundation/aria_foundation_blueprint.md` §9.3, §9.5*

## Versioning Policy

- Ogni skill usa `semver` (MAJOR.MINOR.PATCH)
- Ogni release aggiorna `compatibility` metadata (`requires_tools`, `min_versions`)
- Ogni MAJOR richiede ADR se impatta flussi utente o policy HITL
- CI valida `_registry.json` contro firme tool correnti

*source: `docs/foundation/aria_foundation_blueprint.md` §9.4*

## Vedi anche

- [[agents-hierarchy]] — Quali agenti usano quali skill
- [[search-agent]] — deep-research skill in contesto
- [[workspace-agent]] — triage-email, calendar-orchestration, doc-draft
