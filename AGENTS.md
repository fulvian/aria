# AGENTS.md

## Purpose
- This file defines how coding agents should work in this repository.
- It captures build/lint/test commands, coding standards, and safety constraints.
- Follow this file unless an explicit user instruction overrides it.

## Repository Reality Check (as of 2026-04-21)
- **Status**: Phase 1 MVP — Implementation complete and in verification.
- **Source of truth**: `docs/foundation/aria_foundation_blueprint.md` (the "Stella Polare").
- **Implemented structure** (NOT planned — actual code exists):
  - `src/aria/` — Full Python package with memory, scheduler, gateway, agents, credentials subsystems.
  - `tests/` — Unit, integration, and e2e tests with pytest-asyncio.
  - `bin/aria` — Launcher script with KiloCode isolation.
  - `systemd/` — User service templates (aria-scheduler, aria-gateway, aria-memory).
  - `Makefile` — Operational tasks including `make quality`.
  - `.aria/kilocode/` — Isolated KiloCode config, agents, skills.
- When commands below require missing files, check if bootstrap is needed: `./scripts/bootstrap.sh`.

## Source of Truth
- Primary technical reference: `docs/foundation/aria_foundation_blueprint.md`.
- **Ten Commandments** (Section 16) are inderogable — always respect them:
  - P1: Isolation First — ARIA runs in dedicated workspace isolated from global KiloCode.
  - P2: Upstream Invariance — Never fork/modify KiloCode source; consume as configured dependency.
  - P3: Polyglot Pragmatism — KiloCode is TypeScript; ARIA layer is Python; MCP is the glue.
  - P4: Local-First, Privacy-First — All data, credentials, memory stay on-disk.
  - P5: Actor-Aware Memory — Every stored datum tagged with origin actor (user_input, tool_output, agent_inference, system_event).
  - P6: Verbatim Preservation — Tier 0 (raw) is authoritative and immutable.
  - P7: HITL on Destructive Actions — Destructive/costly/irreversible actions require Human-In-The-Loop.
  - P8: Tool Priority Ladder — MCP > Skill > Python script; never skip a layer.
  - P9: Scoped Toolsets — No sub-agent sees more than 20 tools simultaneously.
  - P10: Self-Documenting Evolution — Every divergence from blueprint registered via ADR.
- **Stella Polare rule**: For any discrepancy between this file and the blueprint, the blueprint takes precedence.

## Cursor / Copilot Rules
- `.cursorrules`: not found.
- `.cursor/rules/`: not found.
- `.github/copilot-instructions.md`: not found.
- If any of these files are added later, merge their directives into this document and treat them as high-priority repo policy.

## Environment and Layout

| Path | Purpose |
|------|---------|
| `/home/fulvio/coding/aria` | Project root |
| `src/aria/` | Python package root |
| `tests/` | Test suite (unit/integration/e2e/fixtures) |
| `bin/aria` | Launcher script (isolated KiloCode) |
| `systemd/` | Systemd user service templates |
| `.aria/` | Isolated state (gitignored) |
| `.aria/kilocode/` | KiloCode config, agents, skills, sessions |
| `.aria/runtime/` | Runtime data (memory, scheduler, gateway, logs) |
| `.aria/credentials/` | SOPS-encrypted secrets |
| `docs/foundation/decisions/` | Architecture Decision Records |

- Python target: 3.11+.
- Preferred dependency manager: `uv` (Makefile targets use this).

## Build / Setup Commands

### Bootstrap
```bash
./scripts/bootstrap.sh          # First-time setup (installs deps, generates keys)
./scripts/bootstrap.sh --check  # Verify environment
```

### Makefile (preferred)
```bash
make install          # uv sync
make dev-install      # uv sync --dev  
make quality          # lint + format + typecheck + test (full gate)
make lint             # ruff check src/
make format           # ruff format src/
make typecheck        # mypy src/
make test             # pytest -q
make test-unit        # pytest -q tests/unit
make test-integration # pytest -q tests/integration
make bootstrap        # ./scripts/bootstrap.sh
make systemd-start    # Start user services
make systemd-status   # Show service status
```

### Direct commands (when Makefile not available)
```bash
uv sync --dev         # Install all dependencies
uv pip install -e .    # Editable install
python -m aria.scheduler.daemon
python -m aria.gateway.daemon
python -m aria.memory.mcp_server
```

## Lint / Format / Typecheck

- Use `ruff` for linting and import/order checks.
- Use `ruff format` (configured in pyproject.toml, line-length=100).
- Use `mypy` for static typing (configured with loose mode, not strict).

### Standard quality gate (pre-commit)
```bash
ruff check src/
ruff format --check src/
mypy src
pytest -q
```

### Auto-fix workflow
```bash
ruff check src/ --fix
ruff format src/
# Re-run mypy to verify
mypy src
```

## Test Commands (pytest)

- Full suite: `pytest -q`
- Verbose with stop-on-first-failure: `pytest -x -vv`
- Unit only: `pytest -q tests/unit`
- Integration only: `pytest -q tests/integration`
- E2E only: `pytest -q tests/e2e`
- With coverage: `pytest --cov=src/aria --cov-report=term-missing`

### Single test execution
- Single file: `pytest -q tests/unit/test_example.py`
- Single test function: `pytest -q tests/unit/test_example.py::test_happy_path`
- Single test class method: `pytest -q tests/unit/test_example.py::TestRouter::test_selects_tavily`
- Pattern match: `pytest -q -k "router and not integration"`

### Pytest markers
- `@pytest.mark.unit` — Unit tests
- `@pytest.mark.integration` — Integration tests
- `@pytest.mark.e2e` — End-to-end tests
- `@pytest.mark.slow` — Slow tests

## CI Expectations for Agents
- Before proposing completion, run at minimum:
  - `make lint` (or `ruff check src/`)
  - `make typecheck` (or `mypy src`)
  - `pytest -q` (or targeted subset if full suite unavailable)
- If any command cannot run, state that explicitly in your report.

## Python Code Style Guidelines

### Formatting and line length
- Follow formatter output; do not hand-format against tool decisions.
- Line length: 100 characters (configured in pyproject.toml).
- Use trailing commas in multiline literals/calls to stabilize diffs.

### Imports
- Group imports in this order with one blank line between groups:
  1) standard library
  2) third-party (`aria.*` is third-party, not local — it's the package name)
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
- For retries/backoff, use deterministic policies (e.g., `tenacity`) and log retry reasons.
- Respect circuit-breaker behavior for provider/tool failures.

## Logging and Observability
- Use structured JSON logging for services and daemons.
- Include timestamp, level, logger, event, and contextual fields.
- Propagate `trace_id` across gateway -> conductor -> sub-agent -> tool chains.
- Never log secrets, tokens, or raw credential payloads.
- Log files stored in `.aria/runtime/logs/` with rotation.

## Security and Secrets

### Credential Management
- **API Keys**: Encrypted with SOPS+age in `.aria/credentials/secrets/api-keys.enc.yaml`.
- **OAuth Tokens**: Stored in OS keyring via `keyring` library.
- **Runtime State**: Encrypted in `.aria/runtime/credentials/providers_state.enc.yaml`.
- **Age Keys**: Separate key in `~/.config/sops/age/keys.txt`.

### Human-In-The-Loop (HITL) — Per Ten Commandment #7
Actions requiring HITL confirmation:
- Delete operations (memory forget, credential revoke)
- Write operations to external systems (send email, create calendar event)
- Expensive operations (token budget exceeded)
- New authentication (OAuth consent)

HITL implementation paths:
- `src/aria/scheduler/hitl.py` — Scheduler HITL queue
- `src/aria/gateway/hitl_responder.py` — Gateway HITL responder

### Safety Rules
- Do not commit plaintext secrets.
- Use `.env.example` for documented variables only.
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
- Current ADRs: ADR-0001 to ADR-0007 covering dependency baseline, SQLite policy, OAuth security, memory format, scheduler concurrency, prompt injection, STT stack.

## Git & GitHub Workflow Rules

### Branching Strategy
- **Primary branch**: `main` (protected, no direct pushes)
- **Feature branches**: `feature/<short-description>` or `feat/<description>`
- **Bugfix branches**: `fix/<description>` or `hotfix/<description>`
- **Branch naming**: kebab-case, max 50 chars, include ticket/issue reference when applicable
- **Branch lifetime**: Short-lived (< 1 week), single responsibility per branch

### Commit Messages (Conventional Commits)
Format: `<type>(<scope>): <description>`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, no code change
- `refactor`: Code change that neither fixes nor adds feature
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependencies, build changes
- `perf`: Performance improvements
- `ci`: CI/CD changes
- `revert`: Reverting previous commits

**Rules**:
- Subject line: max 72 characters, imperative mood ("add" not "added")
- Body: wrap at 72 chars, explain "what" and "why" not "how"
- Reference issues/PRs: `Closes #123` or `Fixes #456`
- No empty commit messages; never commit with `--no-verify`
- Squash WIP commits before merge

### Pull Request Workflow
1. Create PR from feature branch → `main`
2. PR title: follows Conventional Commits format
3. PR description: summary, motivation, changes, testing evidence
4. Required before merge:
   - At least 1 approving review (2+ for significant changes)
   - All CI checks passing
   - No unresolved review comments
   - Branch up-to-date with `main`
5. Use "Request Changes" sparingly; prefer comments for minor issues
6. PR size: prefer < 400 lines changed; break large PRs into stacked PRs

### Branch Protection Rules (enforced on `main`)
- Require pull request reviews before merging
- Require status checks to pass before merging (CI must be green)
- Dismiss stale reviews when new commits are pushed
- Require branches to be up to date before merge
- Block force-pushes to `main`
- Block branch deletion
- Require CODEOWNERS review for sensitive paths (`src/`, `docs/`)

### Code Review Best Practices
- Review < 400 lines at a time; take breaks for larger PRs
- Respond to all comments before merging
- Use "Approve" only if no blocking issues
- Use "Request Changes" only for blocking issues
- Be constructive: suggest fixes, not just criticism
- Check: logic, tests, edge cases, security, performance, docs

### Merging Strategy
- **Default merge method**: Squash and merge (clean history on `main`)
- **Merge commit**: Only for multi-commit PRs needing to preserve history
- **Rebase**: For syncing feature branches; never rebase `main`
- **Always use `--no-ff`** for merge commits to preserve feature branch history

### Safety Constraints
- NEVER force push to `main` or shared branches
- NEVER push secrets, credentials, or API keys (use `.env` pattern + `.gitignore`)
- NEVER commit generated files, build artifacts, or cache directories
- ALWAYS run quality gates before committing:
  - `make lint` (or `ruff check src/`)
  - `ruff format --check src/`
  - `mypy src` (for Python)
- NEVER disable or bypass CI checks
- Require HITL (Human-in-the-Loop) for:
  - Adding new CI/CD dependencies
  - Modifying branch protection rules
  - Transferring repository ownership
  - Deleting branches or tags

### Git Operations by Agents
- Agents MUST NOT push directly to `main` or any protected branch
- Agents MUST create feature branches for all changes
- Agents MUST open PRs for all changes to protected branches
- Agents MUST NOT amend or rebase commits that have been pushed
- Agents MUST NOT delete remote branches without explicit instruction
- Agents MUST fetch and rebase on latest `main` before finalizing work

## Agent Working Rules
- Prefer minimal, reviewable diffs.
- Do not perform destructive git actions without explicit user instruction.
- Do not modify unrelated files.
- If repository scaffolding is incomplete, create only the minimal required structure for the requested task.
- In completion notes, distinguish:
  - commands actually executed,
  - commands recommended but not executable in current repo state.

## ARIA-Specific Architecture

### Sub-Agents (in `.aria/kilocode/agents/`)
| Agent | Purpose |
|-------|---------|
| **aria-conductor** | Primary orchestrator; intent classification, dispatch to sub-agents |
| **search-agent** | Web research with multi-provider routing (Tavily, Firecrawl, Brave, Exa, SearXNG) |
| **workspace-agent** | Gmail, Calendar, Drive, Docs, Sheets via Google Workspace MCP |
| **compaction-agent** | Context Lifecycle Manager; T0→T1 distillation |
| **summary-agent** | Session summarization |
| **memory-curator** | Review queue management |

### Skills (in `.aria/kilocode/skills/`)
Implemented skills: `deep-research`, `planning-with-files`, `triage-email`, `calendar-orchestration`, `pdf-extract`, `doc-draft`, `hitl-queue`, `memory-distillation`, `blueprint-keeper`.

### MCP Servers
- **ARIA-Memory** (`src/aria/memory/mcp_server.py`) — FastMCP server for memory operations
- **Search tools** (`src/aria/tools/tavily/mcp_server.py`, etc.) — Provider-specific MCP servers
- **Google Workspace MCP** — External MCP for Gmail, Calendar, Drive
- **Brave Search MCP** — External MCP for Brave Search

### Tools Priority Ladder (per Ten Commandment #8)
1. **MCP tools** — Primary interface (memory, search providers, workspace)
2. **Skills** — Composed workflows (`deep-research`, `planning-with-files`, etc.)
3. **Python scripts** — Direct implementation (only when MCP/skill insufficient)

## Quick Command Cheat Sheet
```
make install        # uv sync
make quality        # Full quality gate (lint + format + typecheck + test)
make lint           # ruff check src/
make format         # ruff format src/
make typecheck      # mypy src/
make test           # pytest -q
make test-unit      # pytest -q tests/unit
make bootstrap      # ./scripts/bootstrap.sh
make systemd-start  # Start systemd services

pytest -q tests/unit/test_example.py::test_happy_path  # Single test
```