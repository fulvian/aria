---
document: ARIA Foundation Blueprint
version: 1.1.0-audit-aligned
status: ratified
date_created: 2026-04-20
last_review: 2026-04-20
author: ARIA Chief Architect
project: ARIA — Autonomous Reasoning & Intelligent Assistant
canonical_path: docs/foundation/aria_foundation_blueprint_v2.md
license: private
update_policy: |
  Questo documento è la "stella polare" prescrittiva di ARIA.
  Qualsiasi divergenza tra implementazione e blueprint DEVE essere registrata:
    (a) come emendamento a questo documento via PR con sezione motivazionale, OPPURE
    (b) come ADR in `docs/foundation/decisions/ADR-NNNN-<slug>.md` linkato nella sezione pertinente.
  La skill `blueprint-keeper` (vedi §17) scansiona settimanalmente il codice e apre PR
  automatiche di update. Ogni sezione espone un proprio frontmatter con:
    { status: draft|ratified|implemented|deprecated, last_review: YYYY-MM-DD, owner: <handle> }
changelog:
  - 2026-04-20: v1.1.0-audit-aligned — integrazione remediation obbligatorie e raccomandate da `ARIA_blueprint_audit.md`.
  - 2026-04-20: v1.0.0-draft — fondazione ratificata dall'utente (Fulvio).
---

# ARIA — Autonomous Reasoning & Intelligent Assistant
## Foundation Blueprint

> **Stella polare** per lo sviluppo di ARIA. Documento tecnico, prescrittivo, inderogabile nei principi e nelle regole (§2 e §16), evolutivo nei dettagli implementativi (auto-update §17).

---

## Indice

0. [Front Matter & Policy](#0-front-matter--policy)
1. [Visione e Scope](#1-visione-e-scope)
2. [Principi Architetturali Inderogabili](#2-principi-architetturali-inderogabili)
3. [Architettura di Sistema](#3-architettura-di-sistema)
4. [Isolamento dall'ambiente KiloCode globale](#4-isolamento-dallambiente-kilocode-globale)
5. [Sottosistema di Memoria 5D](#5-sottosistema-di-memoria-5d)
6. [Scheduler & Autonomia](#6-scheduler--autonomia)
7. [Gateway Esterno](#7-gateway-esterno)
8. [Gerarchia Agenti](#8-gerarchia-agenti)
9. [Skills Layer](#9-skills-layer)
10. [Tools & MCP Ecosystem](#10-tools--mcp-ecosystem)
11. [Sub-Agent di Ricerca Web](#11-sub-agent-di-ricerca-web)
12. [Sub-Agent Google Workspace](#12-sub-agent-google-workspace)
13. [Credential Management](#13-credential-management)
14. [Governance & Osservabilità](#14-governance--osservabilità)
15. [Roadmap di Implementazione](#15-roadmap-di-implementazione)
16. [Regole Inderogabili — The Ten Commandments](#16-regole-inderogabili--the-ten-commandments)
17. [Auto-aggiornamento del Blueprint](#17-auto-aggiornamento-del-blueprint)
18. [Appendici](#18-appendici)

---

## 0. Front Matter & Policy

### 0.1 Posizionamento del documento

Questo blueprint **precede** qualsiasi scrittura di codice. Piani di implementazione dettagliati (sprint-level) sono documenti separati in `docs/plans/phase-N/sprint-NN.md`, generati referenziando questo blueprint come **fonte autoritativa**.

### 0.2 Convenzioni tipografiche

- `MUST` / `DEVE`: inderogabile.
- `SHOULD` / `DOVREBBE`: fortemente raccomandato; deviazioni solo via ADR.
- `MAY` / `PUÒ`: opzionale.
- Path in **grassetto monospace** indicano posizioni canoniche.
- Etichette `@faseN` su titoli identificano l'orizzonte di implementazione.

### 0.3 Audience

Sviluppatori che implementano ARIA in sessioni di Claude Code (o simili), incluso il proprietario-utente (Fulvio). Ogni sessione parte riferenziandosi a questo blueprint e al piano di sprint corrente.

### 0.4 Compatibility window e review cadence

Per ridurre drift tecnico su librerie critiche, ARIA adotta una finestra di compatibilità esplicita:

- **Cadence minima**: review tecnica ogni 30 giorni su dipendenze P0/P1 (`fastmcp`, `google_workspace_mcp`, `python-telegram-bot`, `lancedb`, stack STT, SQLite runtime).
- **Regola di pinning**: vincoli con major guard (`>=X.Y,<X+1.0`) per librerie core.
- **Trigger straordinari**: review immediata in caso di advisory sicurezza, breaking release major, deprecazioni OAuth/API provider.
- **Output richiesto**: changelog sezione + ADR se impatta principi o comportamento.

---

## 1. Visione e Scope

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 1.1 Cosa è ARIA

**ARIA — Autonomous Reasoning & Intelligent Assistant** è un **assistente agentico AI a 360°**, fondato su KiloCode CLI come motore cognitivo, ma **espanso** oltre il dominio del coding verso attività di vita quotidiana e lavoro intellettuale: ricerche web profonde, analisi di documenti, operazioni su Google Workspace, automazione di routine, attività asincrone schedulate, interazione conversazionale tramite canali esterni (Telegram in MVP, altri canali in Fase 2).

ARIA si pone come il **life agent personale** del proprietario. Non è un prodotto multi-tenant; l'eventuale estensione a terzi è un obiettivo di Fase 3.

### 1.2 Obiettivi fondativi

1. **Assistenza reattiva multimodale**: rispondere a richieste in linguaggio naturale (testo, voce, immagini) con esecuzione di azioni reali su sistemi esterni.
2. **Agentività proattiva**: svegliarsi autonomamente, eseguire task schedulati, notificare con risultati significativi (non rumore).
3. **Persistenza cognitiva**: ricordare conversazioni, preferenze, decisioni architetturali, dati consolidati — senza amnesia tra sessioni.
4. **Ubiquità**: accessibile dalla CLI locale, da Telegram in MVP, da più canali in Fase 2.
5. **Controllo utente**: ogni azione distruttiva, costosa o irreversibile passa per un gate HITL (Human-In-The-Loop) configurabile.

### 1.3 Non-obiettivi

ARIA **NON** è:
- Un IDE o un assistente di coding full-stack (quello è KiloCode stand-alone).
- Una piattaforma SaaS multi-tenant (fino a Fase 3).
- Un sostituto di strumenti di produttività enterprise (Jira, Slack aziendale, ERP).
- Un assistente vocale real-time (Whisper è batch in MVP).
- Un sistema che agisce **autonomamente** su operazioni distruttive senza HITL.

### 1.4 Casi d'uso fondativi (MVP)

Il successo dell'MVP è misurato dalla capacità di ARIA di gestire i seguenti flussi senza intervento manuale intermedio:

1. **Ricerca tematica**: "ARIA, fai una ricerca approfondita su X e scrivimi un report" → Search-Agent orchestra Tavily/Brave/Firecrawl, distilla risultati, salva report in Drive, notifica via Telegram.
2. **Triage email**: schedulato ogni mattina alle 08:00 → Workspace-Agent legge Inbox Gmail, classifica, riassume, segnala urgenti via Telegram.
3. **Gestione calendario**: "ARIA, pianifica una call di 30min con Mario la prossima settimana" → Workspace-Agent consulta disponibilità, propone slot, chiede conferma HITL, crea evento.
4. **Analisi documento**: "ARIA, leggi questo PDF e dimmi i punti chiave" → estrazione contenuto, sintesi distillata, persistenza in memoria semantica per riferimenti futuri.
5. **Conversazione persistente**: riprendere una conversazione tecnica iniziata tre settimane prima, con contesto recuperato dalla memoria episodica/semantica.

---

## 2. Principi Architetturali Inderogabili

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

Le seguenti **10 leggi architetturali** sono inderogabili. Ogni deviazione richiede un ADR esplicito e approvato.

### P1 — Isolation First
ARIA **DEVE** vivere in uno spazio isolato: directory dedicata `/home/fulvio/coding/aria/`, config KiloCode separata via `KILOCODE_CONFIG_DIR`, stato runtime separato, credenziali separate. **Nessuna contaminazione** con l'installazione KiloCode globale dell'utente (dedicata al coding).

### P2 — Upstream Invariance
**NON** si modifica il codice sorgente di KiloCode. Lo si consuma come dipendenza npm pinned, lo si configura via file (agents, skills, mcp.json, modes). Aggiornamenti upstream devono essere assorbibili senza rework.

### P3 — Polyglot Pragmatism
KiloCode rimane TypeScript. Tutto il layer ARIA (memoria, scheduler, gateway, credential vault, sub-agent wrappers) è **Python 3.11+**. La colla tra i due mondi è **MCP** + file di stato condivisi.

### P4 — Local-First, Privacy-First
Dati personali, credenziali e memoria **DEVONO** stare in locale. Cloud solo per chiamate LLM (necessarie) e API esterne (Google Workspace, Tavily, ecc.). Nessun provider di memoria cloud (Mem0, Zep) in MVP. File cifrati con SOPS+age possono essere committati in repo.

### P5 — Actor-Aware Memory
Ogni dato persistito **DEVE** essere etichettato con l'attore di origine: `user_input | tool_output | agent_inference | system_event`. Le inferenze probabilistiche **non possono** essere promosse silenziosamente a fatti autoritativi.

### P6 — Verbatim Preservation (Tier 0)
La memoria episodica **DEVE** preservare il testo verbatim (Tier 0 raw) come fonte autoritativa. Distillazioni, riassunti e summarizations sono layer derivati asincroni (Tier 1+). La sintesi **non sovrascrive** mai il raw.

### P7 — HITL on Destructive or Non-Explicit Actions
Qualsiasi azione con uno di questi attributi **DEVE** passare per un gate HITL (Human-In-The-Loop) via Telegram o CLI: (a) distruttiva (delete, overwrite), (b) costosa in token/credits sopra soglia, (c) scrittura/modifica non richiesta esplicitamente nel prompt utente corrente, (d) autenticazione nuova.

Le operazioni di sola lettura sono sempre autorizzate.

### P8 — Tool Priority Ladder
Per aggiungere una capability:
1. **Prima opzione**: un server MCP maturo esistente. Lo si configura.
2. **Seconda opzione**: una **skill** (workflow markdown) che orchestra tool esistenti.
3. **Terza opzione**: uno **script Python locale** (wrapper verso API non coperta). Va comunque esposto via MCP custom entro 2 sprint.

**È vietato** aggiungere uno script Python se un MCP maturo copre il caso, ed è vietato aggiungere un MCP se una skill può ottenere lo stesso risultato componendo tool esistenti.

### P9 — Scoped Toolsets
Nessun sub-agente **PUÒ** avere accesso simultaneo a più di **20 tool MCP**. I toolset sono scoped per sub-agente via config dichiarativo. Il Workspace-Agent non vede il Search-Agent toolset e viceversa.

### P10 — Self-Documenting Evolution
Ogni divergenza implementativa rispetto al blueprint **DEVE** essere registrata via ADR (§17). La skill `blueprint-keeper` scansiona settimanalmente e propone PR di allineamento. Drift silenzioso è vietato.

---

## 3. Architettura di Sistema

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 3.1 Diagramma a Layer (logico)

```
┌─────────────────────────────────────────────────────────────────────┐
│                   CANALI DI INTERAZIONE UMANA                        │
│  ┌─────────┐  ┌──────────┐  ┌───────────────┐  ┌────────────────┐  │
│  │  CLI    │  │ Telegram │  │ (Slack @fase2)│  │ (WebUI @fase2) │  │
│  └────┬────┘  └────┬─────┘  └───────┬───────┘  └────────┬───────┘  │
│       │            │                │                    │          │
└───────┼────────────┼────────────────┼────────────────────┼──────────┘
        │            │                │                    │
        │            └────────┬───────┘                    │
        │                     ▼                            │
        │         ┌─────────────────────────┐              │
        │         │   ARIA GATEWAY (Python) │              │
        │         │  session mgr │ auth     │              │
        │         │  multimodal  │ routing  │              │
        │         └───────────┬─────────────┘              │
        │                     │                            │
        ▼                     ▼                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ARIA CORE (KiloCode + wrapper)                    │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │           ARIA-CONDUCTOR (primary agent)                      │  │
│   │          dispatch to sub-agents via child sessions            │  │
│   └──┬────────┬────────────┬──────────┬──────────┬───────────────┘  │
│      │        │            │          │          │                   │
│      ▼        ▼            ▼          ▼          ▼                   │
│   ┌─────┐ ┌───────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐       │
│   │Srch │ │Wkspce │ │Compaction│ │Summary │ │ Memory-      │       │
│   │Agent│ │ Agent │ │  Agent   │ │ Agent  │ │ Curator      │       │
│   └─────┘ └───────┘ └──────────┘ └────────┘ └──────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
       │          │           │          │           │
       ▼          ▼           ▼          ▼           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TOOL LAYER (MCP + scripts)                        │
│   ┌─────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐  │
│   │ Tavily  │ │Firecrawl │ │ Brave  │ │  Exa   │ │ Google       │  │
│   │ MCP     │ │ MCP      │ │ MCP    │ │ script │ │ Workspace    │  │
│   └─────────┘ └──────────┘ └────────┘ └────────┘ │ MCP          │  │
│   ┌─────────┐ ┌──────────┐ ┌──────────────┐     └──────────────┘  │
│   │ FS MCP  │ │ Git MCP  │ │ Playwright   │                         │
│   └─────────┘ └──────────┘ └──────────────┘                         │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │          ARIA-MEMORY MCP (server custom)                    │   │
│   │   remember | recall | distill | curate | forget            │   │
│   └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
       │                     │                    │
       ▼                     ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│              SERVIZI DI BACKEND (Python daemons)                    │
│   ┌──────────────┐  ┌───────────────┐  ┌───────────────────────┐   │
│   │   Memory     │  │   Scheduler   │  │  Credential Manager   │   │
│   │   Subsystem  │  │   Daemon      │  │  (SOPS+age + keyring) │   │
│   │   (5 tiers)  │  │   (systemd)   │  │                       │   │
│   └──────────────┘  └───────────────┘  └───────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
       │                     │
       ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                PERSISTENCE LAYER                                     │
│   SQLite (memory, scheduler) │ FTS5 │ LanceDB lazy │ YAML enc       │
│   OS Keyring (OAuth tokens) │ logs JSON │ backups git-crypt        │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Flow di Interazione

#### 3.2.1 Flow sincrono (reattivo)

```
[user msg] → [Gateway] → [session lookup] → [ARIA-Conductor]
    → [intent classification] → [child_session: Search-Agent]
    → [MCP tool calls] → [memory writes (Tier 0 raw)] → [result]
    → [Conductor synthesis] → [Gateway] → [user]
    → [async: Compaction-Agent distills episodic → semantic]
```

#### 3.2.2 Flow asincrono (proattivo)

```
[systemd timer / cron trigger] → [Scheduler Daemon]
    → [budget gate check] → [policy gate (allow|ask|deny)]
    → (if ask) → [HITL prompt via Telegram] → [user approval]
    → [spawn KiloCode task session] → [agent executes]
    → [result persisted to memory] → [notify user if significant]
    → [task run logged → tasks/runs table]
```

### 3.3 Topologia di processi e servizi

| Componente              | Runtime              | Avvio                    | Persistenza           |
|-------------------------|----------------------|--------------------------|-----------------------|
| ARIA Launcher (`aria`)  | bash script          | on-demand                | N/A (stateless)       |
| KiloCode CLI            | Node.js              | on-demand via launcher   | sessioni in state dir |
| Gateway Daemon          | Python 3.11+         | `systemd --user` unit    | SQLite sessions       |
| Scheduler Daemon        | Python 3.11+         | `systemd --user` unit    | SQLite scheduler      |
| ARIA-Memory MCP Server  | Python (FastMCP)     | spawned by KiloCode      | SQLite, FTS5, LanceDB |
| Credential Manager      | Python lib (in-proc) | embedded in ogni daemon  | SOPS+age, keyring     |

Tutti i servizi girano in **user space** (`systemd --user`), nessun privilegio root richiesto.

---

## 4. Isolamento dall'ambiente KiloCode globale

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 4.1 Layout directory completo

```
/home/fulvio/coding/aria/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example                    # template (NON contiene segreti)
├── pyproject.toml                  # dipendenze Python (uv/poetry)
├── package.json                    # pinning di KiloCode CLI
├── Makefile                        # task comuni (install, run, test, backup)
│
├── bin/
│   └── aria                        # launcher script (bash)
│
├── .aria/                          # STATO ISOLATO (gitignored eccetto config)
│   ├── kilocode/                   # ← KILOCODE_CONFIG_DIR
│   │   ├── kilo.json               # config KiloCode
│   │   ├── mcp.json                # registry MCP server (global)
│   │   ├── agents/                 # agent definitions
│   │   │   ├── aria-conductor.md
│   │   │   ├── search-agent.md
│   │   │   ├── workspace-agent.md
│   │   │   └── _system/
│   │   │       ├── compaction-agent.md
│   │   │       ├── summary-agent.md
│   │   │       ├── memory-curator.md
│   │   │       ├── blueprint-keeper.md
│   │   │       └── security-auditor.md
│   │   ├── skills/                 # skills layer
│   │   │   ├── planning-with-files/
│   │   │   ├── deep-research/
│   │   │   ├── pdf-extract/
│   │   │   ├── memory-distillation/
│   │   │   ├── hitl-queue/
│   │   │   ├── blueprint-keeper/
│   │   │   └── [...future skills]
│   │   ├── modes/                  # custom modes se necessari
│   │   └── sessions/               # sessioni KiloCode persistite
│   │
│   ├── runtime/                    # STATO a runtime (gitignored)
│   │   ├── memory/
│   │   │   ├── episodic.db         # SQLite raw + FTS5
│   │   │   ├── semantic/           # LanceDB dir (lazy)
│   │   │   └── graph/              # @fase2: grafo associativo
│   │   ├── scheduler/
│   │   │   └── scheduler.db        # SQLite tasks/runs/dlq
│   │   ├── gateway/
│   │   │   └── sessions.db         # SQLite mapping canali
│   │   ├── credentials/
│   │   │   └── providers_state.enc.yaml   # runtime state cifrato (NO GIT)
│   │   ├── logs/                   # structured JSON logs
│   │   └── tmp/                    # file temporanei
│   │
│   └── credentials/                # (gitignored eccetto .sops.yaml)
│       ├── .sops.yaml              # config SOPS (IN GIT)
│       ├── secrets/
│       │   └── api-keys.enc.yaml   # IN GIT (cifrato)
│       └── keyring-fallback/       # solo se Secret Service non disponibile
│
├── src/                            # codice Python ARIA (IN GIT)
│   ├── aria/
│   │   ├── __init__.py
│   │   ├── config.py               # loading config ARIA
│   │   ├── credentials/
│   │   │   ├── __init__.py
│   │   │   ├── manager.py          # credential_manager.py unified API
│   │   │   ├── sops.py
│   │   │   ├── keyring_store.py
│   │   │   ├── rotator.py          # circuit breaker + rotation
│   │   │   └── audit.py
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── schema.py           # Pydantic models
│   │   │   ├── episodic.py         # SQLite raw + FTS5
│   │   │   ├── semantic.py         # LanceDB wrapper
│   │   │   ├── procedural.py       # skills registry
│   │   │   ├── associative.py      # @fase2
│   │   │   ├── clm.py              # Context Lifecycle Manager
│   │   │   ├── actor_tagging.py
│   │   │   └── mcp_server.py       # ARIA-Memory MCP server
│   │   ├── scheduler/
│   │   │   ├── __init__.py
│   │   │   ├── daemon.py           # systemd entrypoint
│   │   │   ├── store.py            # SQLite tasks/runs/dlq
│   │   │   ├── triggers.py         # cron/event/webhook/oneshot/manual
│   │   │   ├── budget_gate.py
│   │   │   ├── policy_gate.py
│   │   │   ├── hitl.py             # HITL via Telegram
│   │   │   ├── notify.py           # sd_notify watchdog
│   │   │   └── reaper.py
│   │   ├── gateway/
│   │   │   ├── __init__.py
│   │   │   ├── daemon.py
│   │   │   ├── telegram_adapter.py
│   │   │   ├── session_manager.py
│   │   │   ├── auth.py             # whitelist + HMAC
│   │   │   └── multimodal.py       # OCR/vision, Whisper
│   │   ├── agents/                 # wrapper logic per sub-agent
│   │   │   ├── __init__.py
│   │   │   ├── search/
│   │   │   │   ├── router.py       # intent-aware routing
│   │   │   │   ├── providers/
│   │   │   │   │   ├── tavily.py
│   │   │   │   │   ├── firecrawl.py
│   │   │   │   │   ├── brave.py
│   │   │   │   │   ├── exa.py
│   │   │   │   │   └── searxng.py
│   │   │   │   └── dedup.py
│   │   │   └── workspace/
│   │   │       └── oauth_helper.py  # first-time consent
│   │   ├── tools/                  # Python scripts esposti via MCP custom
│   │   └── utils/
│   │       ├── logging.py
│   │       └── metrics.py
│   │
│   └── tests/                      # pytest
│       ├── unit/
│       ├── integration/
│       └── fixtures/
│
├── systemd/                        # unit files (template, IN GIT)
│   ├── aria-scheduler.service
│   ├── aria-gateway.service
│   └── aria-memory.service         # opzionale se MCP server sta standalone
│
├── scripts/                        # script di setup/maintenance (IN GIT)
│   ├── bootstrap.sh                # primo setup (deps, .sops.yaml, age keys)
│   ├── install_systemd.sh
│   ├── backup.sh
│   ├── restore.sh
│   ├── oauth_first_setup.py        # Google OAuth one-time
│   └── rotate_api_keys.py
│
└── docs/
    ├── foundation/
    │   ├── aria_foundation_blueprint_v2.md   ← QUESTO FILE
    │   ├── fonti/                         # studi di ricerca (IN GIT)
    │   └── decisions/                     # ADR (IN GIT)
    ├── implementation/
    │   ├── phase-0/
    │   ├── phase-1/
    │   └── phase-2/
    ├── operations/
    │   ├── runbook.md
    │   ├── provider_exhaustion.md
    │   ├── disaster_recovery.md
    │   └── telemetry.md
    └── api/                        # API docs generata (se utile)
```

### 4.2 Variabili d'ambiente dedicate

Tutte le variabili ARIA hanno prefisso `ARIA_` oppure sono di KiloCode usate in isolamento.

```bash
# --- KiloCode isolation ---
export KILOCODE_CONFIG_DIR=/home/fulvio/coding/aria/.aria/kilocode
export KILOCODE_STATE_DIR=/home/fulvio/coding/aria/.aria/kilocode/sessions

# --- ARIA paths ---
export ARIA_HOME=/home/fulvio/coding/aria
export ARIA_RUNTIME=/home/fulvio/coding/aria/.aria/runtime
export ARIA_CREDENTIALS=/home/fulvio/coding/aria/.aria/credentials

# --- ARIA operational ---
export ARIA_LOG_LEVEL=INFO                 # DEBUG|INFO|WARN|ERROR
export ARIA_TIMEZONE=Europe/Rome
export ARIA_LOCALE=it_IT.UTF-8
export ARIA_QUIET_HOURS=22:00-07:00        # no proactive notify in queste ore

# --- SOPS ---
export SOPS_AGE_KEY_FILE=$HOME/.config/sops/age/keys.txt

# --- Gateway Telegram ---
export ARIA_TELEGRAM_WHITELIST=123456789,987654321  # user ID autorizzati
```

La variabile `SOPS_AGE_KEY_FILE` punta fuori dalla directory di progetto (in `~/.config/sops/age/`) per evitare inclusione accidentale nel repo.

### 4.3 Launcher script `aria`

**File**: `bin/aria` (chmod +x, aggiunto al PATH utente)

```bash
#!/usr/bin/env bash
# ARIA launcher — garantisce isolamento dal KiloCode globale
set -euo pipefail

export ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
export KILOCODE_CONFIG_DIR="$ARIA_HOME/.aria/kilocode"
export KILOCODE_STATE_DIR="$ARIA_HOME/.aria/kilocode/sessions"
export ARIA_RUNTIME="$ARIA_HOME/.aria/runtime"
export ARIA_CREDENTIALS="$ARIA_HOME/.aria/credentials"

# carica .env se presente (non-segreti; segreti via SOPS)
if [[ -f "$ARIA_HOME/.env" ]]; then
  set -a; source "$ARIA_HOME/.env"; set +a
fi

# Pre-flight checks
[[ -d "$KILOCODE_CONFIG_DIR" ]] || { echo "ERR: config dir missing"; exit 1; }
[[ -f "$KILOCODE_CONFIG_DIR/kilo.json" ]] || { echo "ERR: kilo.json missing"; exit 1; }

# Sub-commands
case "${1:-repl}" in
  repl)       exec npx --yes kilocode chat ;;
  run)        shift; exec npx --yes kilocode chat --auto "$@" ;;
  mode)       shift; exec npx --yes kilocode chat --mode "$@" ;;
  schedule)   shift; exec python -m aria.scheduler "$@" ;;
  gateway)    shift; exec python -m aria.gateway "$@" ;;
  memory)     shift; exec python -m aria.memory "$@" ;;
  creds)      shift; exec python -m aria.credentials "$@" ;;
  backup)     shift; exec "$ARIA_HOME/scripts/backup.sh" "$@" ;;
  --help|-h|help)  exec cat "$ARIA_HOME/docs/foundation/aria_foundation_blueprint_v2.md" | less ;;
  *)          echo "Unknown: $1" >&2; exit 2 ;;
esac
```

### 4.4 Dipendenze versionate

**`package.json`** pinning (ricostruito ad ogni upstream update con PR):
```json
{
  "name": "aria-kilocode-host",
  "private": true,
  "dependencies": {
    "kilocode": "X.Y.Z"          // pinnare versione stabile al momento del bootstrap
  }
}
```

**`pyproject.toml`** — sezione principali:
```toml
[project]
name = "aria"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.6,<3.0",
    "fastmcp>=3.2,<4.0",
    "python-telegram-bot>=22.0,<23.0",
    "aiosqlite>=0.19",
    "lancedb>=0.30,<0.31",         # lazy import
    "cryptography>=42.0",
    "sops>=3.8",                   # binding CLI
    "keyring>=25.0",
    "secretstorage>=3.3",
    "httpx>=0.27",
    "tenacity>=8.2",               # retry/circuit breaker
    "croniter>=2.0",
    "python-dateutil>=2.8",
    "faster-whisper>=1.2,<2.0",    # default STT locale
    "openai-whisper>=20250625",    # fallback STT offline/API compatibility
    "pytesseract>=0.3",            # OCR
    "pillow>=10.0",
    "rich>=13.0",
    "typer>=0.12",
    "sd-notify>=0.1",              # sd_notify Python
]
```

Policy operativa dipendenze:
- `uv.lock` obbligatorio in repo per freeze riproducibile.
- Review semestrale pianificata + review straordinaria su security advisory o major release.
- CI con smoke test compatibilità su servizi core (`aria-memory`, `scheduler`, `gateway`).

---

## 5. Sottosistema di Memoria 5D

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 5.1 Tassonomia a 5 dimensioni

| Tipo         | Scope                             | Storage                              | Scrittura             | Lettura                |
|--------------|-----------------------------------|--------------------------------------|-----------------------|------------------------|
| **Working**  | sessione corrente, volatile       | context window LLM                   | automatica            | implicita              |
| **Episodic** | eventi/interazioni, verbatim      | SQLite `episodic.db`                 | ogni turn             | per range temporale/tag |
| **Semantic** | fatti consolidati, concetti       | SQLite FTS5 + LanceDB lazy           | distill async (CLM)   | per keyword/similarity  |
| **Procedural**| procedure, workflow, skill        | SKILL.md in filesystem               | definite manualmente  | progressive disclosure  |
| **Associative@fase2** | relazioni tra entità     | SQLite graph tables / Neo4j embedded | estrazione NER async  | query grafo             |

### 5.2 Storage Tiers

| Tier | Scopo                         | Backend                | Latenza target | Abilitato in  |
|------|-------------------------------|------------------------|----------------|---------------|
| T0   | raw verbatim episodic         | SQLite (WAL mode)      | <10ms          | MVP           |
| T1   | summaries + FTS5              | SQLite FTS5            | <50ms          | MVP           |
| T2   | embeddings semantici          | LanceDB (lazy-created) | <200ms         | MVP (opzionale, cache) |
| T3   | grafo associativo             | SQLite graph tables    | <500ms         | Fase 2        |

**Regola chiave (P6)**: T0 è **autoritativo e immutabile**. T1/T2/T3 sono **derivati** e ricostruibili da T0 ri-eseguendo il CLM.

Per T3 è vietato usare `pickle` come storage canonico: serializzazione ammessa solo in formato sicuro e versionabile (SQLite/JSON/Parquet/engine graph dedicato), da formalizzare in ADR (§18.H).

### 5.3 Actor-aware tagging

Ogni memory unit ha un campo `actor: Literal["user_input", "tool_output", "agent_inference", "system_event"]`. Questo è una delle tutele contro la "cristallizzazione dell'errore":

- **`user_input`**: messaggio originale dell'utente. Massimo trust.
- **`tool_output`**: output verificabile di un tool (e.g. API response). Alto trust.
- **`agent_inference`**: deduzione/ipotesi dell'LLM. Trust condizionato; **non promuovibile automaticamente** a fatto semantico. Per promuoverlo serve: (a) un secondo riscontro da tool_output, oppure (b) conferma esplicita `user_input`.
- **`system_event`**: log di sistema (avvii, errori). Metadato, non influenza inferenze.

### 5.4 Context Lifecycle Manager (CLM)

Il CLM è un processo asincrono (task schedulato o trigger on-event) che:

1. **Scansiona T0** (ultime N conversazioni chiuse)
2. **Distilla** → genera summary tipizzati (persone, fatti, decisioni, action items)
3. **Promuove** in T1 (FTS5) con actor tagging preservato
4. **(Opzionale, solo se feature flag attivo)** genera embedding T2 per gli item più "caldi" (frequenza di riferimento)
5. **Non cancella mai T0**.

Il CLM è implementato come **sub-agente `compaction-agent`** (§8.4), con prompt system che impone l'invariante "preserva provenienza, mai promuovere inferenze".

### 5.5 Schema Pydantic

**File**: `src/aria/memory/schema.py`

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal, Optional
from uuid import UUID, uuid4

class Actor(str, Enum):
    USER_INPUT = "user_input"
    TOOL_OUTPUT = "tool_output"
    AGENT_INFERENCE = "agent_inference"
    SYSTEM_EVENT = "system_event"

class EpisodicEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    ts: datetime
    actor: Actor
    role: Literal["user", "assistant", "system", "tool"]
    content: str                             # verbatim, NON sintetizzato
    content_hash: str                        # sha256
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, object] = Field(default_factory=dict)   # provider, model, tool_name, ecc.

class SemanticChunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_episodic_ids: list[UUID]          # provenienza T0
    actor: Actor                             # aggregato (downgrade se mix)
    kind: Literal["fact", "preference", "decision", "action_item", "concept"]
    text: str                                # sintesi distillata
    keywords: list[str] = Field(default_factory=list)
    confidence: float = 1.0                  # 0.0-1.0
    first_seen: datetime
    last_seen: datetime
    occurrences: int = 1
    embedding_id: Optional[UUID] = None      # se T2 attivato

class ProceduralSkill(BaseModel):
    id: str                                  # slug e.g. "deep-research"
    path: str                                # path a SKILL.md
    name: str
    description: str                         # ~100 tok per advertise
    trigger_keywords: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    version: str = "1.0.0"

class Association(BaseModel):                # @fase2
    id: UUID = Field(default_factory=uuid4)
    subject_id: UUID
    relation: str                            # "works_at", "prefers", "depends_on"
    object_id: UUID
    confidence: float = 1.0
    source_episodic_ids: list[UUID]
```

### 5.6 API interna + MCP server ARIA-Memory

**Modulo**: `src/aria/memory/mcp_server.py` (FastMCP)

Tool esposti (≤ 10, per rispettare P9):

| Tool              | Input                                          | Output                      | Note                          |
|-------------------|------------------------------------------------|-----------------------------|-------------------------------|
| `remember`        | `content`, `actor`, `role`, `session_id`, `tags[]` | `EpisodicEntry`         | scrive T0                     |
| `recall`          | `query`, `top_k=10`, `kinds?`, `since?`, `until?`| `list[SemanticChunk\|EpisodicEntry]` | prima FTS5, poi vettoriale se configurato |
| `recall_episodic` | `session_id` OR `since`, `limit=50`            | `list[EpisodicEntry]`       | cronologico                   |
| `distill`         | `session_id`                                   | `list[SemanticChunk]`       | trigger CLM on-demand         |
| `curate`          | `id`, `action=promote\|demote\|forget`         | `ok`                        | HITL-gated                    |
| `forget`          | `id`                                           | `ok`                        | soft delete + tombstone       |
| `stats`           | —                                              | `{t0_count, t1_count, ...}` | telemetria                    |

Le chiamate `curate(action=forget)` e `forget` richiedono **HITL** quando l'utente non sta interagendo esplicitamente (P7).

### 5.7 Governance memoria

- **Retention default**: T0 conservato 365 giorni, T1 indefinitamente (compresso dopo 90gg). Configurable.
- **Oblio programmato** (GDPR-like locale): comando `aria memory forget --session=<id>` con HITL.
- **Review queue**: entries con `actor=agent_inference` e `confidence < 0.7` vanno in review queue, l'utente può approvare/scartare via Telegram.
- **Backup**: `scripts/backup.sh` dump SQLite + tar cifrato con age, depositato in `~/.aria-backups/` con retention.

---

## 6. Scheduler & Autonomia

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

Pattern ispirato a **kiloclaw proactive scheduler**, semplificato per MVP ma già strutturato per scalare.

### 6.1 Task store SQLite — schema

**File**: `.aria/runtime/scheduler/scheduler.db`

```sql
CREATE TABLE IF NOT EXISTS tasks (
  id                TEXT PRIMARY KEY,         -- UUID
  name              TEXT NOT NULL,
  category          TEXT NOT NULL,            -- 'search' | 'workspace' | 'memory' | 'custom'
  trigger_type      TEXT NOT NULL,            -- 'cron' | 'event' | 'webhook' | 'oneshot' | 'manual'
  trigger_config    TEXT NOT NULL,            -- JSON
  schedule_cron     TEXT,                     -- e.g. '0 8 * * *'
  timezone          TEXT DEFAULT 'Europe/Rome',
  next_run_at       INTEGER,                  -- epoch ms
  status            TEXT NOT NULL DEFAULT 'active',    -- 'active'|'paused'|'dlq'|'completed'|'failed'
  policy            TEXT NOT NULL DEFAULT 'allow',     -- 'allow'|'ask'|'deny'
  budget_tokens     INTEGER,                  -- max token per run (null = unlimited)
  budget_cost_eur   REAL,                     -- max cost per run (null = unlimited)
  max_retries       INTEGER DEFAULT 3,
  retry_count       INTEGER DEFAULT 0,
  last_error        TEXT,
  owner_user_id     TEXT,                     -- telegram user id if external origin
  payload           TEXT NOT NULL,            -- JSON: prompt, sub_agent, tools_scoped
  created_at        INTEGER NOT NULL,
  updated_at        INTEGER NOT NULL
);

CREATE INDEX idx_tasks_next_run ON tasks(next_run_at) WHERE status='active';
CREATE INDEX idx_tasks_category ON tasks(category);

CREATE TABLE IF NOT EXISTS task_runs (
  id                TEXT PRIMARY KEY,
  task_id           TEXT NOT NULL REFERENCES tasks(id),
  started_at        INTEGER NOT NULL,
  finished_at       INTEGER,
  outcome           TEXT NOT NULL,            -- 'success'|'failed'|'blocked_budget'|'blocked_policy'|'timeout'
  tokens_used       INTEGER,
  cost_eur          REAL,
  result_summary    TEXT,                     -- breve testo di outcome
  logs_path         TEXT                      -- path a log dettagliato
);

CREATE TABLE IF NOT EXISTS dlq (
  id                TEXT PRIMARY KEY,
  task_id           TEXT NOT NULL REFERENCES tasks(id),
  last_run_id       TEXT REFERENCES task_runs(id),
  moved_at          INTEGER NOT NULL,
  reason            TEXT NOT NULL,
  payload_snapshot  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hitl_pending (
  id                TEXT PRIMARY KEY,
  task_id           TEXT REFERENCES tasks(id),
  run_id            TEXT REFERENCES task_runs(id),
  created_at        INTEGER NOT NULL,
  expires_at        INTEGER NOT NULL,
  question          TEXT NOT NULL,
  options_json      TEXT,                     -- scelta multipla
  channel           TEXT NOT NULL,            -- 'telegram'|'cli'
  user_response     TEXT,
  resolved_at       INTEGER
);
```

### 6.1.1 SQLite reliability baseline (obbligatoria)

- Runtime **DEVE** usare SQLite `>= 3.51.3` (o backport ufficiale equivalente) per mitigare bug WAL-reset.
- Ogni DB (`episodic.db`, `scheduler.db`, `sessions.db`) avvia con `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`.
- Policy checkpoint:
  - `wal_autocheckpoint=1000` pagine (default iniziale)
  - checkpoint manuale schedulato (`PRAGMA wal_checkpoint(TRUNCATE)`) almeno ogni 6h in quiet window
  - alert se WAL supera soglia configurabile (default 256MB) con notifica `system_event`.

### 6.2 Tipi di trigger

1. **`cron`**: espressione cron 5-field (con `croniter`), fuso orario rispettato. Esempio: `0 8 * * *` = ogni giorno 08:00.
2. **`event`**: internal event bus (memoria semantica che raggiunge soglia, task DLQ, credential rotation needed, ecc.).
3. **`webhook`**: endpoint HTTP locale (con auth HMAC) per trigger esterni.
4. **`oneshot`**: eseguito una sola volta a `next_run_at`, poi `status=completed`.
5. **`manual`**: solo via CLI `aria schedule run <task_id>` o Telegram `/run <task_id>`.

### 6.3 Budget gate

Ogni task ha budget opzionali **per run** e **per categoria-giornaliera**:

- `budget_tokens` per run (e.g. 50.000) → se superato mid-run, abort graceful.
- Aggregato `category_daily_budget_tokens` in config (e.g. `search=500k`, `workspace=100k`).
- Misura reale via counters esposti dal modello LLM (Claude returns usage); se non disponibili, stima approssimata.
- Violazione → `outcome=blocked_budget`, task in pausa per 24h, notifica utente.

### 6.4 Policy gate

Valori:
- **`allow`**: esegue senza chiedere (task di routine safe, read-only).
- **`ask`**: apre una `hitl_pending`, notifica Telegram/CLI, aspetta risposta con timeout (default 15min).
- **`deny`**: non esegue, logga. Utile per "ricordami di fare questo, non farlo da solo".

Policy è determinata da:
1. Override esplicito nel task
2. Default per categoria (`search=allow`, `workspace.read=allow`, `workspace.write=ask_if_not_explicit`, `memory.forget=ask`)
3. Override per orario (Quiet Hours: se `ask` scade in quiet hours, auto-`deny` o deferred al mattino)

### 6.5 DLQ e retry

- Dopo `max_retries` fallimenti consecutivi → task → DLQ, `status=dlq`.
- DLQ check ogni 60s: i task in DLQ non vengono ri-provati automaticamente; solo `aria schedule replay <id>` li riattiva.
- Log dettagliato in `dlq.reason` + payload snapshot.

### 6.6 Systemd user service + sd_notify

**File**: `systemd/aria-scheduler.service` (copiato in `~/.config/systemd/user/`)

```ini
[Unit]
Description=ARIA Scheduler Daemon
After=default.target

[Service]
Type=notify
WorkingDirectory=%h/coding/aria
EnvironmentFile=%h/coding/aria/.env
ExecStart=%h/coding/aria/.venv/bin/python -m aria.scheduler.daemon
Restart=on-failure
RestartSec=5s
WatchdogSec=60s
NotifyAccess=main

# hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=tmpfs
ReadWritePaths=%h/coding/aria/.aria
PrivateTmp=true
PrivateDevices=true
ProtectControlGroups=true
ProtectKernelModules=true
ProtectKernelTunables=true
RestrictSUIDSGID=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native

[Install]
WantedBy=default.target
```

Il daemon chiama `sdnotify.SystemdNotifier().notify('WATCHDOG=1')` ogni ~30s; se silenzio > 60s, systemd restart.

Le stesse direttive di hardening (con `ReadWritePaths` adattato) si applicano anche a `aria-gateway.service` e, se separato, `aria-memory.service`.

### 6.7 Quiet Hours, rate limiting, circuit breaker

- **Quiet hours**: range orario in `ARIA_QUIET_HOURS`; durante, policy `ask` → `defer_to_morning` (riabilitato al termine).
- **Rate limiting**: token bucket per categoria, bloccante.
- **Circuit breaker**: errori consecutivi su una provider (e.g. Tavily fallisce 5 volte in 10min) → provider skipped per 30min, fallback automatico.

---

## 7. Gateway Esterno

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 7.1 Architettura

Gateway Python standalone, daemon systemd. In MVP **solo Telegram**; architettura già predisposta per multi-canale in Fase 2.

Implementazione Telegram allineata a `python-telegram-bot` v22 (`Application` async nativa), con handler non bloccanti e retry espliciti sugli errori di rete.

```
┌────────────────────────────────────────────────────┐
│  Gateway Daemon (Python)                           │
│  ├─ Channel Adapters                               │
│  │   └─ Telegram (python-telegram-bot)             │
│  ├─ Session Manager (SQLite mapping)               │
│  ├─ Auth & Authz (whitelist + HMAC per webhook)    │
│  ├─ Multimodal Handlers                            │
│  │   ├─ Image → OCR (pytesseract) / VLM pass-thru  │
│  │   └─ Voice → Whisper (locale o API)             │
│  └─ ARIA Core invoker (spawn KiloCode child)       │
└────────────────────────────────────────────────────┘
```

### 7.2 Sessioni multi-utente isolate

Tabella `gateway_sessions`:
```sql
CREATE TABLE gateway_sessions (
  id                TEXT PRIMARY KEY,
  channel           TEXT NOT NULL,             -- 'telegram'|'slack'|...
  external_user_id  TEXT NOT NULL,             -- e.g. telegram user id
  aria_session_id   TEXT NOT NULL,             -- FK verso KiloCode session
  created_at        INTEGER NOT NULL,
  last_activity     INTEGER NOT NULL,
  locale            TEXT DEFAULT 'it-IT',
  state_json        TEXT                       -- flags, preferenze, workflow active
);
CREATE UNIQUE INDEX ux_gateway_session ON gateway_sessions(channel, external_user_id);
```

### 7.3 Autenticazione

- **Whitelist**: solo `external_user_id` in `ARIA_TELEGRAM_WHITELIST`. Messaggi da ID non whitelisted → log + scartati silenziosamente.
- **Webhook ingress** (se gateway accetta webhook Telegram invece di polling): HMAC-SHA256 con secret rotabile.
- **Escalation**: in Fase 2 introduzione di ruoli (`owner`, `guest`) per preparare multi-user.

### 7.4 Multimodalità

- **Immagini**: download da Telegram → se task richiede vision, passaggio diretto a modello (se supporta) oppure fallback OCR pytesseract.
- **Voce**: download audio → STT locale `faster-whisper` (default) → fallback `openai-whisper` → testo → normalizzato come `user_input`.
- **Documenti PDF**: skill `pdf-extract` (PyMuPDF) → testo → ingesto come episodic.

### 7.5 Roadmap canali

| Canale     | MVP | Fase 2 | Note                                    |
|------------|-----|--------|-----------------------------------------|
| CLI        | ✅  |        | sempre disponibile                      |
| Telegram   | ✅  |        | `python-telegram-bot`                   |
| Slack      |     | ✅     | eventualmente via GolemBot adapter port |
| WhatsApp   |     | ✅     | via WA Business API                     |
| Discord    |     | ✅     |                                         |
| WebUI      |     | ✅     | Tauri+React o FastAPI+HTMX              |

---

## 8. Gerarchia Agenti

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 8.1 Regola strutturale (inderogabile)

```
ORCHESTRATOR (ARIA-Conductor)
  └─> SUB-AGENT (es. search-agent, workspace-agent)
        └─> SKILL (es. deep-research, triage-email)
              └─> TOOL (MCP tool o script Python locale)
```

**Ciascun livello ha responsabilità circoscritte** e non salta livelli inferiori:
- L'orchestrator **non chiama tool** direttamente; delega a sub-agenti.
- I sub-agenti **usano skill** per workflow complessi e tool per operazioni atomiche.
- Le skill **non definiscono tool**; orchestrano tool esistenti.

### 8.2 ARIA-Conductor (orchestrator primario)

**File**: `.aria/kilocode/agents/aria-conductor.md`

Ruolo: **dispatcher cognitivo**, entry point di ogni interazione. Classifica intent, pianifica, delega a sub-agenti via child sessions, sintetizza il risultato finale.

Modello LLM: **selezione manuale dall'utente** via slash command KiloCode (`/model <id>`) in MVP. In Fase 2, routing automatico per intent.

Capabilities:
- Leggere tutto l'albero memoria (ARIA-Memory MCP)
- Spawn child sessions (uno per sub-agente)
- Invocare skill `planning-with-files` per workflow complessi
- **NO accesso diretto** a tool di ricerca web, Google Workspace, filesystem pesante

```markdown
---
name: aria-conductor
type: primary
description: Entry point orchestratore di ARIA. Dispatcher cognitivo.
color: "#FFD700"
category: orchestration
temperature: 0.2
allowed-tools:
  - aria-memory/*
  - sequential-thinking/*
  - spawn-subagent
required-skills:
  - planning-with-files
  - hitl-queue
mcp-dependencies: []
---

# ARIA-Conductor

## Ruolo
Sei il conduttore di ARIA. Non esegui mai direttamente task operativi.
Comprendi l'intento dell'utente, ti aggiorni dalla memoria ARIA, pianifichi
una decomposizione in sub-task, delegali al sub-agente più adatto tramite
`spawn-subagent`, raccogli risultati, sintetizza risposta finale.

## Principi
- Prima di rispondere su argomenti persistenti, INTERROGA la memoria via
  `aria-memory/recall`.
- Per richieste >3 passi, USA `planning-with-files` per creare un piano.
- Ogni azione potenzialmente distruttiva/costosa → apri HITL via
  `hitl-queue/ask`.
- Non inventare fatti: se non trovi in memoria o in tool output, dichiaralo.

## Sub-agenti disponibili
- `search-agent`: ricerca web, analisi fonti, news
- `workspace-agent`: Gmail, Calendar, Drive, Docs, Sheets
- `compaction-agent` (system): chiamato dal CLM, non da te
- `memory-curator` (system): per review queue inferenze
```

### 8.3 Sub-agenti OPERATIVI (MVP)

#### 8.3.1 Search-Agent

**File**: `.aria/kilocode/agents/search-agent.md`

```markdown
---
name: search-agent
type: subagent
description: Ricerca web e sintesi informazioni da fonti online
color: "#2E86AB"
category: research
temperature: 0.1
allowed-tools:
  - tavily-mcp/search
  - firecrawl-mcp/scrape
  - firecrawl-mcp/extract
  - brave-mcp/web_search
  - brave-mcp/news_search
  - exa-script/search
  - searxng-script/search
  - aria-memory/remember
  - aria-memory/recall
  - fetch/fetch
required-skills:
  - deep-research
  - source-dedup
mcp-dependencies: [tavily, firecrawl, brave, exa, searxng]
---

# Search-Agent
Orchestri provider multipli con rotation intelligente. Vedi §11.
```

#### 8.3.2 Workspace-Agent

**File**: `.aria/kilocode/agents/workspace-agent.md`

```markdown
---
name: workspace-agent
type: subagent
description: Operazioni Gmail, Calendar, Drive, Docs, Sheets via Google Workspace MCP
color: "#4285F4"
category: productivity
temperature: 0.1
allowed-tools:
  - google_workspace/search_gmail_messages
  - google_workspace/get_gmail_message_content
  - google_workspace/send_gmail_message
  - google_workspace/list_calendars
  - google_workspace/get_events
  - google_workspace/create_event
  - google_workspace/search_drive_files
  - google_workspace/get_drive_file_content
  - google_workspace/get_presentation
  - google_workspace/get_page
  - google_workspace/read_presentation_comments
  - google_workspace/create_doc
  - google_workspace/read_sheet_values
  - google_workspace/modify_sheet_values
  - aria-memory/remember
  - aria-memory/recall
  - aria-memory/hitl_ask
required-skills:
  - triage-email
  - calendar-orchestration
  - doc-draft
mcp-dependencies: [google_workspace]
---

# Workspace-Agent
Vedi §12 per spec dettagliata (OAuth, scope, handbook comandi).
```

### 8.4 Sub-agenti di SISTEMA

Invisibili all'utente, invocati in automatico dai flussi interni.

| Agent                | Trigger                                    | Funzione                                             |
|----------------------|--------------------------------------------|------------------------------------------------------|
| `compaction-agent`   | post-session + scheduler ogni 6h           | CLM: distilla T0 → T1                                |
| `summary-agent`      | fine sessione                              | genera title + summary sessione                      |
| `memory-curator`     | cron giornaliero + on-demand               | review queue, promote/demote, oblio programmato      |
| `blueprint-keeper`   | cron settimanale (domenica 10:00)          | scansione codice, divergenze, PR di update blueprint |
| `security-auditor`   | cron settimanale                           | audit permessi, scope, credential usage, anomalies   |

### 8.5 Matrice capabilities (tool access)

| Sub-Agent          | aria-memory | tavily | firecrawl | brave | exa | searxng | google_* | playwright | filesystem | git | github |
|--------------------|:-----------:|:------:|:---------:|:-----:|:---:|:-------:|:--------:|:----------:|:----------:|:---:|:------:|
| aria-conductor     | ✅          |        |           |       |     |         |          |            |            |     |        |
| search-agent       | ✅          | ✅     | ✅        | ✅    | ✅  | ✅      |          | ✅ @fase2  |            |     |        |
| workspace-agent    | ✅          |        |           |       |     |         | ✅       |            |            |     |        |
| compaction-agent   | ✅          |        |           |       |     |         |          |            |            |     |        |
| summary-agent      | ✅          |        |           |       |     |         |          |            |            |     |        |
| memory-curator     | ✅          |        |           |       |     |         |          |            |            |     |        |
| blueprint-keeper   | ✅          |        |           |       |     |         |          |            | ✅ ro      | ✅  | ✅     |
| security-auditor   | ✅          |        |           |       |     |         |          |            | ✅ ro      | ✅  |        |

**ro = read only**. Il totale tool di ciascun sub-agente **MUST** ≤ 20 (P9).

### 8.6 Child sessions isolate

Ogni delega a un sub-agente avvia una **child session** KiloCode separata, con:
- Context window **non condivisa** con il Conductor (pulita)
- Transcript salvata in `sessions/children/<id>.json`
- Output di ritorno serializzato come JSON con `{status, result, tokens_used, tools_invoked[]}`
- Timeout configurabile (default 10min, override per task)

---

## 9. Skills Layer

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 9.1 Formato SKILL.md

**Path**: `.aria/kilocode/skills/<skill-slug>/SKILL.md`

```markdown
---
name: deep-research
version: 1.0.0
description: Ricerca web approfondita multi-provider con deduplica e sintesi
trigger-keywords: [ricerca, search, approfondisci, analizza tema]
user-invocable: true
allowed-tools:
  - tavily-mcp/search
  - firecrawl-mcp/scrape
  - brave-mcp/web_search
  - exa-script/search
  - aria-memory/remember
max-tokens: 50000
estimated-cost-eur: 0.10
---

# Deep Research Skill

## Obiettivo
Condurre una ricerca tematica su N query, deduplicare risultati, estrarre
contenuti, sintetizzare report strutturato.

## Procedura
1. Pianifica 3-7 sub-query diverse che coprono il tema da angolazioni distinte
2. Per ogni sub-query invoca il router (§11): Tavily > Brave > Firecrawl > Exa
3. Deduplica URL (Levenshtein title + URL canonicalization)
4. Per top-N risultati, scrape full content via firecrawl
5. Classifica per rilevanza e data
6. Sintetizza report con sezioni: TL;DR, Findings, Open Questions, Sources
7. Salva report in memoria episodica con tag `research_report`
8. (Opzionale) esporta in Google Drive via workspace-agent

## Invarianti
- Cita SEMPRE le fonti con URL
- Se fonti contraddittorie, riportale entrambe
- Se meno di 3 fonti trovate, dichiara "ricerca povera"
```

Struttura directory:
```
.aria/kilocode/skills/deep-research/
├── SKILL.md                    # spec + procedura
├── scripts/
│   ├── dedup_urls.py           # helper
│   └── canonicalize.py
└── resources/
    ├── prompt_synthesis.md     # sub-prompt di sintesi
    └── report_template.md
```

### 9.2 Progressive Disclosure (pattern Anthropic Agent Skills)

4 stadi canonici:

1. **Advertise** (~100 token): solo `name` + `description` sono iniettati nel system prompt. Il modello decide se caricare.
2. **Load**: invocazione `load_skill(name)` → carica `SKILL.md` body.
3. **Read resource**: `read_skill_resource(name, resource_id)` → carica file sotto `resources/`.
4. **Run script**: `run_skill_script(name, script_id, args)` → esegue sandbox script Python.

In MVP implementiamo **stadi 1 e 2** nativamente; stadi 3-4 se KiloCode li supporta nativamente (controllare upstream). Fallback: inclusione diretta dei contenuti quando il modello carica.

### 9.3 Registry e attivazione

`.aria/kilocode/skills/_registry.json` (auto-generato da scan della directory):

```json
{
  "skills": [
    { "name": "planning-with-files", "path": "planning-with-files/SKILL.md", "version": "1.0.0", "category": "system" },
    { "name": "deep-research", "path": "deep-research/SKILL.md", "version": "1.0.0", "category": "research" },
    { "name": "triage-email", "path": "triage-email/SKILL.md", "version": "0.9.0", "category": "workspace" },
    { "name": "pdf-extract", "path": "pdf-extract/SKILL.md", "version": "1.0.0", "category": "ingest" },
    { "name": "hitl-queue", "path": "hitl-queue/SKILL.md", "version": "1.0.0", "category": "system" },
    { "name": "memory-distillation", "path": "memory-distillation/SKILL.md", "version": "1.0.0", "category": "memory" },
    { "name": "blueprint-keeper", "path": "blueprint-keeper/SKILL.md", "version": "1.0.0", "category": "governance" }
  ]
}
```

### 9.4 Skills versioning policy (obbligatoria)

Per evitare drift funzionale tra skill e tool signatures:

- Ogni skill usa `semver` (`MAJOR.MINOR.PATCH`).
- Ogni release skill aggiorna `compatibility` in metadata (`requires_tools`, `min_versions`, `breaking_changes`).
- Ogni `MAJOR` richiede ADR se impatta flussi utente o policy HITL.
- CI valida `_registry.json` contro firme tool correnti (`mcp.json` + wrapper locali).

### 9.5 Skills fondative MVP

1. **planning-with-files**: pianificazione strutturata su file (`task_plan.md`, `findings.md`, `progress.md`) — pattern kilo_kit.
2. **deep-research**: ricerca multi-provider (vedi §9.1).
3. **pdf-extract**: PyMuPDF → testo + metadata, salva in memoria.
4. **triage-email**: classifica Inbox per urgenza, genera digest.
5. **memory-distillation**: invoca CLM su range/sessione.
6. **hitl-queue**: interfaccia gate HITL verso Telegram.
7. **blueprint-keeper**: scansione codice vs blueprint, PR automatica.

---

## 10. Tools & MCP Ecosystem

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 10.1 Tool Priority Ladder (P8 richiamato)

Quando serve una nuova capability:
1. **MCP esistente maturo** → configurare
2. **Skill che compone MCP esistenti** → scrivere SKILL.md
3. **Script Python locale** → `src/aria/tools/` e promuovere a MCP custom entro 2 sprint

È **vietato** aggiungere Python se esiste MCP equivalente, ed è **vietato** aggiungere MCP se una skill copre il caso via composizione.

### 10.2 Scoped toolsets per sub-agente (MVP)

In KiloCode, ogni agent definisce `allowed-tools` (lista esplicita di `server/tool_name` con wildcard). Il Conductor può leggere la matrice §8.5 per scoprire chi fa cosa ma **non può chiamare direttamente** i tool dei sub-agenti: deve delegare.

### 10.3 MCP server inclusi in MVP

**File**: `.aria/kilocode/mcp.json` (esempio condensato)

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/fulvio/coding/aria"],
      "disabled": false
    },
    "git": {
      "command": "uvx",
      "args": ["mcp-server-git", "--repository", "/home/fulvio/coding/aria"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}" }
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    },
    "aria-memory": {
      "command": "/home/fulvio/coding/aria/.venv/bin/python",
      "args": ["-m", "aria.memory.mcp_server"],
      "env": { "ARIA_HOME": "/home/fulvio/coding/aria" }
    },
    "tavily": {
      "command": "/home/fulvio/coding/aria/scripts/wrappers/tavily-wrapper.sh"
    },
    "firecrawl": {
      "command": "/home/fulvio/coding/aria/scripts/wrappers/firecrawl-wrapper.sh"
    },
    "brave": {
      "command": "npx",
      "args": ["-y", "@brave/brave-search-mcp-server"],
      "env": { "BRAVE_API_KEY": "${BRAVE_API_KEY_ACTIVE}" }
    },
    "google_workspace": {
      "command": "uvx",
      "args": ["google_workspace_mcp"],
      "env": {
        "GOOGLE_OAUTH_CLIENT_ID": "${GOOGLE_OAUTH_CLIENT_ID}",
        "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8080/callback",
        "GOOGLE_OAUTH_USE_PKCE": "true",
        "GOOGLE_OAUTH_CLIENT_SECRET": "${GOOGLE_OAUTH_CLIENT_SECRET_OPTIONAL}"
      }
    },
    "playwright": {
      "command": "npx",
      "args": ["-y", "@executeautomation/playwright-mcp-server"],
      "disabled": true,
      "_comment": "@fase2"
    }
  }
}
```

I wrapper bash (`tavily-wrapper.sh`, `firecrawl-wrapper.sh`) invocano il relativo MCP passando per il `credential_manager.py` per key rotation.

### 10.4 Wrapper Python per API non-MCP

Struttura base: ogni script Python in `src/aria/tools/<provider>/cli.py` è invocabile via CLI e implementa un'interfaccia minimale (`--op <name> --args-json '{...}'`). Quando raggiunge maturità, viene riscritto come server FastMCP in `src/aria/tools/<provider>/mcp_server.py` e registrato in `mcp.json`.

### 10.5 Roadmap Fase 2 anti-bloat

- **MCP Gateway custom** (Python): proxy che espone solo i tool rilevanti per la sessione corrente, basato su scope dichiarativo + heuristic query.
- **Valutazione di `mcp-compressor`** (Atlassian Labs) come alternativa ready-made.
- **Anthropic Tool Search API**: attivare se supportato da KiloCode + modello.

---

## 11. Sub-Agent di Ricerca Web

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 11.1 Provider supportati (MVP)

| Provider       | Tier gratuito          | Forte su                    | Costo incremento       |
|----------------|-----------------------|----------------------------|------------------------|
| **Tavily**     | 1.000 req/mese         | LLM-ready synthesis, news  | $0.008/req base        |
| **Firecrawl**  | 500 credits lifetime   | deep scraping, extract AI  | ~$0.005–0.015/page     |
| **Brave**      | $5/mese free credits   | privacy, volume (50 req/s) | $0.005/web, $0.004/ans |
| **Exa**        | 1.000 req/mese         | semantic search academic   | $0.007/req             |
| **SearXNG**    | self-hosted, illimitato| meta, privacy totale       | zero (solo infra)      |
| **SerpAPI**    | 100 req/mese           | fallback di ultima istanza | $5/1k                  |

DuckDuckGo esplicitamente escluso (no API ufficiale, scraping fragile).

### 11.2 Logica di routing (intent-aware)

Il router Python (`src/aria/agents/search/router.py`) classifica l'intent della query e seleziona provider:

```python
INTENT_ROUTING = {
    "news":             ["tavily", "brave_news"],
    "academic":         ["exa", "tavily"],
    "deep_scrape":      ["firecrawl_extract", "firecrawl_scrape"],
    "general":          ["brave", "tavily"],
    "privacy":          ["searxng", "brave"],
    "fallback":         ["serpapi"],
}
```

Il classifier è una mini-skill `intent-classifier` basata su keyword + (opzionale) zero-shot LLM call su Haiku 4.5.

### 11.3 Rotation API keys con circuit breaker

Pattern mutuato da `fulvian/kilo_kit` potenziato con SOPS.

Stato per-chiave (persistito in `.aria/runtime/credentials/providers_state.enc.yaml`, cifrato e fuori git):

```yaml
providers:
  tavily:
    keys:
      - key_id: tvly-1
        credits_total: 1000
        credits_used: 0
        circuit_state: closed       # closed|open|half_open
        failure_count: 0
        cooldown_until: null
        last_used_at: null
        last_error: null
      - key_id: tvly-2
        credits_total: 1000
        ...
    rotation_strategy: least_used   # round_robin | least_used | failover
```

`credential_manager.py` espone:
```python
cm = CredentialManager()
key = cm.acquire("tavily", strategy="least_used")    # restituisce chiave + budget info
try:
    response = call_api(key)
    cm.report_success("tavily", key.id, credits_used=1)
except RateLimitError:
    cm.report_failure("tavily", key.id, reason="rate_limit")
    key = cm.acquire("tavily")                       # ottiene prossima
```

Circuit breaker: dopo 3 failure consecutivi in 5min → `circuit_state=open` per 30min → `half_open` (1 tentativo) → `closed` se ok, `open` se fail.

### 11.4 Deduplicazione e ranking multi-provider

`src/aria/agents/search/dedup.py`:
1. URL canonicalization (rimozione utm_, query params non significativi)
2. Fuzzy match titoli con Levenshtein (ratio ≥ 0.85 = duplicato)
3. Score aggregato: `score = provider_weight × relevance × recency_decay`

### 11.5 Caching

- Cache query→results in memoria episodica tagged `search_cache` con TTL default 6h
- Hit ratio atteso ≥ 20% (utente ripete argomenti)
- `aria search --no-cache` per forzare bypass

### 11.6 Provider exhaustion e graceful degradation

Runbook deterministico quando quote/crediti sono esauriti:

1. Health-check provider all'avvio e ogni 5 minuti (`available`, `degraded`, `down`, `credits_exhausted`).
2. Fallback tree per intent:
   - `news/general`: Tavily → Brave → SearXNG → cache stale (con banner `degraded`).
   - `deep_scrape`: Firecrawl → fetch+readability locale → solo metadata+fonti.
   - `academic`: Exa → Tavily → Brave web.
3. Se tutti i provider esterni sono indisponibili: modalità `local-only` (cache + SearXNG self-hosted se presente), risposta esplicita all'utente con qualità ridotta.
4. Notifica `system_event` + report giornaliero con tasso degradazione.

Runbook operativo: `docs/operations/provider_exhaustion.md`.

---

## 12. Sub-Agent Google Workspace

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 12.1 Dipendenza

**Upstream**: `taylorwilsdon/google_workspace_mcp` v1.19.0+ (stable aprile 2026), licenza MIT, runtime Python 3.10+, installato via `uvx workspace-mcp`.

### 12.2 Scope minimi

In fase iniziale ARIA richiede **il minimo principio di privilegio**; scope aggiuntivi abilitati on-demand con nuovo consent.

| Servizio  | Scope                        | Giustificazione                     |
|-----------|------------------------------|-------------------------------------|
| Gmail     | `gmail.readonly`             | lettura e classificazione           |
| Gmail     | `gmail.modify`               | label, archive, no delete           |
| Gmail     | `gmail.send`                 | invio esplicito email               |
| Calendar  | `calendar.readonly`          | lettura eventi sempre autorizzata   |
| Calendar  | `calendar.events`            | creazione/modifica eventi           |
| Drive     | `drive.readonly`             | ricerca/lettura file utente         |
| Drive     | `drive.file`                 | scrittura file gestiti da ARIA      |
| Docs      | `documents.readonly`         | lettura documenti                   |
| Docs      | `documents`                  | scrittura documenti                 |
| Sheets    | `spreadsheets.readonly`      | lettura fogli                       |
| Sheets    | `spreadsheets`               | scrittura fogli                     |
| Slides    | `presentations.readonly`     | lettura presentazioni e contenuto   |

Gli scope sono configurati in `.env` (commentabili):
```
GOOGLE_WORKSPACE_SCOPES=gmail.readonly,gmail.modify,gmail.send,calendar.readonly,calendar.events,drive.readonly,drive.file,documents.readonly,documents,spreadsheets.readonly,spreadsheets,presentations.readonly
```

### 12.3 OAuth flow (PKCE-first)

1. **First-time setup** (`scripts/oauth_first_setup.py`): apre browser sul consent screen con **PKCE secret-less** come default; redirect su `localhost:8080/callback`, lo script intercetta, memorizza `refresh_token` nell'**OS keyring** (Linux Secret Service, Gnome-keyring o KWallet) sotto service name `aria.google_workspace`, account `primary`.
2. **Runtime**: il server MCP Google Workspace recupera `refresh_token` dal keyring via API standard `keyring.get_password()`, refresh `access_token` quando scaduto, transparente per l'agente. **Utente non deve riautenticarsi** se non scade il refresh (Google: fino a 6 mesi di inattività o revoca esplicita).
3. **Escalation controllata**: `client_secret` è opzionale e ammesso solo quando richiesto da specifica app policy/provider edge-case; deve essere documentato in ADR security.
4. **Revoca**: `aria workspace revoke` → chiama Google revoke endpoint + rimuove keyring entry. Nuovo setup richiede rerun di `oauth_first_setup.py`.

### 12.4 Multi-account (Fase 2)

Keyring service name pattern: `aria.google_workspace.<account_label>`. Router seleziona account per operazione (header `X-Aria-Account`).

### 12.5 Handbook comandi (esempi)

| Comando utente                                       | Tool invocato                      |
|-----------------------------------------------------|------------------------------------|
| "Leggi le mie ultime email non lette"               | `google_workspace/search_gmail_messages` |
| "Quanti meeting ho domani?"                         | `google_workspace/get_events`      |
| "Crea un evento per lunedì alle 10 con X"           | `google_workspace/create_event` (autorizzazione implicita; HITL solo se rischio alto) |
| "Riassumi il doc 'Q2 Strategy'"                     | `google_workspace/search_docs` → `google_workspace/get_doc_content` → skill `memory-distillation` |
| "Aggiorna il foglio Budget con questi valori"       | `google_workspace/modify_sheet_values` (HITL `ask`) |

Le operazioni **read** sono sempre `policy=allow`. Le operazioni **write** usano `policy=ask` solo quando non richieste esplicitamente dall'utente o quando il rischio e alto.

### 12.6 Retrieval fidelity (obbligatoria)

Per richieste di ricerca documentale in Drive/Slides/Docs, il Workspace-Agent **DEVE**:
1. Preservare tutti i vincoli espliciti del prompt (tema, autore, periodo, tipo file).
2. Usare query progressive con termini quotati e sinonimi, senza perdere i filtri chiave.
3. Validare la pertinenza leggendo un estratto del contenuto prima di sintetizzare.
4. Scartare risultati nominalmente simili ma semanticamente fuori tema.

---

## 13. Credential Management

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 13.1 Schema cifrato SOPS+age

**File** (in GIT cifrato): `.aria/credentials/secrets/api-keys.enc.yaml`

Contenuto (visualizzato decrypted):
```yaml
# api-keys.yaml — API keys for free/paid providers
version: 1
providers:
  tavily:
    - id: tvly-1
      key: tvly-dev-XXXXXXXXXXXX
      owner: fulvio-primary
      credits_total: 1000
    - id: tvly-2
      key: tvly-dev-YYYYYYYYYYYY
      owner: fulvio-secondary
      credits_total: 1000
  firecrawl:
    - id: fc-1
      key: fc-XXXXXXXXXXXX
      credits_total: 500
  brave:
    - id: brave-1
      key: BSA-XXXXXXXXXXXX
      credits_monthly_eur: 5.00
  exa:
    - id: exa-1
      key: exa-XXXXXXXXXXXX
      credits_total: 1000
  serpapi:
    - id: serp-1
      key: XXXXXXXXXXXX
      credits_monthly: 100
github:
  token: ghp_XXXXXXXXXXXX
openai:
  api_key: sk-XXXXXXXXXXXX       # opzionale per Whisper API
```

**File** (in GIT, non cifrato): `.sops.yaml`

```yaml
creation_rules:
  - path_regex: \.aria/credentials/secrets/.*\.enc\.yaml$
    age: age1XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX        # public key di Fulvio
    encrypted_regex: '^(key|token|api_key|secret|password)$'
```

### 13.2 Workflow rotazione

1. Utente aggiunge nuova key Tavily via dashboard Tavily.
2. `sops .aria/credentials/secrets/api-keys.enc.yaml` apre editor decrypted.
3. Aggiunge entry `- id: tvly-3 …`.
4. Save → SOPS ricifra automaticamente.
5. `aria creds reload` → il credential manager ricarica stato.

Lo stato runtime (usage counter, circuit state) è in file separato `.aria/runtime/credentials/providers_state.enc.yaml` (cifrato, fuori git, aggiornabile ad alta frequenza). Snapshot firmati periodici possono essere esportati in `docs/operations/` o backup cifrati.

### 13.3 OS keyring per OAuth

Solo refresh_token Google Workspace vanno nel keyring (Secret Service su Linux). Pattern:

```python
import keyring
keyring.set_password("aria.google_workspace", "primary", refresh_token)
rt = keyring.get_password("aria.google_workspace", "primary")
```

Fallback per sistemi senza Secret Service: file cifrato age, decryption on-demand con age key (separata dalla SOPS key).

### 13.4 Unified `credential_manager.py`

API pubblica (Python):
```python
from aria.credentials import CredentialManager

cm = CredentialManager()

# API key acquisition con rotation
key_info = cm.acquire(provider="tavily", strategy="least_used")
# key_info.key, key_info.id, key_info.budget_remaining

# OAuth token
oauth = cm.get_oauth(service="google_workspace", account="primary")
# oauth.access_token (auto-refresh), oauth.scopes

# Success/failure reporting
cm.report_success(provider="tavily", key_id=key_info.id, credits_used=1)
cm.report_failure(provider="tavily", key_id=key_info.id, reason="rate_limit", retry_after=60)

# Osservabilità
status = cm.status(provider="tavily")
# {active_keys, blocked_keys, credits_remaining_total, ...}
```

### 13.5 Circuit breaker

- **Closed** (normale) → errori rari tollerati
- **Open** (blocco) → dopo N failure/ΔT (default: 3/5min)
  - cooldown `cooldown_until = now + 30min`
  - acquire() skippa questa chiave
- **Half-open** → dopo cooldown, permette 1 tentativo; se ok → closed, se fail → open esteso

Parametri tunabili in config.

### 13.6 Audit logging

Ogni chiamata `cm.acquire/report_*` produce un record JSON in `.aria/runtime/logs/credentials_YYYY-MM-DD.log`:

```json
{"ts":"2026-04-20T14:32:10Z","op":"acquire","provider":"tavily","key_id":"tvly-1","result":"ok","credits_remaining":847}
{"ts":"2026-04-20T14:33:01Z","op":"report_failure","provider":"firecrawl","key_id":"fc-1","reason":"rate_limit","circuit_state_after":"open"}
```

Log ruotati giornalmente, retention 90gg.

---

## 14. Governance & Osservabilità

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 14.1 Logging (structured JSON)

- Formato: JSON line, UTC ISO8601 ts, `level`, `logger`, `event`, `context{}`.
- Destinazioni: file giornaliero in `.aria/runtime/logs/`; stdout se interactive.
- Livelli: `DEBUG|INFO|WARN|ERROR|CRITICAL`. Default `INFO`.
- Correlation: ogni action ha `trace_id` propagato lungo la catena Gateway → Conductor → Sub-Agent → Tool.

### 14.2 Metriche Prometheus-ready

Endpoint opzionale `http://localhost:9090/metrics` esposto dal gateway daemon:
- bind esplicito `127.0.0.1` (no `0.0.0.0`)
- se esposto remotamente in Fase 2+: obbligo mTLS o reverse proxy autenticato
- `aria_tasks_total{category,status}` counter
- `aria_task_duration_seconds{category}` histogram
- `aria_tokens_used_total{model,provider}` counter
- `aria_memory_entries_total{tier}` gauge
- `aria_credential_circuit_state{provider,key_id}` gauge (0/1/2)
- `aria_hitl_pending_total` gauge

### 14.3 Policy di sicurezza

- **Nessun accesso root**: tutto in user space.
- **Sandbox** (Fase 2): execution di script generati in container Docker (simile a Daytona).
- **No-destroy without HITL** (P7): elimina, overwrite, send → default `ask`.
- **Nessuna esfiltrazione silenziosa**: se un tool esterno viene chiamato verso dominio non nella whitelist (`ARIA_EGRESS_WHITELIST`), warn loggato.
- **Prompt injection mitigation**: input da tool_output viene incapsulato in un frame `<<TOOL_OUTPUT>>...<</TOOL_OUTPUT>>` e il system prompt del conductor istruisce a **non eseguire** istruzioni trovate in tool output.

### 14.4 Backup memoria

**Script**: `scripts/backup.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail
: "${ARIA_HOME:?}"
TS=$(date +%Y%m%d-%H%M%S)
DEST="$HOME/.aria-backups/aria-backup-$TS.tar.age"
tar -czf - -C "$ARIA_HOME" .aria/runtime .aria/credentials \
  | age -r $(cat "$ARIA_HOME/.age-backup.pub") \
  -o "$DEST"
find "$HOME/.aria-backups" -mtime +30 -type f -delete
echo "backup: $DEST"
```

Schedulato daily via `aria schedule add --cron '0 3 * * *' --name daily-backup …`.

### 14.5 ADR workflow

**Directory**: `docs/foundation/decisions/`

**File**: `ADR-NNNN-<slug>.md`

Template (vedi §18.D). Ogni ADR ha: title, status (Proposed|Accepted|Superseded), context, decision, consequences, references. La `blueprint-keeper` skill referenzia gli ADR pertinenti nelle sezioni del blueprint che impattano.

---

## 15. Roadmap di Implementazione

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### FASE 0 — Foundation (1-2 sprint, ~2 settimane)

**Obiettivo**: ambiente ARIA isolato, bootstrap completo, zero logica agentica.

Deliverable:
- [ ] Struttura directory `/home/fulvio/coding/aria/` completa
- [ ] Launcher `bin/aria` funzionante
- [ ] KiloCode CLI consumabile via `KILOCODE_CONFIG_DIR`
- [ ] Git repo con `.gitignore`, `.sops.yaml`, SOPS+age configurato, key pair generata
- [ ] `pyproject.toml` con deps, venv `.venv/`
- [ ] Skeleton `src/aria/` con moduli vuoti
- [ ] Unit file systemd (non ancora installati)
- [ ] Bootstrap script `scripts/bootstrap.sh` idempotente
- [ ] README.md e CONTRIBUTING.md

Criteri di uscita: `aria repl` avvia KiloCode in modalità isolata, senza interferire con installazione globale.

### FASE 1 — MVP (3-4 sprint, ~6-8 settimane)

**Obiettivo**: ARIA operativa su Telegram, con Search-Agent + Workspace-Agent + memoria funzionante.

**Sprint 1.1 — Credential Manager & Memoria Tier 0/1**
- `src/aria/credentials/` completo con SOPS+age + keyring + circuit breaker
- `src/aria/memory/episodic.py` (SQLite WAL + FTS5)
- `src/aria/memory/clm.py` con compaction semplice (summary extractive)
- `aria-memory` MCP server esposto (remember, recall, recall_episodic, stats)

**Sprint 1.2 — Scheduler & Gateway Telegram**
- `src/aria/scheduler/` completo (SQLite store, cron/oneshot, budget gate, policy gate, HITL, DLQ)
- systemd `aria-scheduler.service` installato e testato
- `src/aria/gateway/telegram_adapter.py` operativo (polling mode)
- HITL via Telegram funzionante (`ask` → inline keyboard → risposta)

**Sprint 1.3 — ARIA-Conductor & Search-Agent**
- Definizioni agent markdown in `.aria/kilocode/agents/`
- Skills `deep-research`, `planning-with-files`, `pdf-extract`
- Router Python `src/aria/agents/search/router.py` + providers Tavily/Brave/Firecrawl/Exa
- Test E2E: "ARIA, ricerca su …" → report salvato in memoria

**Sprint 1.4 — Workspace-Agent**
- `google_workspace_mcp` installato e configurato
- `scripts/oauth_first_setup.py` con browser flow + keyring
- Skills `triage-email`, `calendar-orchestration`, `doc-draft`
- Test E2E: triage inbox giornaliero schedulato, digest via Telegram

Criteri di uscita: i 5 casi d'uso fondativi (§1.4) funzionano end-to-end su Telegram.

Quality gates quantitativi Fase 1 (obbligatori):
- `p95 recall memoria` (T0+T1) < 250ms su dataset locale baseline.
- `DLQ rate` < 2% su rolling 7 giorni.
- `HITL timeout rate` < 5% su richieste `policy=ask`.
- `Provider degradation rate` < 15% su query search pianificate.
- `Scheduler success rate` > 98% su task `allow`.

### FASE 2 — Maturazione (4-6 sprint, ~8-12 settimane)

- **Memoria Tier 3**: grafo associativo (NER + relazioni), query multi-hop
- **LLM routing deterministico**: intent classifier + mapping sub-agente/task → modello (config dichiarativa)
- **Canali aggiuntivi**: Slack, WebUI Tauri
- **MCP Gateway**: riduzione tool bloat via proxy scoped
- **Nuovi sub-agenti**: Finance-Agent (estratti conto), Health-Agent (CSV fitness tipo Hevy), Research-Academic (Exa + Zotero MCP)
- **Playwright per browser automation**: avanzate ricerche + form filling
- **Backup automatici + Disaster Recovery runbook**
- **Observability dashboard**: Grafana locale

### FASE 3 — Scale (orizzonte 6-12 mesi)

- **Multi-utente / multi-tenant**: ruoli, RBAC, quota per user
- **Dashboard WebUI completa**: Tauri+React o FastAPI+HTMX
- **Extension marketplace**: formato `.aria-skill.tar.age` installabile
- **Fine-tuning procedurale** (opzionale): LoRA per skill frequenti
- **Enterprise hardening**: audit trail completo, SBOM, SLSA provenance

---

## 16. Regole Inderogabili — The Ten Commandments

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

> I 10 comandamenti di ARIA. Deviazioni richiedono ADR esplicito approvato.

1. **Isolation First** — ARIA vive in spazio separato; nessuna contaminazione con KiloCode globale.
2. **Upstream Invariance** — KiloCode non si forka; lo si configura.
3. **Polyglot Pragmatism** — KiloCode TS invariato; layer ARIA Python; MCP come colla.
4. **Local-First, Privacy-First** — dati e credenziali in locale; cloud solo per LLM e API esterne dichiarate.
5. **Actor-Aware Memory** — ogni dato etichettato con l'attore di origine; le inferenze non sono fatti.
6. **Verbatim Preservation** — T0 raw è autoritativo e immutabile; sintesi sono derivate ricostruibili.
7. **HITL on Destructive Actions** — ogni azione distruttiva/costosa/irreversibile passa per gate umano.
8. **Tool Priority Ladder** — MCP > Skill > Python script; mai saltare il livello.
9. **Scoped Toolsets ≤ 20** — nessun sub-agente vede più di 20 tool simultaneamente.
10. **Self-Documenting Evolution** — ogni divergenza è registrata via ADR; drift silenzioso è vietato.

---

## 17. Auto-aggiornamento del Blueprint

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 17.1 Frontmatter per sezione

Ogni sezione (§1–§18) ha un blocco YAML `status/last_review/owner`. Status ammessi:

| Status         | Significato                                               |
|----------------|----------------------------------------------------------|
| `draft`        | In definizione, non ancora ratificato                    |
| `ratified`     | Ratificato dall'utente, vincolante                       |
| `implemented`  | Ratificato E implementato nel codice (coperto da test)   |
| `deprecated`   | Non più valido; mantenere per storicità, vedere ADR      |

Le sezioni `implemented` **devono** linkare i file/moduli che le implementano.

### 17.2 ADR Process

- Path: `docs/foundation/decisions/ADR-NNNN-<slug>.md`
- Numerazione monotona crescente a 4 cifre.
- Stati: `Proposed` → `Accepted` | `Rejected` | `Superseded by ADR-MMMM`.
- Template vedi §18.D.
- Ogni ADR che impatta una sezione del blueprint → PR che modifica sia il blueprint sia crea l'ADR.

### 17.3 Skill `blueprint-keeper`

Skill di sistema schedulata (`cron: '0 10 * * 0'` — domenica 10:00):

**Procedura**:
1. Legge `aria_foundation_blueprint_v2.md`
2. Per ogni sezione `status=implemented`, verifica che i file referenziati esistano
3. Scansiona `src/aria/**/*.py` cercando divergenze dai pattern descritti
4. Confronta agents/skills nel filesystem con quelli descritti in §8–§9
5. Se divergenza detectata → genera `ADR-<next>-<slug>.md` draft + PR di update blueprint
   - batch massimo: 1 PR/settimana, max 3 sezioni toccate per PR
   - labels obbligatorie: `docs-only` | `breaking` | `security`
   - se severity `breaking` o `security`: PR in stato draft + HITL esplicito
6. Notifica utente via Telegram: "Blueprint review ready for your approval"

### 17.4 Implementation log

Appendice `§18.G — Implementation Log` append-only con entry per milestone:

```markdown
## Implementation Log

### 2026-05-03 — Phase 0 Completed
- Struttura dirs ratified and in place (commit abc123)
- Bootstrap script idempotente (`scripts/bootstrap.sh`)
- Launcher `aria` testato su bash e zsh
- SOPS+age keys generate e backup offsite

### 2026-05-17 — Phase 1 Sprint 1.1 Completed
- CredentialManager operativo (coverage 87%)
- Memoria T0+T1 online con ARIA-Memory MCP
- ...
```

---

## 18. Appendici

```yaml
status: ratified
last_review: 2026-04-20
owner: fulvio
```

### 18.A File layout (riferimento rapido)

Vedi §4.1.

### 18.B Esempi config

#### 18.B.1 `kilo.json` minimale

```json
{
  "$schema": "https://app.kilo.ai/config.json",
  "default_agent": "aria-conductor",
  "agents_dir": "./agents",
  "skills_dir": "./skills",
  "modes_dir": "./modes",
  "mcp_config": "./mcp.json",
  "sessions_dir": "./sessions",
  "locale": "it-IT",
  "model": {
    "provider": "anthropic",
    "id": "claude-sonnet-4-6"
  },
  "hooks": {
    "PreToolUse": [],
    "PostToolUse": [],
    "UserPromptSubmit": [],
    "Stop": []
  }
}
```

#### 18.B.2 Esempio agente (extract)

Vedi §8.2, §8.3.

#### 18.B.3 Esempio skill (extract)

Vedi §9.1.

### 18.C Schema SQLite completo

Vedi §5 (memoria), §6.1 (scheduler), §7.2 (gateway sessions). File concatenato: `docs/foundation/schemas/sqlite_full.sql` (generato a Fase 0).

### 18.D Template ADR

```markdown
# ADR-NNNN: <Titolo decisione>

- **Status**: Proposed | Accepted | Rejected | Superseded by ADR-MMMM
- **Date**: YYYY-MM-DD
- **Author**: <handle>
- **Impacts blueprint sections**: §X.Y, §Z

## Context
<Il problema, il vincolo, la scelta richiesta>

## Decision
<Cosa si decide>

## Consequences
- Positive: ...
- Negative: ...
- Trade-offs: ...

## Alternatives Considered
1. <alt A> — scartata perché ...
2. <alt B> — scartata perché ...

## References
- Fonte: ...
- Benchmark: ...
```

### 18.E Glossario

| Termine                | Definizione                                                   |
|------------------------|---------------------------------------------------------------|
| ARIA-Conductor         | Agente orchestratore primario di ARIA                          |
| Actor-Aware Memory     | Memoria con tagging di provenienza (user/tool/inference/sys)  |
| ADR                    | Architecture Decision Record                                   |
| CLM                    | Context Lifecycle Manager (distillazione async T0→T1)         |
| Child session          | Sessione KiloCode isolata avviata da un parent                 |
| Circuit Breaker        | Pattern per disabilitare risorse in errore                     |
| DLQ                    | Dead Letter Queue                                              |
| HITL                   | Human-In-The-Loop                                              |
| Progressive Disclosure | Caricamento on-demand di skill/tool                           |
| Scoped Toolset         | Sottoinsieme di tool accessibile a un sub-agente               |
| SOPS                   | Mozilla Secrets Operations (file-level encryption)             |
| Tool Priority Ladder   | Ordine MCP > Skill > Python                                    |
| Verbatim Preservation  | Invariante: Tier 0 raw immutabile                              |

### 18.F Fonti e link

**Fonti ufficiali runtime/stack (audit 2026-04)**:
- MCP Specification (2025-11-25): https://modelcontextprotocol.io/specification/2025-11-25
- FastMCP docs: https://gofastmcp.com/getting-started/installation
- FastMCP PyPI: https://pypi.org/project/fastmcp/
- python-telegram-bot docs (v22.x): https://docs.python-telegram-bot.org/
- Google OAuth best practices: https://developers.google.com/identity/protocols/oauth2/resources/best-practices
- Google OAuth overview: https://developers.google.com/identity/protocols/oauth2
- SQLite WAL: https://www.sqlite.org/wal.html
- SQLite FTS5: https://www.sqlite.org/fts5.html
- Pydantic fields/defaults: https://docs.pydantic.dev/latest/concepts/fields/
- LanceDB docs: https://docs.lancedb.com
- OpenAI Whisper: https://github.com/openai/whisper
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- systemd.exec reference: https://manpages.debian.org/unstable/systemd/systemd.exec.5.en.html

**Fonti primarie analizzate** (in `docs/foundation/fonti/`):
- `AI Coding Agents Memory Report.md`
- `Analisi Approfondita di MemPalace e Simili.md`
- `Analisi Approfondita LLM Wiki.md`
- `Analisi GolemBot_ CLI e Assistenti Onnipresenti.md`
- `Kilocode_Opencode come assistenti AI.md`

**Repository di riferimento**:
- KiloCode: https://github.com/Kilo-Org/kilocode
- Kilo_kit (pattern agents/skills/rotation): https://github.com/fulvian/kilo_kit
- Google Workspace MCP: https://github.com/taylorwilsdon/google_workspace_mcp
- MemPalace (studiato come anti-esempio): https://github.com/MemPalace/mempalace
- GolemBot (pattern gateway): https://github.com/0xranx/golembot
- Opencode scheduler (pattern systemd/sd_notify): https://github.com/different-ai/opencode-scheduler
- SOPS: https://github.com/getsops/sops
- age: https://github.com/FiloSottile/age

**Documentazione API**:
- Tavily: https://docs.tavily.com/
- Firecrawl: https://docs.firecrawl.dev/
- Brave Search: https://brave.com/search/api/
- Exa: https://exa.ai/
- Anthropic MCP Tool Search: https://docs.anthropic.com/ (verificare aprile 2026)

**Benchmark di riferimento**:
- LOCOMO (Long-term Conversational Memory benchmark, ECAI 2025)
- Terminal-Bench 2.0
- SWE-bench

### 18.G Implementation Log (append-only)

> *Questa sezione sarà popolata a partire dalla Fase 0.*
> *Ogni milestone aggiunge una entry con data ISO, titolo, bullet list di deliverable chiusi e link al commit/PR.*

### 2026-04-20 — Phase 0 Completed

- **Struttura directory** completa secondo §4.1 blueprint
- **Launcher `bin/aria`** funzionante con isolamento KiloCode
- **`.aria/kilocode/`** configurato con kilo.json, mcp.json, agents, skills
- **pyproject.toml** + **uv.lock** presenti con dipendenze Phase 0
- **Skeleton `src/aria/`** creato con moduli stub per credentials, memory, scheduler, gateway
- **config.py** creato per loading configurazione ARIA
- **SOPS+age baseline** configurato in `.aria/credentials/`
- **API keys criptate** con age (8 chiavi Tavily, 7 Firecrawl, Brave, Exa, SerpAPI, GitHub)
- **SQLite 3.51.3** installato da source (corretto WAL bug)
- **Systemd unit templates** in `systemd/aria-*.service` (verificati con systemd-analyze)
- **Scripts operativi** (`bootstrap.sh`, `backup.sh`, `restore.sh`, `install_systemd.sh`, `smoke_db.sh`)
- **Schema SQLite** completo in `docs/foundation/schemas/sqlite_full.sql`
- **Quality gates** passati: ruff check, ruff format, mypy, pytest
- **Age keys** generate in `~/.config/sops/age/keys.txt`
- **ADR-0001** creato per Dependency Baseline
- **ADR-0002** creato per SQLite Reliability Policy

### 2026-04-21 — Sprint 1.3 Completed (ARIA-Conductor + Search-Agent)

- **Search module** (`src/aria/agents/search/`): schema, router, dedup, cache, health + 6 providers (Tavily, Brave, Firecrawl, Exa, SearXNG, SerpAPI)
- **MCP wrappers** (`src/aria/tools/`): FastMCP 3.x Tavily + Firecrawl + Exa + SearXNG servers
- **ConductorBridge** (`src/aria/gateway/conductor_bridge.py`): subprocess spawn con env isolation + close_fds + secret redaction
- **Prompt injection mitigation** (ADR-0006): `<<TOOL_OUTPUT>>` frame + sanitizer in `src/aria/utils/prompt_safety.py`
- **HITL tools** in `aria-memory` MCP: `hitl_ask`, `hitl_list_pending`, `hitl_cancel`
- **Provider exhaustion runbook** (`docs/operations/provider_exhaustion.md`)
- **19 bug fixes** complessivi su API mismatches, routing, URL validation, HTTP retry, MCP naming, env isolation
- **45/45 tests passing**, agent validation PASSED (8 agents), skill validation PASSED (7 skills)
- **Evidence pack**: `docs/implementation/phase-1/sprint-03-evidence.md`

### 2026-04-21 — Sprint 1.4 Implemented (Workspace-Agent + E2E MVP in verification)

- **OAuth PKCE setup** (`scripts/oauth_first_setup.py`): Google OAuth 2.0 PKCE flow, refresh_token stored in keyring via KeyringStore
- **OAuth helper** (`src/aria/agents/workspace/oauth_helper.py`): runtime token management with `ensure_refresh_token()`, `get_scopes()`, `revoke()`
- **Scope manager** (`src/aria/agents/workspace/scope_manager.py`): minimal scopes enforcement, escalation control with ADR reference
- **Workspace-Agent** (`.aria/kilocode/agents/workspace-agent.md`): activated with 17 scoped tools (under P9 limit of 20)
- **Skills**: `triage-email` (v1.0.0), `calendar-orchestration` (v1.0.0), `doc-draft` (v1.0.0) created and registered
- **MCP wrapper** (`scripts/wrappers/google-workspace-wrapper.sh`): keyring injection for google_workspace_mcp
- **Scheduler seed** (`scripts/seed_scheduler.py`): 3 tasks seeded (daily-email-triage, weekly-backup, blueprint-review stub)
- **Backup/DR**: `test_backup_restore.sh` created, `disaster_recovery.md` runbook implemented
- **SLO benchmarks** (`tests/benchmarks/phase1_slo.py`): p95 recall, DLQ rate, HITL timeout, provider degradation, scheduler success
- **ADR-0003** accepted: PKCE-first, scope minimalism, keyring storage, revocation
- **MVP demo** (`docs/implementation/phase-1/mvp_demo_2026-04-21.md`): checklist prepared; live evidence still required for Phase 1 GO/NO-GO

### 18.H ADR backlog immediato (post-audit)

- `ADR-0001` — Dependency Baseline 2026Q2 (`fastmcp 3.x`, `ptb 22.x`, `lancedb 0.30.x`, STT dual stack).
- `ADR-0002` — SQLite Reliability Policy (version floor, WAL checkpointing, backup cadence).
- `ADR-0003` — OAuth Security Posture (PKCE-first, secret minimization, scope escalation in-context).
- `ADR-0004` — Associative Memory Persistence Format (no pickle per storage canonico).

---

**Fine del Foundation Blueprint v1.1.0-audit-aligned.**

*Questo documento rimane la stella polare finché la governance §17 non ne approva la revisione. Per dubbi implementativi, consultare prima le Ten Commandments (§16), poi la sezione specifica, infine gli ADR.*
