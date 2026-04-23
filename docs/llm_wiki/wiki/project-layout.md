---
title: Project Layout
sources:
  - docs/foundation/aria_foundation_blueprint.md §4
  - AGENTS.md
last_updated: 2026-04-23
tier: 1
---

# Project Layout — Struttura Directory e Isolamento

## Root Directory

```
/home/fulvio/coding/aria/
├── README.md
├── AGENTS.md                    # Regole per coding agents (tu stai leggendo da qui)
├── pyproject.toml               # Dipendenze Python (uv/poetry)
├── package.json                 # Pinning KiloCode CLI
├── Makefile                     # Task comuni
├── .env.example                 # Template (NON contiene segreti)
├── .sops.yaml                   # SOPS config (IN GIT)
│
├── bin/
│   └── aria                     # Launcher script (bash, chmod +x)
│
├── .aria/                       # STATO ISOLATO (gitignored eccetto config)
│   ├── kilocode/                # ← KILOCODE_CONFIG_DIR
│   │   ├── kilo.json            # Config KiloCode (con mcp: inline)
│   │   ├── agents/              # Definizioni agenti (.md)
│   │   ├── skills/              # Skills (.md + scripts + resources)
│   │   ├── modes/               # Custom modes
│   │   └── sessions/            # Sessioni KiloCode persistite
│   │
│   ├── runtime/                 # Stato runtime (gitignored)
│   │   ├── memory/
│   │   │   ├── episodic.db      # SQLite raw + FTS5
│   │   │   └── semantic/        # LanceDB dir (lazy)
│   │   ├── scheduler/
│   │   │   └── scheduler.db     # SQLite tasks/runs/dlq
│   │   ├── gateway/
│   │   │   └── sessions.db      # SQLite mapping canali
│   │   ├── credentials/
│   │   │   └── providers_state.enc.yaml  # Runtime state cifrato (NO GIT)
│   │   └── logs/                # Structured JSON logs
│   │
│   └── credentials/             # (gitignored eccetto .sops.yaml)
│       ├── .sops.yaml
│       └── secrets/
│           └── api-keys.enc.yaml # IN GIT (cifrato con SOPS+age)
│
├── src/aria/                    # Codice Python ARIA
│   ├── config.py
│   ├── credentials/
│   ├── memory/
│   ├── scheduler/
│   ├── gateway/
│   ├── agents/
│   ├── tools/
│   └── utils/
│
├── tests/                       # pytest
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── benchmarks/
│   └── fixtures/
│
├── systemd/                     # Unit templates (IN GIT)
│   ├── aria-scheduler.service
│   ├── aria-gateway.service
│   └── aria-memory.service
│
├── scripts/                     # Operational scripts (IN GIT)
│   ├── bootstrap.sh
│   ├── install_systemd.sh
│   ├── backup.sh
│   ├── restore.sh
│   ├── oauth_first_setup.py
│   ├── seed_scheduler.py
│   └── wrappers/               # MCP wrapper scripts
│
└── docs/                        # Documentazione
    ├── foundation/              # Blueprint, ADR, fonti
    ├── implementation/          # Phase trackers
    ├── operations/              # Runbooks
    ├── plans/                   # Sprint plans
    ├── handoff/                 # Handoff notes
    └── llm_wiki/               # Questo wiki (Tier 1)
```

*source: `docs/foundation/aria_foundation_blueprint.md` §4.1*

## Variabili d'Ambiente

### KiloCode Isolation
```bash
export KILOCODE_CONFIG_DIR=/home/fulvio/coding/aria/.aria/kilocode
export KILOCODE_STATE_DIR=/home/fulvio/coding/aria/.aria/kilocode/sessions
```

### ARIA Paths
```bash
export ARIA_HOME=/home/fulvio/coding/aria
export ARIA_RUNTIME=/home/fulvio/coding/aria/.aria/runtime
export ARIA_CREDENTIALS=/home/fulvio/coding/aria/.aria/credentials
```

### ARIA Operational
```bash
export ARIA_LOG_LEVEL=INFO                 # DEBUG|INFO|WARN|ERROR
export ARIA_TIMEZONE=Europe/Rome
export ARIA_LOCALE=it_IT.UTF-8
export ARIA_QUIET_HOURS=22:00-07:00
```

### SOPS
```bash
export SOPS_AGE_KEY_FILE=$HOME/.config/sops/age/keys.txt
```

### Gateway Telegram
```bash
export ARIA_TELEGRAM_WHITELIST=123456789,987654321
```

*source: `docs/foundation/aria_foundation_blueprint.md` §4.2*

## Launcher (`bin/aria`)

Il launcher garantisce isolamento dal KiloCode globale:

| Comando | Azione |
|---------|--------|
| `aria repl` | Avvia KiloCode interattivo |
| `aria run "<prompt>"` | Esegue singolo prompt |
| `aria mode <name>` | Imposta mode attivo |
| `aria schedule` | Avvia scheduler daemon |
| `aria gateway` | Avvia Telegram gateway |
| `aria memory` | Avvia memory MCP server |
| `aria creds` | Gestione credenziali |
| `aria backup` | Esegue backup |

*source: `docs/foundation/aria_foundation_blueprint.md` §4.3*

## Isolamento KiloCode (Runtime effettivo)

Il launcher imposta un `HOME` isolato per evitare contaminazione:

```
HOME=~/coding/aria/.aria/kilo-home
XDG_CONFIG_HOME=~/coding/aria/.aria/kilo-home/.config
XDG_DATA_HOME=~/coding/aria/.aria/kilo-home/.local/share
XDG_STATE_HOME=~/coding/aria/.aria/kilo-home/.local/state
KILO_CONFIG_DIR=~/coding/aria/.aria/kilocode
KILO_DISABLE_EXTERNAL_SKILLS=true
```

*source: `docs/operations/runbook.md` §1.0*

## Vedi anche

- [[architecture]] — Layer diagram
- [[credentials]] — Gestione credenziali e SOPS
- [[quality-gates]] — Comandi build/test
