# Sprint 1.2 — Implementation Log
## Scheduler & Gateway Telegram

**Started:** 2026-04-20

---

## Session Log

### 2026-04-20

- Read sprint plan (sprint-02.md), foundation blueprint, phase-1 README
- Assessed current codebase state: scheduler/gateway daemons are stubs, no store/triggers/gates implemented
- Sprint 1.1 completed: CredentialManager, EpisodicStore, logger, config
- Decided to invoke sub-agents in parallel groups for efficiency
- Created task_plan.md and progress.md for tracking

---

## Implementation Groups

| Group | Agents | Components |
|-------|--------|------------|
| Scheduler Store & Logic | coder (scheduler-store) | W1.2.A-E |
| Scheduler Daemon | coder (scheduler-daemon) | W1.2.F-H |
| Gateway Core | coder (gateway-core) | W1.2.I, J |
| Gateway Advanced | coder (gateway-advanced) | W1.2.K, L, O |
| CLI & Systemd | coder (cli-systemd) | W1.2.M, N |

---

## Decisions

1. **ADR-0005** will be created: lease-based concurrency with `lease_owner`/`lease_expires_at`
2. **Migration**: `0003__lease_columns.sql` adds lease columns to scheduler tasks table
3. **PTB 22.x**: All handlers async, use `Application.builder()` pattern
4. **Metrics**: Prometheus client on 127.0.0.1:9090 (gateway exposes)

---

## Quality Gates Status

| Gate | Status |
|------|--------|
| ruff check | pending |
| ruff format --check | pending |
| mypy | pending |
| pytest | pending |
| systemd-analyze verify | pending |

---

## Evidence

- E2E test: `tests/e2e/test_hitl_flow.py` (with PTBTestApp mock)
- Integration test: `tests/integration/scheduler/test_end_to_end_hitl.py`

---

### 2026-04-21 (Audit sprint 0-4 and remediation)

- Reviewed blueprint + phase plans and reconstructed implemented architecture
  (gateway -> conductor -> sub-agents -> MCP -> daemons).
- Ran baseline verification:
  - `uv run mypy src` -> 54 errors (pre-remediation)
  - `uv run ruff check src/` -> 38 errors (pre-remediation)
  - `uv run pytest -q` -> 280 passed
- Queried Context7 docs (mandatory):
  - `/omnilib/aiosqlite` — async DB connection lifecycle
  - `/pydantic/pydantic` — v2 model configuration patterns
  - `/python-telegram-bot/python-telegram-bot` — Application builder + polling
  - `/jd/tenacity` — retry/circuit-breaker decorators
- First pass (typing): fixed `session_manager`, `schema`, scheduler modules,
  `credentials/sops`, `utils/logging`, `pyproject.toml` overrides.
- Second pass (lint + doc drift):
  - Renamed `OAuthSetupRequired` -> `OAuthSetupRequiredError` (src + tests).
  - Rewrote `actor_tagging` to dict dispatch + precedence chain.
  - Cleaned `EpisodicStore` UUID imports, replaced `os.path.getsize` with
    `Path.stat().st_size`, broke long DDL lines where safe.
  - `rotator`: fixed unused loop var, merged SIM102, scoped `# noqa: PLR0912`
    on circuit-breaker `acquire`.
  - `utils/logging`: removed dead `_loggers_lock` and stale `global`,
    scoped `# noqa` for stdlib-compatible `backupCount` and structured logging `**Any`.
  - `schema.EpisodicEntry.__init__(**data: Any)` annotated.
  - `pyproject.toml`: `[tool.ruff.lint.per-file-ignores]` adds `E501` for
    `memory/migrations.py` and `memory/semantic.py` (DDL/FTS5 projections).
  - Documentation frontmatters realigned: `sprint-02.md` and `sprint-04.md`
    plans -> `status: implemented`; `sprint-01-evidence.md` -> `status: completed`.
- Re-verified (post full remediation):
  - `uv run ruff check src/` -> PASS (all checks passed)
  - `uv run ruff format --check src/` -> PASS (70 files formatted)
  - `uv run mypy src` -> PASS (0 errors)
  - `uv run pytest -q` -> PASS (280 passed in 11.78s)

### 2026-04-22 (Google Workspace Drive auth hotfix)

- Investigated real session failure where Gmail tools worked but Drive tools returned
  `403 forbidden / unregistered callers`.
- Traced issue to wrapper-generated credentials bootstrap payload in
  `scripts/wrappers/google-workspace-wrapper.sh` (`token: ""` + `expiry: null`).
- Implemented fix to force refresh when no real access token exists:
  - reuse cached access token only if expiry is valid and in the future;
  - otherwise normalize token to `null` and set bootstrap `expiry` to `1970-01-01T00:00:00+00:00`.
- Verified script syntax: `bash -n scripts/wrappers/google-workspace-wrapper.sh`.
- Ran targeted workspace tests: 
  - `uv run pytest -q tests/unit/agents/workspace/test_oauth_helper.py tests/unit/agents/workspace/test_scope_manager.py` -> `8 passed`.
- Reproduced and validated credential behavior via direct API probe:
  - with `token=""` + `expiry=null`: credentials may be treated as valid before refresh;
  - with `token=null` + past expiry: Drive call auto-refreshes and succeeds.
- Identified and fixed wrapper parsing bug in inline `python -c` block:
  - removed unescaped `"` in embedded Python comments that could break shell arg parsing;
  - confirmed wrapper now rewrites `google_workspace_mcp/fulviold@gmail.com.json`
    with keyring refresh token + forced-refresh bootstrap state.

### 2026-04-22 (Workspace agent deep analysis + full plan)

- Performed deep audit of:
  - `.aria/kilocode/agents/workspace-agent.md`
  - workspace skills (`triage-email`, `calendar-orchestration`, `doc-draft`)
  - wrapper/runtime scope governance (`google-workspace-wrapper.sh`, `scope_manager.py`)
  - scheduler execution path (`src/aria/scheduler/runner.py`).
- Verified key operational gap remains: workspace tasks still route to
  `not_implemented` in scheduler runner for non-system categories.
- Verified contract mismatch still present in agent/skills tool naming
  (`google_workspace/...` vs runtime `google_workspace_*`).
- Collected external references for implementation posture:
  - Context7 `/taylorwilsdon/google_workspace_mcp`
  - Context7 `/modelcontextprotocol/python-sdk`
  - MCP spec tools/HITL security guidance
  - Google Workspace MCP configuration and security guidance.
- Produced new implementation plan:
  `docs/plans/google_workspace_agent_full_operational_plan.md`.

### 2026-04-22 (Sprint 1.6 - Phase A: Contract Normalization)

**Context7 Verified References:**
- Google Workspace MCP tools: `google_workspace_search_gmail_messages`, `google_workspace_get_gmail_message_content`, etc.
- MCP Python SDK: HITL elicitation via `ctx.elicit()`, error handling via `task.fail()`, task support via `ToolExecution`

**Phase A Work Completed:**

1. **W1.6.A1 - Fixed workspace-agent.md tool naming**
   - Changed slash-style (`google_workspace/search_gmail_messages`) to underscore prefix (`google_workspace_search_gmail_messages`)
   - Updated body text references to use underscore format
   - Changed `aria-memory/*` wildcard to specific tools: `aria_memory_remember`, `aria_memory_recall`
   - Note: 24 tools now exceeds P9 max 20 limit (to be addressed in Phase B via profiles)

2. **W1.6.A2 - Fixed triage-email skill tool naming**
   - Updated allowed-tools to underscore prefix format
   - Fixed `aria-memory/hitl_ask` → `aria_memory_hitl_ask`
   - Updated procedure text to reference new tool names

3. **W1.6.A3 - Fixed calendar-orchestration skill tool naming**
   - Updated allowed-tools to underscore prefix format
   - Added `google_workspace_get_event` and `google_workspace_modify_event` to complete event lifecycle
   - Fixed aria-memory references to underscore format

4. **W1.6.A4 - Fixed doc-draft skill tool naming**
   - Updated allowed-tools to underscore prefix format
   - Added `google_workspace_list_docs_in_folder` for folder browsing
   - Fixed aria-memory references to underscore format

5. **W1.6.A5 - Added validator rules for slash-style MCP tools**
   - Updated `scripts/validate_agents.py`:
     - Added `_is_slash_style_mcp_tool()` to detect slash-style MCP naming
     - Added `_server_exists()` for flexible server matching (underscore/hyphen variants)
     - Added `_get_server_prefix()` with progressive matching against kilo.json
     - Rejects slash-style tools with clear error message
   - Updated `scripts/validate_skills.py` with same validation logic
   - Validators now correctly identify:
     - Slash-style tools (e.g., `google_workspace/search`) as INVALID
     - Underscore-prefix tools (e.g., `google_workspace_search`) as VALID

**Quality Gates (Phase A verification):**
```
uv run ruff check src/          # PASS (All checks passed)
uv run mypy src                 # PASS (0 errors)
uv run pytest -q                # PASS (280 tests)
```

**Validator Status:**
- `workspace-agent`: Passes naming validation, fails only on 24>20 tools (Phase B issue)
- `triage-email`: PASS
- `calendar-orchestration`: PASS
- `doc-draft`: PASS
- `deep-research`: FAILS (slash-style tools) - outside current sprint scope

**Known Issues:**
- workspace-agent has 24 tools > 20 P9 limit (to be addressed via profiles in Phase B)

### 2026-04-22 (Sprint 1.6 - Phase A+B: Contract Normalization + Profiled Agents)

**Phase A Completed:**
- Fixed workspace-agent.md tool naming (slash → underscore prefix) ✅
- Fixed triage-email, calendar-orchestration, doc-draft skill naming ✅
- Added validator rules to block slash-style MCP tools ✅

**Phase B Completed:**
- Created 8 profiled workspace agents (<=20 tools each, P9 compliant):
  - `workspace-mail-read.md` (4 tools)
  - `workspace-mail-write.md` (5 tools)
  - `workspace-calendar-read.md` (5 tools)
  - `workspace-calendar-write.md` (6 tools)
  - `workspace-docs-read.md` (6 tools)
  - `workspace-docs-write.md` (7 tools)
  - `workspace-sheets-read.md` (6 tools)
  - `workspace-sheets-write.md` (9 tools)
- Reduced base workspace-agent.md from 24 to 17 tools (<=20 P9 compliant)
- Created `docs/roadmaps/workspace_tool_profile_matrix.md` documenting all profiles

**Quality Gates:**
```
uv run python scripts/validate_agents.py  # PASS (8 agents)
uv run python scripts/validate_skills.py # deep-research FAILS (slash-style, out of scope)
uv run ruff check src/                   # PASS
uv run mypy src                          # PASS (0 errors)
uv run pytest -q tests/unit/agents/workspace tests/unit/scheduler  # PASS (105 tests)
```

**Validator Status:**
- workspace-agent: 17 tools ✅ (<=20 P9 compliant)
- All 8 profiled agents: validated ✅
- deep-research skill: FAILS on slash-style tools (search-agent scope, not workspace)
