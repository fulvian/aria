# ARIA — Autonomous Reasoning & Intelligent Assistant

> **Documentation**: See [docs/foundation/aria_foundation_blueprint.md](./docs/foundation/aria_foundation_blueprint.md) for the full technical specification.

## Overview

ARIA is a personal AI agent built on KiloCode CLI as the cognitive engine, expanded beyond coding into daily life and intellectual work: deep web research, document analysis, Google Workspace operations, scheduled routine automation, and conversational interaction via Telegram.

## Quick Start

```bash
# Clone and enter the repository
cd /home/fulvio/coding/aria

# First-time setup (installs dependencies, generates SOPS+age keys)
./scripts/bootstrap.sh

# Launch ARIA REPL (isolated from global KiloCode)
./bin/aria repl

# Check status
./bin/aria --help
```

## Architecture Highlights

- **Isolation First**: ARIA runs in a dedicated workspace, isolated from the global KiloCode installation
- **Python 3.11+ Layer**: Memory, Scheduler, Gateway, and Credential Manager are Python-based
- **MCP as Glue**: Model Context Protocol connects KiloCode (TypeScript) with ARIA's Python services
- **Local-First**: All data, credentials, and memory stay on-disk; cloud only for LLM API calls and declared external APIs

## Project Structure

```
aria/
├── bin/aria                 # Launcher script (isolated KiloCode)
├── .aria/                   # Isolated state (gitignored)
│   ├── kilocode/            # KiloCode config, agents, skills, sessions
│   ├── runtime/             # Runtime data (memory, scheduler, gateway)
│   └── credentials/         # SOPS-encrypted secrets
├── src/aria/                # Python package
├── systemd/                 # Systemd unit templates (user services)
├── scripts/                 # Operational scripts
└── docs/                    # Documentation and decisions
```

## Documentation

- [Foundation Blueprint](./docs/foundation/aria_foundation_blueprint.md) — Technical specification
- [Phase 0 Sprint Plan](./docs/plans/phase-0/sprint-00.md) — Implementation roadmap
- [Implementation Notes](./docs/implementation/phase-0/README.md) — Phase tracker

## Requirements

- Python >= 3.11 with `uv` package manager
- Node.js (for KiloCode CLI)
- `sqlite >= 3.51.3` (WAL mode for reliability)
- `sops` and `age` for secrets encryption
- Linux with systemd (user services)

## Status

**Phase 0 — Foundation**: Completed and audit-aligned (2026-04-20). See [sprint-00.md](./docs/plans/phase-0/sprint-00.md) for deliverables.

## License

Private — All rights reserved
