# Audit Findings — Sprint 0→4 (2026-04-21)

## 1. Architecture Reconstruction

Runtime layering matches blueprint §§6, 7, 8, 10:

- `gateway` (Telegram, PTB 22.x, polling, `SessionManager`, `ConductorBridge`, metrics)
  -> `scheduler` (cron/oneshot, budget/policy gate, HITL, DLQ, lease-based concurrency per ADR-0005)
  -> sub-agents: `search` (Tavily/Brave/Firecrawl/Exa + SearXNG/SerpAPI adapters, router + cache + dedup)
               `workspace` (OAuth PKCE helper, multi-account, scope manager per ADR-0003)
  -> MCP tools (`aria-memory`, `tavily`, `brave`, `firecrawl`, `exa`, `searxng`, `google_workspace`)
  -> backend daemons (`memory` daemon, `scheduler` daemon) -> SQLite (T0/T1) + keyring + SOPS.

Sprint artifacts present: agent md files under `.aria/kilocode/`, ADR-0003/4/5/6/7 accepted,
DR scripts in `scripts/`, evidence packs under `docs/implementation/phase-1/`, prompt-injection
frame utilities in `src/aria/utils/prompt_safety.py`.

Tool-scoping (P9) still <= 20 entries per inspected agent (`search-agent`, `workspace-agent`,
`aria-conductor`). `SessionManager` uses WAL + foreign_keys + lease columns; `EpisodicStore`
enforces verbatim preservation (P6) via tombstones.

## 2. Gaps and Criticalities (2026-04-21 pass)

1. **Static type reliability gap** — `uv run mypy src` initially failed with 54 errors
   concentrated in `scheduler` run outcomes, budget accounting, `SessionManager` Optional
   connection, `SOPS` lock path, `PolicyGate` timezone handling.
2. **Lint (ruff) debt in runtime code** — 38 residual issues in `src/`: long SQL/DDL literals,
   exception naming (`OAuthSetupRequired` missing Error suffix), nested-if in the circuit
   breaker, unused loop variable in rotator state load, redundant runtime re-imports
   (`uuid` in `EpisodicStore`), stdlib-naming collisions (`backupCount`), structured logging
   `Any` signatures, async-path use of `os.path.getsize`, unused `global` in logger factory.
3. **Documentation-state drift** — `sprint-02.md` and `sprint-04.md` plan frontmatters still
   `status: draft`, `sprint-01-evidence.md` also `draft`, despite completion in codebase
   and git history.

## 3. Remediation Applied (2026-04-21)

### 3.1 Static typing
- `SessionManager`: `_require_conn()` guard eliminates `Optional` connection hazards on
  every public method.
- `TaskStore.rowcount` typed explicitly; `TaskRunner` outcomes constrained with `Literal`.
- `BudgetGate` daily-usage is a typed structure (was `Any`).
- `PolicyGate` quiet-hours boundary uses a timezone-aware `datetime`.
- `SOPS` lock timeout raises with explicit exception chaining.
- mypy overrides extended for `sd_notify` and `yaml`.

### 3.2 Runtime lint (src)
- `OAuthSetupRequired` -> `OAuthSetupRequiredError` (renamed across `oauth_helper`,
  package `__init__`, tests).
- `actor_tagging.derive_actor_from_role` -> dict dispatch (`_ROLE_TO_ACTOR`);
  `actor_aggregate` collapsed to precedence chain per blueprint P5.
- `EpisodicStore`: moved `UUID` to module-level, removed redundant `from uuid import UUID as _UUID`
  and `import uuid as _uuid` re-imports; replaced `os.path.getsize` with
  `Path.stat().st_size` (fixes ASYNC240); broke long INSERT column lists across lines.
- `rotator._load_state` loop control renamed to `_provider_name`; HALF_OPEN nested-if
  merged with `and` (was SIM102); `acquire` annotated with a scoped `# noqa: PLR0912`
  since the branches encode the circuit-breaker state machine.
- `AuditLogger` singleton marked with scoped `# noqa: PLW0603`; example docstring
  reflowed under 100 cols.
- `utils.logging`: `backupCount` kept for stdlib compatibility (`# noqa: N803`); dead
  `_loggers_lock` symbol and unused `global` statement removed; `log_event(**context: Any)`
  retained with scoped `# noqa: ANN401` since structured logging accepts JSON-serializable
  values.
- `schema.EpisodicEntry.__init__(**data: Any)` annotated (pydantic init surface).
- Per-file ruff ignore for `E501` added for `memory/migrations.py` and `memory/semantic.py`
  (DDL triggers / FTS5 column projections must stay on one line for readability).

### 3.3 Documentation alignment
- `docs/plans/phase-1/sprint-02.md`: `status: draft` -> `status: implemented` (v1.0.1).
- `docs/plans/phase-1/sprint-04.md`: `status: draft` -> `status: implemented` (v1.0.1).
- `docs/implementation/phase-1/sprint-01-evidence.md`: `status: draft` -> `status: completed`
  (v1.1.1).

## 4. Verification (2026-04-21, post-remediation)

```
uv run ruff check src/        # All checks passed!
uv run ruff format --check src/  # 70 files already formatted
uv run mypy src               # Success: no issues found in 70 source files
uv run pytest -q              # 280 passed in 11.78s
```

## 5. Context7 Documentation Consulted (required)

- `/omnilib/aiosqlite` — async connection lifecycle, execute/commit patterns
  (basis for `SessionManager._require_conn()` guard and WAL pragmas).
- `/pydantic/pydantic` — v2 model configuration and kwargs typing
  (basis for `EpisodicEntry.__init__(**data: Any)` annotation).
- `/python-telegram-bot/python-telegram-bot` — `Application.builder().token().build()`
  pattern and `run_polling(allowed_updates=Update.ALL_TYPES)` (matches `gateway/daemon.py`).
- `/jd/tenacity` — `retry` with `stop_after_attempt`, combined stop conditions,
  `reraise=True` (matches circuit-breaker usage in `credentials/rotator.py`).

## 6. Residual Known Work (not blocking Sprint 0-4 closure)

- Full-repo ruff (`uv run ruff check .`) still reports pre-existing issues in
  `tests/` (missing `-> None` annotations on test functions), `scripts/` and benchmarks.
  Not in the Phase 1 `src/aria/` quality gate scope. To be addressed as a
  test-hygiene sweep in a dedicated commit.
- Sprint 1.4 evidence still flagged `verified_code_pending_live_demo`; live Telegram
  demo is outside this audit.

## 7. Google Workspace Drive auth regression (2026-04-22)

- Reproduced with session logs: Gmail tools succeed while Drive tools (`search_drive_files`,
  `list_drive_items`) fail with Drive API 403 `Method doesn't allow unregistered callers`.
- Root causes identified:
  1) Wrapper bootstrap could preserve `token: ""` with `expiry: null`, which is unsafe for
     deterministic refresh semantics.
  2) Wrapper sync path had embedded unescaped double quotes inside a `python -c "..."` block
     comment, causing silent command-argument corruption in shell parsing and preventing
     deterministic credential-file rewrite in practice.
- Independent verification: direct Python Drive call with the same file fails before refresh and
  succeeds immediately after explicit `credentials.refresh(Request())`.
- Fix applied in `scripts/wrappers/google-workspace-wrapper.sh`:
  - cached token is reused only if non-empty and paired with a parseable, future expiry;
  - otherwise bootstrap payload stores `token=null` and past expiry (`1970-01-01T00:00:00+00:00`);
  - removed embedded double quotes in inline Python comments to avoid shell tokenization issues
    in `python -c` invocation;
  - this deterministically forces refresh path and ensures bearer token injection before Drive calls.
