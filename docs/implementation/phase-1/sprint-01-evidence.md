---
document: ARIA Phase 1 - Sprint 1.1 Evidence Pack
version: 1.1.1
status: completed
date_created: 2026-04-20
last_review: 2026-04-21
owner: fulvio
phase: 1
sprint: "1.1"
---

# Sprint 1.1 - Evidence and Remediation Log

## Scope of remediation

This evidence pack records the final alignment work completed for the following residual gaps:

1. Credentials CLI migrated to Typer.
2. Memory HITL stub persisted in a dedicated `hitl_pending` queue.
3. Coverage targets demonstrated:
   - `aria.credentials` >= 85%
   - `aria.memory` >= 80%
4. Benchmark script aligned with real `EpisodicStore.connect()` + migration flow.
5. Python interpreter runtime aligned to blueprint SQLite floor (`>= 3.51.3`).

## Implemented changes

### 1) CLI credentials -> Typer

- Reworked `src/aria/credentials/__main__.py` to Typer commands:
  - `list`
  - `rotate <provider>`
  - `status [--provider]`
  - `audit [--tail]`
  - `reload`
- Kept `rich` tabular output.

### 2) Memory HITL queue persistence

- Added migration and table:
  - `src/aria/memory/migrations/0003__hitl_pending.sql`
  - `src/aria/memory/migrations.py`
  - table name finalized as `memory_hitl_pending` to avoid collision with scheduler `hitl_pending`
- Added store APIs:
  - `EpisodicStore.enqueue_hitl(...)`
  - `EpisodicStore.list_hitl_pending(...)`
- Updated MCP tools to persist HITL requests:
  - `src/aria/memory/mcp_server.py`
    - `forget()` -> queue row in `hitl_pending`
    - `curate(action="forget")` -> queue row in `hitl_pending`

### 3) Benchmark flow realignment

- Replaced workaround benchmark implementation with real store startup:
  - `tests/benchmarks/memory_recall_p95.py`
  - uses `EpisodicStore.connect()` and migration runner directly
  - keeps CLI options required by sprint gate
- Added cleanup fix for SQLite version gate path:
  - `src/aria/memory/episodic.py`
  - close connection before raising on unsupported SQLite version

### 4) Documentation/schema alignment

- Updated canonical schema doc with memory HITL table:
  - `docs/foundation/schemas/sqlite_full.sql`

### 5) Interpreter/runtime alignment (blueprint §6.1.1)

- Root cause: project `.venv` (uv-managed CPython 3.12.13 build) linked `sqlite3` runtime `3.50.4` while host SQLite CLI was `3.51.3`.
- Action performed:
  - old environment archived as `.venv.bak-20260420-1722`
  - recreated `.venv` using `/usr/bin/python3.12` (runtime sqlite `3.51.3`)
  - re-synced dependencies with dev extras (`uv sync --extra dev`)
- Updated operational checks to validate Python sqlite runtime explicitly:
  - `scripts/bootstrap.sh` now checks both `sqlite3 --version` and `python sqlite3.sqlite_version`
  - `scripts/bootstrap.sh` supports `ARIA_PYTHON_BIN` for deterministic venv creation
  - `scripts/smoke_db.sh` now validates Python sqlite runtime and hard-fails on SQL parse errors

## Verification commands and outputs

### Unit + integration tests

Command:

```bash
uv run pytest -q
```

Result:

- `97 passed in 2.21s`

### Coverage gates

Command (global gate used in sprint plan):

```bash
uv run pytest tests/unit tests/integration -q --cov=aria.credentials --cov=aria.memory --cov=aria.utils --cov-report=term
```

Result (key totals):

- `aria.credentials` package total: **86%**
- `aria.memory` package total: **83%**
- Combined report total: `84%`

Target compliance:

- Credentials >= 85%: **PASS**
- Memory >= 80%: **PASS**

### Benchmark command

Command:

```bash
uv run python -m tests.benchmarks.memory_recall_p95 --entries 1000 --queries 200 --fail-if-p95-above-ms 250
```

Current environment output:

- `BENCHMARK PASSED: p95 (1.12ms) < 250.0ms`

Measured values:

- `populate=62.4ms` for 1000 entries
- `p95=1.12ms`, `p99=1.53ms`, `max=1.64ms`

## Added test suites

Credentials:

- `tests/unit/credentials/test_credentials_cli.py`
- `tests/unit/credentials/test_audit_logger.py`
- `tests/unit/credentials/test_keyring_store.py`
- `tests/unit/credentials/test_manager.py`
- `tests/unit/credentials/test_rotator.py`
- `tests/unit/credentials/test_sops_adapter.py`

Memory:

- `tests/unit/memory/test_actor_tagging.py`
- `tests/unit/memory/test_episodic_store.py`
- `tests/unit/memory/test_semantic_store.py`
- `tests/unit/memory/test_clm.py`
- `tests/unit/memory/test_mcp_server.py`
- `tests/unit/memory/test_migrations.py`

## Notes

- The benchmark is now architecture-correct and no longer bypasses migrations.

## Blueprint/Plan conformance delta (explicit)

| Blueprint / Plan requirement | Implemented change | Evidence |
|---|---|---|
| Blueprint §6.1.1, Sprint §1.4 / §3 W1.1.I: SQLite runtime >= 3.51.3 | `.venv` rebuilt on `/usr/bin/python3.12`; runtime check added to bootstrap/smoke | `python sqlite=3.51.3`, benchmark pass |
| Sprint W1.1.L: `forget` / `curate(forget)` HITL-gated stub | persisted queue records via `memory_hitl_pending` | MCP unit tests + migration 0003 |
| Sprint W1.1.G: credentials CLI commands | implemented with Typer + rich output | CLI unit tests |
| Sprint §7 coverage gates | credentials 86%, memory 83% | pytest --cov outputs |
| Sprint §7 benchmark gate | p95 < 250ms | `tests/benchmarks/memory_recall_p95.py` output |

## Command log (runtime alignment)

```bash
/usr/bin/python3.12 -c "import sys,sqlite3; print(sys.version.split()[0], sqlite3.sqlite_version)"
mv .venv .venv.bak-20260420-1722
uv venv --python /usr/bin/python3.12 .venv
uv sync --extra dev
uv run python -c "import sqlite3; print(sqlite3.sqlite_version)"
uv run pytest -q
uv run mypy src/aria/credentials src/aria/memory src/aria/config.py
uv run python -m tests.benchmarks.memory_recall_p95 --entries 1000 --queries 200 --fail-if-p95-above-ms 250
./scripts/bootstrap.sh --check
./scripts/smoke_db.sh
```
