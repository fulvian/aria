---
name: blueprint-keeper
version: 1.0.0
description: Scansione codice vs blueprint, genera ADR per divergenze
trigger-keywords: [blueprint, audit, divergenza, ADR]
user-invocable: false
allowed-tools:
  - filesystem_read
  - aria-memory_wiki_update_tool
  - github_search
max-tokens: 20000
estimated-cost-eur: 0.05
---

# Blueprint Keeper Skill

## Obiettivo
Scansionare il codebase e confrontare con blueprint per detectare divergenze.

## Utilizzo
Skill schedulata domenica 10:00 via blueprint-keeper agent.

## Procedura
1. Leggi `aria_foundation_blueprint.md` per reference
2. Scan `src/aria/**/*.py` per strutture e pattern
3. Verifica agents/skills vs §8, §9 blueprint
4. Se divergenza → genera draft ADR
5. Proponi PR con allineamento

## Regole output
- Batch max 1 PR/settimana
- Max 3 sezioni per PR
- Labels: `docs-only`, `breaking`, `security`
- Severity high → draft PR + HITL
