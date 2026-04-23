---
title: Ten Commandments
sources:
  - docs/foundation/aria_foundation_blueprint.md §16
last_updated: 2026-04-23
tier: 1
---

# Ten Commandments — Principi Architetturali Inderogabili

> I 10 comandamenti di ARIA. Deviazioni richiedono ADR esplicito approvato (per Ten Commandment #10).

*source: `docs/foundation/aria_foundation_blueprint.md` §16*

## P1 — Isolation First

ARIA **DEVE** vivere in uno spazio isolato: directory dedicata `/home/fulvio/coding/aria/`, config KiloCode separata via `KILOCODE_CONFIG_DIR`, stato runtime separato, credenziali separate. **Nessuna contaminazione** con l'installazione KiloCode globale dell'utente.

**Implementazione**: `bin/aria` launcher con `KILOCODE_CONFIG_DIR=/home/fulvio/coding/aria/.aria/kilocode`

## P2 — Upstream Invariance

**NON** si modifica il codice sorgente di KiloCode. Lo si consuma come dipendenza npm pinned, lo si configura via file (agents, skills, mcp.json, modes). Aggiornamenti upstream devono essere assorbibili senza rework.

## P3 — Polyglot Pragmatism

KiloCode rimane TypeScript. Tutto il layer ARIA (memoria, scheduler, gateway, credential vault, sub-agent wrappers) è **Python 3.11+**. La colla tra i due mondi è **MCP** + file di stato condivisi.

## P4 — Local-First, Privacy-First

Dati personali, credenziali e memoria **DEVONO** stare in locale. Cloud solo per chiamate LLM (necessarie) e API esterne (Google Workspace, Tavily, ecc.). Nessun provider di memoria cloud (Mem0, Zep) in MVP. File cifrati con SOPS+age possono essere committati in repo.

## P5 — Actor-Aware Memory

Ogni dato persistito **DEVE** essere etichettato con l'attore di origine: `user_input | tool_output | agent_inference | system_event`. Le inferenze probabilistiche **non possono** essere promosse silenziosamente a fatti autoritativi.

*Dettaglio*: `[[memory-subsystem]]` §Actor Tagging

## P6 — Verbatim Preservation (Tier 0)

La memoria episodica **DEVE** preservare il testo verbatim (Tier 0 raw) come fonte autoritativa. Distillazioni, riassunti e summarizations sono layer derivati asincroni (Tier 1+). La sintesi **non sovrascrive** mai il raw.

*Dettaglio*: `[[memory-subsystem]]` §Storage Tiers

## P7 — HITL on Destructive Actions

Qualsiasi azione con uno di questi attributi **DEVE** passare per un gate HITL (Human-In-The-Loop) via Telegram o CLI:
- (a) distruttiva/irreversibile (delete, overwrite, revoke)
- (b) costosa in token/credits sopra soglia
- (c) autenticazione nuova

Le operazioni di sola lettura sono sempre autorizzate.

*Dettaglio*: `[[scheduler]]` §Policy Gate, `[[gateway]]` §HITL

## P8 — Tool Priority Ladder

Per aggiungere una capability:
1. **Prima opzione**: un server MCP maturo esistente → lo si configura
2. **Seconda opzione**: una **skill** (workflow markdown) che orchestra tool esistenti
3. **Terza opzione**: uno **script Python locale** → promuovere a MCP custom entro 2 sprint

**È vietato** aggiungere uno script Python se un MCP maturo copre il caso.

*Dettaglio*: `[[tools-mcp]]` §Tool Priority Ladder

## P9 — Scoped Toolsets ≤ 20

Nessun sub-agente **PUÒ** avere accesso simultaneo a più di **20 tool MCP**. I toolset sono scoped per sub-agente via config dichiarativo. Il Workspace-Agent non vede il Search-Agent toolset e viceversa.

*Dettaglio*: `[[agents-hierarchy]]` §Tool Access Matrix

## P10 — Self-Documenting Evolution

Ogni divergenza implementativa rispetto al blueprint **DEVE** essere registrata via ADR. La skill `blueprint-keeper` scansiona settimanalmente e propone PR di allineamento. Drift silenzioso è vietato.

*Dettaglio*: `[[adrs]]` — Sommario ADR

## Vedi anche

- [[architecture]] — Architettura di sistema
- [[agents-hierarchy]] — Matrice capabilities
- [[tools-mcp]] — Tool priority ladder dettagliata
