---
title: Quality Gates
sources:
  - AGENTS.md
  - pyproject.toml
  - Makefile
last_updated: 2026-04-23
tier: 1
---

# Quality Gates — Build, Test, Quality

## Comandi Rapidi (Makefile)

| Target | Comando | Descrizione |
|--------|---------|-------------|
| `make install` | `uv sync` | Installa dipendenze |
| `make dev-install` | `uv sync --dev` | Installa anche dev deps |
| `make lint` | `ruff check src/` | Linting |
| `make format` | `ruff format src/` | Formattazione |
| `make typecheck` | `mypy src/` | Type checking |
| `make test` | `pytest -q` | Test suite completa |
| `make test-unit` | `pytest -q tests/unit` | Solo unit test |
| `make test-integration` | `pytest -q tests/integration` | Solo integration |
| `make quality` | lint + format + typecheck + test | **Full quality gate** |

*source: `Makefile`*

## Pre-commit Quality Gate (obbligatorio)

```bash
ruff check src/           # Lint
ruff format --check src/  # Format check
mypy src                  # Type check
pytest -q                 # Tests
```

Tutti devono passare prima del commit.

*source: `AGENTS.md` §CI Expectations*

## Configurazione Strumenti

### ruff
- Line length: 100 caratteri
- Target: Python 3.11
- Regole abilitate: E, W, F, I, N, UP, ANN, ASYNC, B, C4, DTZ, T20, ISC, PIE, RET, SIM, TCH, ARG, PLE, PLR, PLW
- Ignore selettivo: PLR0913, PLR2004, RET505, ISC001, ARG002/003/005, PIE790, ARG001

### mypy
- Python 3.11, non strict
- `warn_return_any`, `warn_unused_ignores`, `check_untyped_defs`
- `no_implicit_optional`, `warn_redundant_casts`
- Ignore missing imports per: pydantic, pytesseract, PIL, faster_whisper, sd_notify, yaml

### pytest
- minversion: 8.0
- testpaths: `tests/`
- asyncio_mode: `auto`
- Markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.slow`
- Coverage: `--cov=src/aria --cov-report=term-missing`

*source: `pyproject.toml`*

## Struttura Test

```
tests/
├── unit/            # Unit tests (routing, business logic)
├── integration/     # Integration tests (tool/provider edges)
├── e2e/             # End-to-end tests
├── benchmarks/      # Performance/SLO benchmarks
└── fixtures/        # Shared test fixtures
```

### Esecuzione Selettiva

```bash
pytest -q tests/unit/test_example.py              # Singolo file
pytest -q tests/unit/test_example.py::test_name   # Singolo test
pytest -q -k "router and not integration"          # Pattern match
pytest --cov=src/aria --cov-report=term-missing    # Con coverage
```

## Auto-fix Workflow

```bash
ruff check src/ --fix    # Auto-fix lint issues
ruff format src/         # Auto-format
mypy src                 # Re-verify types
```

## Dipendenze Python

### Core
pydantic >= 2.6, fastmcp >= 3.2, python-telegram-bot >= 22.0, aiosqlite, httpx, tenacity, rapidfuzz, croniter, rich, typer, sd-notify, prometheus-client, pyyaml, pymupdf, google-auth

### Dev
ruff >= 0.9, mypy >= 1.15, pytest >= 8.3, pytest-asyncio >= 0.25, pytest-cov >= 6.0, pytest-mock >= 3.14, respx >= 0.22

### ML (optional)
lancedb >= 0.30, faster-whisper >= 1.2, pillow >= 10.0, pytesseract >= 0.3

*source: `pyproject.toml`*

## Vedi anche

- [[project-layout]] — Struttura directory
- [[governance]] — Security e observability
