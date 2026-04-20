# AGENTS.md

## Purpose
- This file defines how coding agents should work in this repository.
- It captures build/lint/test commands, coding standards, and safety constraints.
- Follow this file unless an explicit user instruction overrides it.

## Repository Reality Check (as of 2026-04-20)
- The current repository mainly contains architecture and planning docs under `docs/`.
- The implementation blueprint lives in `docs/foundation/aria_foundation_blueprint.md`.
- Python source, `pyproject.toml`, `Makefile`, and `tests/` are planned by the blueprint but may not exist yet.
- When commands below require missing files, scaffold according to the blueprint first.

## Source of Truth
- Primary technical reference: `docs/foundation/aria_foundation_blueprint.md`.
- Respect the "Ten Commandments" (Section 16), especially:
  - Isolation first.
  - Upstream invariance (do not fork/modify KiloCode source directly).
  - Local-first privacy.
  - HITL for destructive/irreversible actions.
  - Tool priority ladder: MCP > skill > local script.

## Cursor / Copilot Rules
- `.cursorrules`: not found.
- `.cursor/rules/`: not found.
- `.github/copilot-instructions.md`: not found.
- If any of these files are added later, merge their directives into this document and treat them as high-priority repo policy.

## Environment and Layout Expectations
- Project root: `/home/fulvio/coding/aria`.
- Python target: 3.11+.
- Planned Python package root: `src/aria/`.
- Planned tests root: `tests/` (unit/integration/fixtures split).
- Runtime state should remain under `.aria/` and stay gitignored unless explicitly required.

## Build / Setup Commands
- Preferred dependency manager: `uv` (or `poetry` fallback) per blueprint intent.
- If `Makefile` exists, prefer Make targets for consistency.

### Bootstrap (when scaffolding exists)
- `uv sync --dev`
- Fallback: `python -m venv .venv && .venv/bin/pip install -e ".[dev]"`

### Editable install
- `uv pip install -e .`
- Fallback: `pip install -e .`

### Run main modules (planned entrypoints)
- `python -m aria.scheduler.daemon`
- `python -m aria.gateway.daemon`
- `python -m aria.memory.mcp_server`

## Lint / Format / Typecheck Commands
- Use `ruff` for linting and import/order checks.
- Use `ruff format` (or `black` only if repo config explicitly uses black).
- Use `mypy` for static typing.

### Standard quality gate
- `ruff check .`
- `ruff format --check .`
- `mypy src`

### Auto-fix workflow
- `ruff check . --fix`
- `ruff format .`
- Re-run `mypy src`

## Test Commands (pytest)
- Full suite: `pytest -q`
- Verbose with stop-on-first-failure: `pytest -x -vv`
- Unit only: `pytest -q tests/unit`
- Integration only: `pytest -q tests/integration`

### Single test execution (important)
- Single file: `pytest -q tests/unit/test_example.py`
- Single test function: `pytest -q tests/unit/test_example.py::test_happy_path`
- Single test class method: `pytest -q tests/unit/test_example.py::TestRouter::test_selects_tavily`
- Pattern match: `pytest -q -k "router and not integration"`

### Coverage (if configured)
- `pytest --cov=src/aria --cov-report=term-missing`

## CI Expectations for Agents
- Before proposing completion, run at minimum:
  - `ruff check .`
  - `mypy src` (or closest package path available)
  - `pytest -q` (or targeted subset if full suite unavailable)
- If any command cannot run due missing scaffolding, state that explicitly in your report.

## Python Code Style Guidelines

### Formatting and line length
- Follow formatter output; do not hand-format against tool decisions.
- Keep lines readable; prefer <= 100 chars unless repo formatter says otherwise.
- Use trailing commas in multiline literals/calls to stabilize diffs.

### Imports
- Group imports in this order with one blank line between groups:
  1) standard library
  2) third-party
  3) local package (`aria.*`)
- Prefer absolute imports from `aria` package root.
- Avoid wildcard imports.
- Remove unused imports immediately.

### Types
- Add type hints for all public functions, methods, and module-level constants.
- Prefer concrete types over `Any`; if `Any` is required, keep it tightly scoped.
- Use `TypedDict`, `Protocol`, `Literal`, `Enum`, and Pydantic models where appropriate.
- Keep model fields explicit; avoid untyped dict payloads across boundaries.

### Naming conventions
- Modules/files: `snake_case.py`.
- Functions/variables: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Async functions should be verb-first (`fetch_*`, `load_*`, `sync_*`) and clearly indicate side effects.

### Function and module design
- Keep functions focused and small; split orchestration from pure logic.
- Prefer explicit dependency injection over hidden global state.
- Keep I/O boundaries obvious (filesystem/network/tool calls).
- Use dataclasses or Pydantic models for structured data contracts.

## Error Handling and Reliability
- Never swallow exceptions silently.
- Catch narrow exception classes, not blanket `except Exception` unless re-raising with context.
- Raise domain-meaningful errors with actionable messages.
- Attach context (IDs, provider, operation) to logs and errors.
- For retries/backoff, use deterministic policies (e.g., tenacity) and log retry reasons.
- Respect circuit-breaker behavior for provider/tool failures.

## Logging and Observability
- Use structured JSON logging for services and daemons.
- Include timestamp, level, logger, event, and contextual fields.
- Propagate `trace_id` across gateway -> conductor -> sub-agent -> tool chains.
- Never log secrets, tokens, or raw credential payloads.

## Security and Secrets
- Do not commit plaintext secrets.
- Use `.env.example` for documented variables only.
- Keep encrypted secrets under SOPS-managed files when applicable.
- Treat credential operations as high-risk and require HITL for destructive changes.

## Testing Guidelines
- Add/adjust tests for every behavioral change.
- Prefer unit tests for routing/business logic and integration tests for tool/provider edges.
- Use fixtures for stable provider/tool mocks.
- Validate both happy paths and failure paths (timeouts, rate limits, invalid payloads).

## Documentation and ADRs
- Update docs when behavior or architecture changes materially.
- For significant decisions, add/update ADR files under `docs/foundation/decisions/`.
- Keep docs aligned with implemented paths and commands.

## Agent Working Rules
- Prefer minimal, reviewable diffs.
- Do not perform destructive git actions without explicit user instruction.
- Do not modify unrelated files.
- If repository scaffolding is incomplete, create only the minimal required structure for the requested task.
- In completion notes, distinguish:
  - commands actually executed,
  - commands recommended but not executable in current repo state.

## Quick Command Cheat Sheet
- Setup: `uv sync --dev`
- Lint: `ruff check .`
- Format: `ruff format .`
- Types: `mypy src`
- Tests (all): `pytest -q`
- Test (single): `pytest -q tests/unit/test_example.py::test_happy_path`
