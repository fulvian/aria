# ARIA — Autonomous Reasoning & Intelligent Assistant

> **Documentation**: See [docs/foundation/aria_foundation_blueprint.md](./docs/foundation/aria_foundation_blueprint.md) for the full technical specification.

## Overview

ARIA is a **personal AI agent** built on KiloCode CLI as the cognitive engine, expanded beyond coding into daily life and intellectual work. It serves as your autonomous reasoning assistant for deep web research, document analysis, Google Workspace operations, scheduled routine automation, and conversational interaction via Telegram.

### Core Capabilities

| Capability | Description |
|------------|-------------|
| **Deep Research** | Multi-provider web search (Exa, Tavily, Firecrawl, SearXNG, Brave) with automatic key rotation and intelligent routing |
| **Memory** | 5D episodic/semantic memory with actor-aware tagging, verbatim preservation, and async distillation |
| **Scheduling** | Cron-based task automation with budget gates, policy gates, and HITL (Human-In-The-Loop) for actions |
| **Workspace** | Google Workspace integration (Gmail, Calendar, Drive, Docs, Sheets) via OAuth PKCE |
| **Gateway** | Telegram bot for conversational interaction with multi-user session management |
| **Security** | SOPS+age encrypted credentials, keyring storage, circuit breaker patterns |

### Status

**Phase 1 — MVP**: Implementation complete and in verification (2026-04-21). See [sprint-00.md](./docs/plans/phase-0/sprint-00.md) for Phase 0 deliverables and [mvp_demo_2026-04-21.md](./docs/implementation/phase-1/mvp_demo_2026-04-21.md) for Phase 1 verification.

## Quick Start

### Prerequisites

- Python >= 3.11 with `uv` package manager
- Node.js (for KiloCode CLI)
- `sqlite >= 3.51.3` (WAL mode enabled)
- `sops` and `age` for secrets encryption
- Linux with systemd (user services)

### First-Time Setup

```bash
# Clone and enter the repository
cd /home/fulvio/coding/aria

# Bootstrap environment (installs dependencies, generates keys)
./scripts/bootstrap.sh

# Launch ARIA REPL (isolated from global KiloCode)
./bin/aria repl
```

### Daemon Services

```bash
# Install systemd user services
./scripts/install_systemd.sh

# Start services manually (if not using systemd)
aria schedule --daemon    # Scheduler daemon
aria gateway              # Telegram gateway daemon
aria memory               # Memory MCP server
```

## Architecture

### Design Principles (The Ten Commandments)

ARIA follows ten inderogable architectural principles defined in [Foundation Blueprint §16](./docs/foundation/aria_foundation_blueprint.md):

1. **Isolation First** — ARIA runs in a dedicated workspace, isolated from the global KiloCode installation
2. **Upstream Invariance** — Never fork/modify KiloCode source; consume as configured dependency
3. **Polyglot Pragmatism** — KiloCode stays TypeScript; ARIA layer is Python; MCP is the glue
4. **Local-First, Privacy-First** — All data, credentials, and memory stay on-disk; cloud only for LLM APIs and declared external APIs
5. **Actor-Aware Memory** — Every stored datum is tagged with origin actor (user_input, tool_output, agent_inference, system_event)
6. **Verbatim Preservation** — Tier 0 (raw) is authoritative and immutable; summaries are derived and rebuildable
7. **HITL on Destructive Actions** — Every destructive, costly, or irreversible action passes through Human-In-The-Loop
8. **Tool Priority Ladder** — MCP > Skill > Python script; never skip a layer
9. **Scoped Toolsets** — No sub-agent sees more than 20 tools simultaneously
10. **Self-Documenting Evolution** — Every divergence from blueprint is registered via ADR; silent drift is forbidden

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                   CANALI DI INTERAZIONE UMANA                        │
│  ┌─────────┐  ┌──────────┐                                    │
│  │  CLI    │  │ Telegram │                                    │
│  └────┬────┘  └────┬─────┘                                    │
│       │            │                                          │
└───────┼────────────┼──────────────────────────────────────────┘
        │            │
        │            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ARIA GATEWAY (Python)                              │
│   Session Manager │ Auth (whitelist) │ Multimodal (OCR/Whisper)        │
└─────────────────────────────┬───────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│               ARIA CORE (KiloCode + Conductor)                       │
│   ┌────────────────────────────────────────────────────────────┐  │
│   │           ARIA-Conductor (primary orchestrator)               │  │
│   └────┬────────┬────────────┬──────────┬───────────────────────┘  │
│        │        │            │          │                               │
│        ▼        ▼            ▼          ▼                               │
│   ┌─────┐ ┌───────┐ ┌──────────┐ ┌──────────────┐                    │
│   │Srch │ │Wkspce │ │Compaction│ │ Summary     │                    │
│   │Agent│ │ Agent │ │  Agent   │ │ Agent       │                    │
│   └─────┘ └───────┘ └──────────┘ └──────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
        │          │           │
        ▼          ▼           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TOOL LAYER (MCP + Python)                       │
│   Tavily │ Firecrawl │ Brave │ Exa │ Google Workspace │ ARIA-Memory  │
└─────────────────────────────────────────────────────────────────────┘
        │                     │
        ▼                     ▼
┌────��────────────────────────────────────────────────────────────────┐
│           BACKEND SERVICES (Python daemons)                         │
│   Memory (5D) │ Scheduler │ Credential Manager (SOPS+age)       │
└─────────────────────────────────────────────────────────────────────┘
```

### Sub-Agents

| Agent | Purpose | Tools |
|-------|---------|-------|
| **ARIA-Conductor** | Primary orchestrator; intent classification, dispatch to sub-agents | Memory only |
| **Search-Agent** | Web research with multi-provider routing, automatic key rotation | Exa, Tavily, Firecrawl, SearXNG, Brave |
| **Workspace-Agent** | Gmail, Calendar, Drive, Docs, Sheets | Google Workspace MCP |
| **Compaction-Agent** | Context Lifecycle Manager; T0→T1 distillation | Memory (async) |
| **Summary-Agent** | Session summarization | Memory (async) |
| **Memory-Curator** | Review queue management | Memory (async) |

See [Foundation Blueprint §8](./docs/foundation/aria_foundation_blueprint.md) for detailed agent specifications.

## Project Structure

```
aria/
├── bin/aria                 # Launcher script (isolated KiloCode)
├── .aria/                   # Isolated state (gitignored)
│   ├── kilocode/            # KiloCode config, agents, skills, sessions
│   │   ├── kilo.json       # KiloCode + MCP configuration
│   │   ├── agents/        # Agent definitions
│   │   │   ├── aria-conductor.md
│   │   │   ├── search-agent.md
│   │   │   └── workspace-agent.md
│   │   └── skills/        # Skill definitions
│   │       ├── deep-research/
│   │       ├── planning-with-files/
│   │       ├── triage-email/
│   │       └── ...
│   ├── runtime/            # Runtime data
│   │   ├── memory/        # SQLite episodic, LanceDB semantic
│   │   ├── scheduler/     # SQLite tasks/runs
│   │   ├── gateway/      # SQLite sessions
│   │   └── logs/         # Structured JSON logs
│   └── credentials/       # SOPS-encrypted secrets
├── src/aria/               # Python package
│   ├── __init__.py
│   ├── config.py           # Configuration loading
│   ├── credentials/        # Credential management (SOPS+age, keyring)
│   ├── memory/            # 5D memory subsystem
│   │   ├── schema.py      # Pydantic models
│   │   ├── episodic.py   # SQLite + FTS5
│   │   ├── semantic.py   # LanceDB wrapper
│   │   ├── clm.py       # Context Lifecycle Manager
│   │   └── mcp_server.py # FastMCP ARIA-Memory server
│   ├── scheduler/         # Task scheduling daemon
│   │   ├── daemon.py     # systemd entrypoint
│   │   ├── store.py      # SQLite tasks/runs
│   │   ├── triggers.py   # cron/event/oneshot/manual
│   │   ├── budget_gate.py
│   │   ├── policy_gate.py
│   │   └── hitl.py
│   ├── gateway/           # Telegram gateway
│   │   ├── daemon.py
│   │   ├── telegram_adapter.py
│   │   └── session_manager.py
│   ├── agents/            # Sub-agent wrappers
│   │   ├── search/
│   │   │   ├── router.py
│   │   │   ├── providers/
│   │   │   └── dedup.py
│   │   └── workspace/
│   │       └── oauth_helper.py
│   └── utils/            # Logging, metrics
├── systemd/               # Systemd unit templates
│   ├── aria-scheduler.service
│   ├── aria-gateway.service
│   └── aria-memory.service
├── scripts/               # Operational scripts
│   ├── bootstrap.sh      # First-time setup
│   ├── backup.sh         # Backup with age encryption
│   ├── restore.sh
│   ├── install_systemd.sh
│   └── oauth_first_setup.py
└── docs/                  # Documentation
    ├── foundation/       # Blueprint, decisions, schemas
    │   ├── aria_foundation_blueprint.md
    │   └── decisions/
    │       ├── ADR-0001-*.md
    │       ├── ADR-0002-*.md
    │       └── ...
    ├── implementation/    # Phase trackers
    │   ├── phase-0/
    │   └── phase-1/
    └── operations/       # Runbooks
```

## Command Reference

| Command | Description |
|---------|-------------|
| `aria repl` | Start interactive REPL |
| `aria run "<prompt>"` | Execute single prompt and exit |
| `aria mode <name>` | Set active mode |
| `aria schedule` | Run scheduler daemon |
| `aria gateway` | Run Telegram gateway |
| `aria memory` | Run memory MCP server |
| `aria creds` | Manage credentials (reload, rotate, status) |
| `aria backup` | Run backup script |

See `./bin/aria --help` for full command reference.

## Documentation

### Foundational

| Document | Description |
|----------|-------------|
| [Foundation Blueprint](./docs/foundation/aria_foundation_blueprint.md) | **The source of truth** — Technical specification, architecture, Ten Commandments |
| [Phase 0 Sprint Plan](./docs/plans/phase-0/sprint-00.md) | Phase 0 implementation roadmap |
| [Implementation Notes Phase 0](./docs/implementation/phase-0/README.md) | Phase 0 completion tracker |

### Phase 1 (MVP) Evidence

| Document | Description |
|----------|-------------|
| [Sprint 1.1 Evidence](./docs/implementation/phase-1/sprint-01.1-evidence.md) | Credential Manager + Memory |
| [Sprint 1.2 Evidence](./docs/implementation/phase-1/sprint-01.2-evidence.md) | Scheduler + Gateway |
| [Sprint 1.3 Evidence](./docs/implementation/phase-1/sprint-01.3-evidence.md) | Conductor + Search-Agent |
| [Sprint 1.4 Evidence](./docs/implementation/phase-1/sprint-01.4-evidence.md) | Workspace-Agent + E2E MVP |

### Architecture Decisions (ADRs)

| ADR | Description |
|-----|-------------|
| [ADR-0001](./docs/foundation/decisions/ADR-0001-dependency-baseline-2026q2.md) | Dependency Baseline 2026 Q2 |
| [ADR-0002](./docs/foundation/decisions/ADR-0002-sqlite-reliability-policy.md) | SQLite Reliability Policy |
| [ADR-0003](./docs/foundation/decisions/ADR-0003-oauth-security-posture.md) | OAuth Security Posture (PKCE-first) |
| [ADR-0004](./docs/foundation/decisions/ADR-0004-associative-memory-persistence-format.md) | Associative Memory Persistence Format |
| [ADR-0005](./docs/foundation/decisions/ADR-0005-scheduler-concurrency.md) | Scheduler Concurrency |
| [ADR-0006](./docs/foundation/decisions/ADR-0006-prompt-injection-mitigation.md) | Prompt Injection Mitigation |
| [ADR-0007](./docs/foundation/decisions/ADR-0007-stt-stack-dual.md) | STT Stack (Dual: faster-whisper + openai-whisper) |

### Operations

| Document | Description |
|----------|-------------|
| [Runbook](./docs/operations/runbook.md) | Service operations and troubleshooting (scheduler/gateway/memory) |
| [Provider Exhaustion](./docs/operations/provider_exhaustion.md) | Provider degradation runbook |
| [Disaster Recovery](./docs/operations/disaster_recovery.md) | Backup/restore procedures |
| [Telemetry](./docs/operations/telemetry.md) | Metrics and observability |

### Telegram Gateway Notes (2026-04)

- The gateway now uses a full event loop: `gateway.user_message -> ConductorBridge -> gateway.reply -> TelegramAdapter`.
- `kilo run` invocations use positional messages with `--format json --auto` (no `--input`, no one-shot `--session`).
- `scripts/install_systemd.sh start` enables+starts services (`enable --now`) to avoid inactive daemons after reboot.
- For live troubleshooting, follow `docs/operations/runbook.md` section 7.2 and inspect:
  `journalctl --user -u aria-gateway.service -f`.

## Quality Gates

All code must pass these gates before commit:

```bash
# Linting
ruff check .
ruff format --check .

# Type checking
mypy src

# Tests
pytest -q
```

## Dependencies

### Core Stack (Python 3.11+)

| Package | Version | Purpose |
|---------|---------|---------|
| pydantic | >=2.6,<3.0 | Data validation |
| fastmcp | >=3.2,<4.0 | MCP server |
| python-telegram-bot | >=22.0,<23.0 | Telegram bot |
| aiosqlite | >=0.19 | Async SQLite |
| cryptography | >=42.0 | Encryption |
| keyring | >=25.0 | OS keyring |
| secretstorage | >=3.3 | Secret Service |
| httpx | >=0.27 | HTTP client |
| tenacity | >=8.2 | Retry patterns |
| rapidfuzz | >=3.0 | Search deduplication |
| croniter | >=2.0 | Cron parsing |
| python-dateutil | >=2.8 | Date utilities |
| rich | >=13.0 | CLI output |
| typer | >=0.12 | CLI framework |
| sd-notify | >=0.1 | Systemd notification |
| prometheus-client | >=0.20 | Metrics |
| pymupdf | >=1.27 | PDF extraction |

See [pyproject.toml](./pyproject.toml) for full dependency list.

### MCP Servers

| Server | Purpose |
|--------|---------|
| @modelcontextprotocol/server-filesystem | Filesystem access |
| @modelcontextprotocol/server-git | Git operations |
| @modelcontextprotocol/server-github | GitHub API |
| @modelcontextprotocol/server-sequential-thinking | Reasoning |
| mcp-server-fetch | Web fetching |
| google_workspace_mcp | Google Workspace |
| @brave/brave-search-mcp-server | Brave Search |

### Provider APIs

| Provider | Purpose | Free Tier |
|----------|---------|---------|
| Tavily | LLM-ready search synthesis | 1,000 req/month |
| Firecrawl | Deep scraping, AI extract | 500 credits lifetime |
| Brave Search | Privacy, volume | $5/month |
| Exa | Semantic academic search | 1,000 req/month |
| SearXNG | Meta, privacy (self-hosted) | Unlimited |

## Security

### Credential Management

- **API Keys**: Encrypted with SOPS+age in `.aria/credentials/secrets/api-keys.enc.yaml`
- **OAuth Tokens**: Stored in OS keyring via `keyring` library
- **Runtime State**: Encrypted in `.aria/runtime/credentials/providers_state.enc.yaml`
- **Age Keys**: Separate key in `~/.config/sops/age/keys.txt`

### Human-In-The-Loop (HITL)

Actions requiring HITL confirmation (per Ten Commandment #7):
- Delete operations (memory forget, credential revoke)
- Write operations to external systems (send email, create calendar event)
- Expensive operations (token budget exceeded)
- New authentication (OAuth consent)

## License

Private — All rights reserved

---

> **Stella Polare**: This document is derived from the [Foundation Blueprint](./docs/foundation/aria_foundation_blueprint.md). For any discrepancy, the blueprint takes precedence per Ten Commandment #10 — Self-Documenting Evolution.
