---
title: Architecture
sources:
  - docs/foundation/aria_foundation_blueprint.md §3
  - docs/foundation/aria_foundation_blueprint.md §4
last_updated: 2026-04-23
tier: 1
---

# Architecture

## Overview

ARIA (Autonomous Reasoning & Intelligent Assistant) è un agente AI personale costruito su KiloCode CLI come motore cognitivo, espanso oltre il coding verso vita quotidiana e lavoro intellettuale. È un sistema single-user (MVP), local-first, con architettura a layer separati.

*source: `docs/foundation/aria_foundation_blueprint.md` §1.1*

## Layer Diagram

```
┌─────────────────────────────────────────────────────────────┐
│               CANALI DI INTERAZIONE UMANA                    │
│   CLI (KiloCode) │ Telegram │ (Slack/WebUI @fase2)          │
└───────┬──────────┴────┬─────┘                               │
        │               │                                      │
        ▼               ▼                                      │
┌─────────────────────────────────────────────────────────────┐
│               ARIA GATEWAY (Python)                          │
│   Session Manager │ Auth (whitelist) │ Multimodal            │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│            ARIA CORE (KiloCode + Conductor)                  │
│   ┌──────────────────────────────────────────────────────┐  │
│   │     ARIA-CONDUCTOR (primary orchestrator)             │  │
│   └──┬────────┬──────────┬──────────┬───────────────────┘  │
│      ▼        ▼          ▼          ▼                       │
│   Search   Workspace  Compaction  Summary  Memory-Curator  │
│   Agent    Agent      Agent       Agent                     │
└─────────────────────────────────────────────────────────────┘
        │          │           │          │
        ▼          ▼           ▼          ▼
┌─────────────────────────────────────────────────────────────┐
│               TOOL LAYER (MCP + Python scripts)              │
│   Tavily │ Firecrawl │ Brave │ Exa │ Google Workspace │     │
│   ARIA-Memory │ FS │ Git │ GitHub │ Sequential-Thinking │    │
└─────────────────────────────────────────────────────────────┘
        │                     │
        ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│          BACKEND SERVICES (Python daemons)                   │
│   Memory (5D) │ Scheduler (systemd) │ Credential Manager    │
│   (SOPS+age + keyring)                                      │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│          PERSISTENCE LAYER                                   │
│   SQLite (WAL) │ FTS5 │ LanceDB lazy │ YAML enc │ Keyring   │
└─────────────────────────────────────────────────────────────┘
```

*source: `docs/foundation/aria_foundation_blueprint.md` §3.1*

## Topologia Processi e Servizi

| Componente | Runtime | Avvio | Persistenza |
|-----------|---------|-------|-------------|
| ARIA Launcher (`aria`) | bash script | on-demand | Stateless |
| KiloCode CLI | Node.js | on-demand via launcher | Sessioni in state dir |
| Gateway Daemon | Python 3.11+ | `systemd --user` | SQLite sessions |
| Scheduler Daemon | Python 3.11+ | `systemd --user` | SQLite scheduler |
| ARIA-Memory MCP Server | Python (FastMCP) | Spawned by KiloCode | SQLite, FTS5, LanceDB |
| Credential Manager | Python lib (in-proc) | Embedded in ogni daemon | SOPS+age, keyring |

Tutti i servizi girano in **user space** (`systemd --user`), nessun privilegio root richiesto.

*source: `docs/foundation/aria_foundation_blueprint.md` §3.3*

## Flow Sincrono (Reattivo)

```
[user msg] → [Gateway] → [session lookup] → [ARIA-Conductor]
    → [intent classification] → [child_session: Sub-Agent]
    → [MCP tool calls] → [memory writes (T0 raw)] → [result]
    → [Conductor synthesis] → [Gateway] → [user]
    → [async: Compaction-Agent distills episodic → semantic]
```

*source: `docs/foundation/aria_foundation_blueprint.md` §3.2.1*

## Flow Asincrono (Proattivo)

```
[systemd timer / cron trigger] → [Scheduler Daemon]
    → [budget gate check] → [policy gate (allow|ask|deny)]
    → (if ask) → [HITL prompt via Telegram] → [user approval]
    → [spawn KiloCode task session] → [agent executes]
    → [result persisted to memory] → [notify user if significant]
    → [task run logged → tasks/runs table]
```

*source: `docs/foundation/aria_foundation_blueprint.md` §3.2.2*

## Casi d'Uso MVP (§1.4)

1. **Ricerca tematica**: Search-Agent orchestra Tavily/Brave/Firecrawl, distilla, salva report, notifica via Telegram.
2. **Triage email**: Schedulato ogni mattina 08:00 → Workspace-Agent legge Gmail, classifica, segnala urgenti.
3. **Gestione calendario**: Workspace-Agent consulta disponibilità, propone slot, HITL, crea evento.
4. **Analisi documento**: PDF → estrazione → sintesi → persistenza in memoria semantica.
5. **Conversazione persistente**: Riprendere conversazioni passate con contesto da memoria episodica/semantica.

## Vedi anche

- [[ten-commandments]] — Principi inderogabili
- [[project-layout]] — Struttura directory e isolamento
- [[agents-hierarchy]] — Dettaglio gerarchia agenti
- [[tools-mcp]] — Ecosistema MCP
