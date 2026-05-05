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
- **Primary operational reference (PRIMA di qualsiasi interazione)**: `docs/llm_wiki/wiki/index.md`
  e pagine correlate. La LLM Wiki (file `.md`) è la documentazione architetturale
  per coding agents che operano sul repository. Contiene architettura corrente,
  sub-agenti, skill, tool MCP via proxy e stato del runtime.
  Vedi § "LLM Wiki-First Reconstruction Rule".
- **Distinzione importante**: la LLM Wiki (`docs/llm_wiki/wiki/*.md`) non va confusa
  con il **wiki.db** (runtime memory store). Il wiki.db è interrogato dal conductor
  ARIA a runtime via `aria-memory/wiki_recall_tool` per ottenere il contesto di
  sessione (profilo utente, preferenze, lezioni apprese). La LLM Wiki in `.md` è
  invece la documentazione architetturale che un coding agent deve leggere prima
  di modificare qualsiasi file del repository.
- Respect the "Ten Commandments" (Section 16), especially:
  - Isolation first.
  - Upstream invariance (do not fork/modify KiloCode source directly).
  - Local-first privacy.
  - HITL for destructive/irreversible actions.
  - Tool priority ladder: MCP > skill > local script.

## LLM Wiki-First Reconstruction Rule (obbligatoria per coding agents)

### Premessa: LLM Wiki vs wiki.db
Questo repository ha **due sistemi wiki distinti** che non vanno confusi:

| Sistema | Cosa contiene | Dove | Chi lo usa | Come si accede |
|---------|--------------|------|-----------|----------------|
| **LLM Wiki** | Documentazione architetturale: architettura 4 livelli, sub-agenti, skill, tool MCP, decisioni ADR, protocolli | `docs/llm_wiki/wiki/*.md` | Coding agent che modificano il repository | Lettura diretta dei file `.md` (Read/Glob) |
| **wiki.db** | Memoria runtime: profilo utente, preferenze, lezioni, entità, decisioni di sessione | `.aria/runtime/wiki.db` | Conductor ARIA a runtime (inizio/fine turno) | `aria-memory/wiki_recall_tool` e `aria-memory/wiki_update_tool` via MCP |

### Principio
Ogni coding agent che opera su questo repository DEVE sempre e per primo leggere
approfonditamente la **LLM Wiki** (`docs/llm_wiki/wiki/*.md`) per comprendere
l'architettura corrente, i sub-agenti, le skill e i tool MCP prima di qualsiasi
modifica a codice, configurazione o documentazione.
Questa regola è inderogabile e precede qualsiasi altra fonte di verità.

La LLM Wiki è la fonte di verità **operativa** per:
- Architettura 4 livelli (L1 coordinamento → L2 MCP → L3 routing → L4 observability)
- Sub-agenti disponibili e loro dominio, capability, boundary
- Skill registrate e pattern di invocazione proxy
- Tool MCP accessibili via proxy (`aria-mcp-proxy__search_tools` / `aria-mcp-proxy__call_tool`)
- Catene di dispatch consentite (max 2 hop tra sub-agenti)
- Contratto runtime wiki memory (`wiki_recall` / `wiki_update`)
- Stato runtime corrente (fix, rollback, remediation in corso)
- HITL gate reali per operazioni write/distruttive/costose

### Ordine di lettura obbligatorio
Prima di rispondere all'utente o proporre modifiche al repository, il coding agent
DEVE leggere, nell'ordine:

1. **index.md**: `docs/llm_wiki/wiki/index.md` — architettura, stato corrente,
   pagine disponibili, provenienza fonti
2. **log.md**: `docs/llm_wiki/wiki/log.md` — implementazioni recenti, bug fix,
   rollback, remediation attive
3. **Pagine architetturali** (almeno le prime 7):
   - `docs/llm_wiki/wiki/mcp-architecture.md` — baseline runtime proxy-native
   - `docs/llm_wiki/wiki/mcp-refoundation.md` — L2 MCP plane, catalog MCP, governance
   - `docs/llm_wiki/wiki/agent-coordination.md` — L1 handoff Pydantic, ContextEnvelope,
     AgentRegistry, SpawnValidator, depth guard
   - `docs/llm_wiki/wiki/agent-capability-matrix.md` — capability matrix YAML,
     allowed_tools per agente, delegazioni consentite
   - `docs/llm_wiki/wiki/mcp-proxy.md` — contratto proxy canonico: synthetic
     `search_tools`, `call_tool` con `_caller_id`, fail-closed enforcement
   - `docs/llm_wiki/wiki/llm-routing.md` — L3 matrice dichiarativa YAML routing LLM,
     fallback, budget gate
   - `docs/llm_wiki/wiki/observability.md` — L4 logging JSON strutturato, metriche
     Prometheus, eventi tipati, trace_id end-to-end
4. **Pagine specifiche per agente** (almeno quelle rilevanti al task corrente):
   - `docs/llm_wiki/wiki/productivity-agent.md` — agente unificato dominio lavoro
   - `docs/llm_wiki/wiki/traveller-agent.md` — agente dominio viaggi
   - `docs/llm_wiki/wiki/research-routing.md` — policy ricerca multi-tier
   - `docs/llm_wiki/wiki/memory-v3.md` — memoria wiki.db, 4 MCP tool wiki
   - `docs/llm_wiki/wiki/memory-subsystem.md` — sottosistema memoria 5D
   - `docs/llm_wiki/wiki/aria-launcher-cli-compatibility.md` — CLI launcher
5. **Protocolli** (se pertinenti):
   - `docs/protocols/protocollo_creazione_agenti.md` — procedura creazione nuovi agenti
     con le fasi A-M (wiki-first reconstruction, Fase L runtime integration checklist)

### Cosa il coding agent DEVE apprendere dalla LLM Wiki

#### 1. Architettura 4 livelli
```
L4 — Observability (logging JSON, metriche Prometheus, eventi tipati)
L3 — LLM Routing (matrice dichiarativa, fallback, budget gate)
L2 — MCP Plane / Proxy (aria-mcp-proxy: search_tools + call_tool, 14+ backend catalog)
L1 — Coordinamento Agenti (handoff, envelope, registry, spawn depth ≤2 hop)
```

#### 2. Sub-agenti ARIA e dominio
| Agente | Tipo | Dominio | Tool proxy | Spawn depth |
|--------|------|---------|------------|:-----------:|
| search-agent | worker | Ricerca web multi-tier | `aria-mcp-proxy__*` | 1 |
| productivity-agent | worker | Lavoro unificato (file office, GW, briefing, email) | `aria-mcp-proxy__*` + `google_workspace__*` | 1 |
| trader-agent | worker | Finanza (7 skill, 8 intent) | `aria-mcp-proxy__*` | 0 |
| traveller-agent | worker | Viaggi (6 skill, 7 intent, 4 backend) | `aria-mcp-proxy__*` | 1 |

#### 3. Catene di dispatch consentite (max 2 hop)
- `search-agent → productivity-agent` (ricerca + sintesi)
- `productivity-agent → workspace-agent` (operazioni GW)
- `search-agent → productivity-agent → workspace-agent` (ricerca + sintesi + send)
- `traveller-agent → productivity-agent` (export viaggio → Drive/Calendar/email)
- `traveller-agent → search-agent` (ricerca web complementare)

**Vincoli**: depth massima 2 hop. Il conductor non esegue mai lavoro operativo diretto.

#### 4. Tool MCP via proxy
Il runtime espone solo 2 entry MCP:
- `aria-memory` (diretto: wiki_recall, wiki_update, hitl_ask)
- `aria-mcp-proxy` (sintetico: `search_tools`, `call_tool`)

I backend operativi si raggiungono ESCLUSIVAMENTE via proxy:
- `aria-mcp-proxy__search_tools(query=...)` — scoperta tool backend
- `aria-mcp-proxy__call_tool(name="server__tool", arguments={..., "_caller_id": "<agent>"})`
  — esecuzione tool backend con identità chiamante

#### 5. Contratto runtime wiki memory v3 (wiki.db)
Il conductor ARIA a runtime usa il wiki.db per memoria di sessione:
- **Inizio turno**: `aria-memory/wiki_recall_tool(query=..., max_pages=5, min_score=0.3)`
- **Fine turno**: `aria-memory/wiki_update_tool(patches_json='...')` esattamente UNA volta
- Profilo utente auto-iniettato in `<profile>` nel prompt conductor
- Salience trigger: fatto stabile, preferenza, correzione, validazione, scelta archit.
- Skip rules: casual, tool_only, recall_only

#### 6. HITL gate reali
- Ogni operazione write/distruttiva/costosa/esterna non idempotente richiede gate reale
  (`hitl-queue/ask`), non pseudo-HITL testuale
- HITL triggers per agente definiti nella capability matrix

### Context7 mandatory verification
Prima di utilizzare una libreria, SDK o MCP server esterno in qualsiasi sub-agente
o skill:

1. Usare SEMPRE `context7_resolve-library-id` + `context7_query-docs` per verificare
   la documentazione ufficiale, gli API pattern e i code snippet corretti.
2. Non basarsi su conoscenza pregressa, documentazione cache, o codice di esempio
   non verificato dalla fonte ufficiale.
3. Rifiutare qualsiasi deliverable da sub-agenti che saltano la verifica Context7.
4. Documentare nella LLM Wiki eventuali discrepanze tra documentazione ufficiale e
   comportamento reale osservato, con data e provenienza.

### Anti-pattern da prevenire
- **Runtime/source-of-truth drift**: file live diversi dai template canonici. La LLM Wiki
  è la fonte di verità architetturale, non il runtime. Ogni agente deve allineare template,
  file attivi e documentazione.
- **Host-native tool drift**: usare `Glob`, `Read`, `Write` del tool host invece del
  proxy MCP canonico. I backend operativi si raggiungono solo via proxy.
- **Pseudo-HITL**: conferma testuale "vuoi procedere?" invece di un gate reale
  (`hitl-queue/ask`). Non è HITL se non usa il tool MCP formale.
- **Self-remediation leakage**: durante workflow utente ordinari, il conductor ARIA NON
  deve editare codice, configurazioni, né killare processi. I bug si segnalano,
  non si correggono live.
- **Duplicate wiki updates**: chiamare `wiki_update_tool` più di una volta per turno
  o con payload schema-invalido.
- **Confusione LLM Wiki / wiki.db**: non confondere la documentazione architetturale
  (`docs/llm_wiki/wiki/*.md`) con la memoria runtime (wiki.db via MCP). Sono due sistemi
  con scopi, formati e modalità di accesso completamente diversi.

### Wiki validity guard
La LLM Wiki NON deve contenere descrizioni di percorsi architetturalmente
invalidi (es. esecuzione diretta di task operativi da parte del conductor, bypass del
proxy, routing errato a workspace-agent). Se un task viene eseguito in modo non
canonico per contingenza:
1. NON memorializzarlo nella LLM Wiki come comportamento valido;
2. Registrare un evento di drift in observability;
3. Segnalare all'utente la necessità di remediation con data di scadenza.

### Conseguenza per failure modes
Se un sub-agente produce deliverable che violano le regole sopra (es. codice che
usa un SDK senza verifica Context7, prompt che espongono backend direttamente invece
che via proxy), il coding agent DEVE:
1. Rifiutare il deliverable con motivazione esplicita;
2. Richiedere la correzione con riferimento alla sezione violata;
3. Non accettare workaround non verificati.

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
- **LLM Wiki-First Reconstruction obbligatoria**: prima di qualsiasi modifica a
  codice, configurazione o documentazione del repository, il coding agent DEVE
  applicare la regola descritta nella sezione "LLM Wiki-First Reconstruction Rule" —
  leggere index.md, log.md, pagine architetturali e pagine specifiche per agente, e
  verificare tutte le librerie/SDK via Context7.
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
