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

## Git & GitHub Workflow Rules (2026 Best Practices)

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
  - `ruff check .` (or linter for language)
  - `ruff format --check .`
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

### Secrets & Sensitive Data in Git
- NEVER commit plaintext API keys, OAuth credentials, tokens, or passwords. Use `.env` (gitignored) + SOPS-encrypted files under `.aria/credentials/secrets/`.
- If secrets are detected by GitHub push protection, FIRST evaluate: are they real credentials or false positives?
  - **Real credentials** in documentation/handoff files (e.g., OAuth client ID/secret in `docs/handoff/`): the user MUST visit the GitHub-provided bypass URL to allow the push. Agents MUST NOT strip secrets from files without explicit user instruction.
  - **Real credentials** in code: remove immediately, replace with `os.getenv(...)` or SOPS decryption, and rotate the compromised credential.
  - **False positives**: bypass via GitHub's push protection URL.
- Agents MUST NOT use `git filter-branch`, `git filter-repo`, or any history-rewriting tool without explicit user approval and a backup of the original branch.
- OAuth client IDs and secrets documented in internal handoff files are considered **intentional documentation**, not leaks. Handle them via push protection bypass, not by removing them from the files.

### Working Tree Hygiene
- Keep the working tree clean: resolve uncommitted changes before starting a new task.
- Untracked runtime/cache directories (`.aria/kilo-home/`, `.npm/`, `.cache/`, `node_modules/`) MUST remain gitignored and NEVER be committed.
- Before creating a feature branch, verify `git status --short` shows minimal changes. If there are more than 10 untracked files, identify and gitignore them first.
- A clean working tree prevents Kilo's branch review from slowing down session startup (see `docs/llm_wiki/wiki/log.md` entry 2026-04-27).

### Push Protocol
- Always use `git push origin <branch>` (simple push). Use `--force-with-lease` ONLY when:
  1. The user explicitly authorizes it (HITL gate).
  2. The remote branch has no upstream history that needs preserving (e.g., it's a personal feature branch, not `main` or a shared branch).
  3. A backup of the original branch exists locally (`git branch <branch>-backup` before force push).
- `git push --force` (without `--with-lease`) is FORBIDDEN. Use `--force-with-lease` which checks that your local ref matches the remote ref before overwriting.
- If GitHub push protection blocks the push due to secrets, follow the "Secrets & Sensitive Data in Git" rules above. Do NOT use `--force` to bypass push protection.

### Branch Lifecycle
- Feature/bugfix branches MUST be deleted locally after they are merged or superseded:
  ```bash
  git branch -d <branch-name>          # safe delete (only if merged)
  git branch -D <branch-name>          # force delete (only with HITL)
  ```
- Remote branches should be cleaned up periodically: `git remote prune origin`.
- Stale local branches (no commits in >30 days) should be listed for review: `git branch -v | grep '\[gone\]'`.
- Keep the total number of local branches under 10. Use `git worktree` for parallel tasks instead of multiple branches.

### Recovery Protocol (when things go wrong)
- If `git filter-branch` or `filter-repo` is used, the original refs are saved under `refs/original/`. Restore with:
  ```bash
  git checkout -b <recovered-branch> refs/original/refs/heads/<lost-branch>
  ```
- If a branch is accidentally deleted, recover from reflog:
  ```bash
  git checkout -b <recovered-branch> <commit-hash>   # find hash via git reflog
  ```
- If the working tree is in a dirty state after a failed rebase/merge, use `git rebase --abort` or `git merge --abort` to return to the pre-operation state.
- When in doubt, STASH before attempting destructive operations: `git stash --include-untracked` creates a safe restore point.

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
