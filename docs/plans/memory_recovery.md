# ARIA Memory Recovery Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore ARIA memory persistence and recall so REPL/Telegram conversations are reliably written to T0 episodic, distilled into T1 semantic chunks, and retrievable by topic-based recall (e.g. "abbiamo parlato di barbecue?").

**Architecture:** Patch the auto-persistence gap in the REPL (Kilo TUI) path by (a) granting the `aria-conductor` agent the `aria-memory/remember` tool plus a mandatory persistence policy in its system prompt, (b) introducing a per-Kilo-session deterministic ARIA `session_id`, (c) repairing the broken `ConductorBridge.add(...)` calls in the gateway path, (d) cleaning the benchmark pollution from `episodic.db` and adding an opt-in benchmark namespace, (e) fixing `recall_episodic` to honor a `query` filter and to exclude benchmark/test sessions by default, (f) replacing the keyword-only CLM with a more inclusive distillation policy that also chunks `agent_inference` summaries and conversation topics, (g) hardening the scheduler so the `VACUUM`/WAL cycle no longer deadlocks against the long-lived MCP connection, and (h) adding integration tests that prove a REPL turn round-trips through write→distill→recall.

**Tech Stack:** Python 3.11+, `aiosqlite`, FastMCP 3.x (`fastmcp` package), Pydantic v2 models in `aria.memory.schema`, KiloCode CLI agents (Markdown front-matter), pytest + pytest-asyncio, `uv`.

**Repository constraints:** All work happens on a feature branch off `main`. Follow `CLAUDE.md` (Ten Commandments, Conventional Commits, mandatory Context7 + LLM Wiki maintenance). Never bypass HITL on destructive ops; tombstones only — no hard delete.

---

## Investigation Summary (Phase 1: Root-Cause Findings)

Live evidence collected on `feature/workspace-write-reliability` @ 2026-04-26.

### Database snapshot (`.aria/runtime/memory/episodic.db`)

| Metric | Value |
|--------|-------|
| `t0_count` | 1008 entries |
| `t1_count` (semantic chunks) | **0** |
| Tombstones | 0 |
| Sessions | (mixed: real + benchmark) |
| Oldest entry | 2026-04-21 05:20:01 UTC |
| **Newest entry** | **2026-04-24 10:54:15 UTC** |
| Entries per day | 2026-04-21: **1000** (`test content entry NNN for memory recall benchmark`); 2026-04-23: 5; 2026-04-24: 3 |
| HITL pending | 0 |

**Implication:** zero real conversations have been persisted since 2026-04-24, despite multiple REPL sessions on 2026-04-25 and 2026-04-26 (the BBQ research session included).

### Live MCP traffic on 2026-04-26 (`mcp-aria-memory-2026-04-26.log`)

```
ListToolsRequest x6 (TUI bootstrap)
CallToolRequest @ 17:55:44.353 → recall(query="barbecue")
CallToolRequest @ 17:55:54.582 → recall_episodic(query="barbecue", limit=50)
CallToolRequest @ 17:56:14.163 → recall_episodic(limit=100)
```

**Implication:** the conductor only ever invokes `recall*` — it has never called `remember`. The `query=` argument passed to `recall_episodic` is silently dropped because the tool signature does not accept it.

### Systemd snapshot

| Service | State | Notes |
|---------|-------|-------|
| `aria-gateway.service` | active (running) | `telegram_adapter` is a stub: `Telegram adapter started (stub - would start polling)` — no inbound traffic processed. |
| `aria-scheduler.service` | **deactivating (timeout)** | Loop log: `Memory task ... failed: cannot VACUUM - SQL statements in progress` repeated every 10s until `start operation timed out. Terminating.` |
| `aria-memory.service` | n/a | MCP server is spawned by Kilo TUI per session, not by systemd. |

### Code-level defects

1. **`src/aria/gateway/conductor_bridge.py:142,179,191`** — calls `await self._store.add(session_id=..., actor=..., ...)` but `EpisodicStore` exposes only `insert(entry: EpisodicEntry)`. Latent `AttributeError`.
2. **`src/aria/memory/mcp_server.py:223-277`** — `recall_episodic` signature: `(session_id, since, limit)` with no `query`. Agent prompts treat it as keyword-searchable; the parameter is dropped.
3. **`src/aria/memory/clm.py:184-229`** — `_distill_entries` skips every entry where `actor != Actor.USER_INPUT`. Assistant turns (`agent_inference`), tool outputs and system events never become semantic chunks. Even the user side is filtered through the small `PREFERENCE_KEYWORDS`/`ACTION_ITEM_PATTERNS`/`FACT_PATTERNS` sets. A general topic like "barbecue" never matches → no chunk → unsearchable in T1.
4. **`src/aria/memory/mcp_server.py:78-84`** — `_get_session_id()` reads `ARIA_SESSION_ID`; if absent it returns a fresh `uuid4()` per call. Each `remember()` invocation can thus end up in a different session, fragmenting recall.
5. **`.aria/kilocode/agents/aria-conductor.md`** — `allowed-tools` lists `aria-memory/*` (so `remember` is technically reachable) **but** the system prompt mandates only `aria-memory/recall`. There is no instruction to `remember` user input or assistant output. With auto mode, the conductor never persists.
6. **Benchmark pollution** — 1000 entries dated 2026-04-21 dominate every list/range query. `EpisodicStore.list_by_time_range` is hard-capped at 500 rows and is FIFO-sorted (`ORDER BY ts ASC`). The scheduler's `distill_range(hours=6)` therefore can never reach real conversation entries when the window straddles 2026-04-21.
7. **Scheduler reaper** — `EpisodicStore.vacuum_wal()` runs `PRAGMA wal_checkpoint(TRUNCATE)` then `VACUUM`. With the long-lived FastMCP connection holding an implicit transaction, `VACUUM` raises `cannot VACUUM - SQL statements in progress` and the systemd unit cycles until timeout.
8. **No round-trip integration test** for the REPL path. Existing tests cover only direct `EpisodicStore`/`CLM` calls and the (non-functional) gateway path.
9. **Wiki gap** — `docs/llm_wiki/wiki/memory-subsystem.md` claims "All 7 gaps closed" but the live system contradicts that on every operational metric. Wiki must be updated post-fix.

### Root-cause taxonomy

| ID | Severity | Description | Layer |
|----|----------|-------------|-------|
| R1 | CRITICAL | Conductor never calls `remember` (no system-prompt mandate) | Agent prompt |
| R2 | CRITICAL | `ConductorBridge` calls non-existent `_store.add` | Gateway code |
| R3 | HIGH | Telegram adapter is a stub → gateway path inert | Gateway code |
| R4 | HIGH | `recall_episodic` ignores topic queries | MCP API |
| R5 | HIGH | 1000 benchmark rows pollute every range query | Data |
| R6 | HIGH | CLM yields zero chunks for conversational topics | CLM rules |
| R7 | HIGH | Scheduler `VACUUM` deadlock vs. live MCP connection | Scheduler/SQLite |
| R8 | MEDIUM | No stable per-Kilo-session ARIA `session_id` | MCP server |
| R9 | MEDIUM | CLM filters out non-`USER_INPUT` actors | CLM rules |
| R10 | MEDIUM | No integration test for REPL → episodic → semantic → recall | Tests |
| R11 | LOW | Wiki claims all gaps closed (inaccurate) | Docs |
| R12 | LOW | `aria-conductor.md` `mcp-dependencies: []` empty | Agent metadata |

---

## Mandatory pre-implementation actions (per `CLAUDE.md`)

Before touching any production code, the implementer must:

1. **Context7 verification** — capture and store evidence in the wiki:
   - `context7_resolve-library-id` with name `fastmcp`, query `tool decorator parameters and signature evolution`. Then `context7_query-docs` with that ID asking how to add an optional `query` parameter to an existing FastMCP tool without breaking existing call sites.
   - `context7_resolve-library-id` with name `aiosqlite`, query `concurrent connections, WAL checkpoint and VACUUM coordination`. Then `context7_query-docs` to confirm how to safely run `wal_checkpoint(TRUNCATE)` and `VACUUM` in a multi-connection scenario.
   - `context7_resolve-library-id` with name `kilocode` (fall back to `kilo-org/kilocode`), query `agent file front-matter schema, allowed-tools, hooks and session lifecycle`. Then `context7_query-docs` to confirm the supported way to inject per-session env vars (we need `ARIA_SESSION_ID`) and any built-in hook for session start/end. Record whether Kilo exposes a usable hook; if not, the plan's session-id wiring stays MCP-side.
2. **Wiki bootstrap check** — `ls docs/llm_wiki/wiki/` must show `index.md`, `log.md`, `memory-subsystem.md`. If missing, run `./scripts/bootstrap.sh` first.
3. **Branch** — create `fix/memory-recovery` off the current branch tip. Do not push to `main`.
4. **Backup** — copy `.aria/runtime/memory/episodic.db` to `.aria/runtime/memory/episodic.db.bak.$(date +%Y%m%d-%H%M%S)` before running any cleanup task. Confirm copy size matches.

The plan below assumes Context7 results agree with the existing API surface; if Context7 shows a deprecated/changed pattern (e.g. FastMCP renaming `@mcp.tool`), the implementer must update the relevant code blocks before committing.

---

## File Map

### Created files

| Path | Responsibility |
|------|----------------|
| `scripts/memory/cleanup_benchmark_entries.py` | One-shot script: tombstone all entries whose content matches the benchmark pattern, emitting a JSON report. |
| `scripts/memory/repl_persistence_sidecar.py` | Optional sidecar daemon (only spawned if Context7 confirms Kilo has no usable per-turn hook) that tails the Kilo session JSON and mirrors turns into the episodic store. |
| `tests/integration/memory/test_repl_persistence_roundtrip.py` | Round-trip test: simulate a Kilo turn → `remember` → `distill_session` → `recall` returns the topic. |
| `tests/integration/memory/test_recall_episodic_query.py` | Verifies the new `query` filter on `recall_episodic` and benchmark-exclusion default. |
| `tests/unit/memory/test_clm_inclusive_distillation.py` | Unit tests for the relaxed CLM rules (covers `agent_inference`, generic topic chunks, dedup). |
| `tests/unit/scheduler/test_reaper_no_vacuum_deadlock.py` | Verifies reaper survives a held read transaction. |

### Modified files

| Path | Change |
|------|--------|
| `.aria/kilocode/agents/aria-conductor.md` | Add `aria-memory/remember` to `allowed-tools`; add explicit pre/post turn `remember` policy; add `mcp-dependencies: [aria-memory]`; document the `ARIA_SESSION_ID` env contract. |
| `src/aria/gateway/conductor_bridge.py` | Replace three `self._store.add(...)` calls with the proper `EpisodicEntry` + `self._store.insert(entry)` pattern. |
| `src/aria/memory/mcp_server.py` | (a) Add `query` parameter to `recall_episodic` and execute FTS5 when provided; (b) default exclusion of `tags=['benchmark']` and `session_id`s starting with the literal benchmark prefix; (c) deterministic `_get_session_id()` based on `ARIA_SESSION_ID` with a clear error if missing in interactive mode. |
| `src/aria/memory/clm.py` | Allow `agent_inference` chunks (kind `concept`); add a fallback "topic" chunk per user message when no rule fires (uses keyword extraction); raise the per-call entry cap and add pagination. |
| `src/aria/memory/episodic.py` | Add `list_by_time_range(..., exclude_tags=...)` and lift the 500 cap to a configurable max; add `vacuum_wal()` retry-with-backoff and skip `VACUUM` when `BUSY` is observed. |
| `src/aria/scheduler/reaper.py` | Use the new vacuum policy; log the skipped `VACUUM` instead of raising. |
| `bin/aria` | Export `ARIA_SESSION_ID` (UUIDv4) into the spawned Kilo env on `repl`/`run`. |
| `docs/llm_wiki/wiki/memory-subsystem.md` | Replace the "all gaps closed" claim with the current findings, then later mark the new fixes done after Phase 4 completes. |
| `docs/llm_wiki/wiki/index.md` | Add this plan to the Raw Sources table. |
| `docs/llm_wiki/wiki/log.md` | Append phase-by-phase log entries. |

---

## Phases overview

- **Phase 0 — Safety net:** branch, backup, Context7 evidence, wiki status update.
- **Phase 1 — Stop the bleeding:** make new conversations actually persist (R1, R8, agent prompt + `ARIA_SESSION_ID`).
- **Phase 2 — Repair existing code paths:** fix `ConductorBridge` (R2), `recall_episodic` `query` (R4), CLM inclusivity (R6, R9).
- **Phase 3 — Data hygiene:** tombstone benchmark pollution (R5) + scheduler VACUUM safety (R7).
- **Phase 4 — Verification + wiki:** integration tests (R10) + wiki/log refresh (R11, R12).

Each task ends with a commit. Use Conventional Commits per `CLAUDE.md`.

---

## Phase 0 — Safety Net

### Task 0.1: Create branch and backup

**Files:** none modified yet.

- [ ] **Step 1: Cut a new branch**

```bash
git checkout -b fix/memory-recovery
```

- [ ] **Step 2: Backup live episodic DB**

```bash
ts=$(date +%Y%m%d-%H%M%S)
cp .aria/runtime/memory/episodic.db ".aria/runtime/memory/episodic.db.bak.${ts}"
cp .aria/runtime/memory/episodic.db-wal ".aria/runtime/memory/episodic.db-wal.bak.${ts}" 2>/dev/null || true
cp .aria/runtime/memory/episodic.db-shm ".aria/runtime/memory/episodic.db-shm.bak.${ts}" 2>/dev/null || true
ls -la .aria/runtime/memory/episodic.db*
```

Expected: backup files present, primary DB unchanged.

- [ ] **Step 3: Stop the cycling scheduler unit so its restarts do not interleave with cleanup**

```bash
systemctl --user stop aria-scheduler.service
systemctl --user status aria-scheduler.service | head -5
```

Expected: `inactive (dead)` (or `failed`).

- [ ] **Step 4: Commit the backup paths via .gitignore (do not commit the DB itself)**

```bash
grep -q '^\.aria/runtime/memory/episodic\.db\.bak\.' .gitignore || \
  printf '\n# memory recovery backups\n.aria/runtime/memory/episodic.db.bak.*\n.aria/runtime/memory/episodic.db-wal.bak.*\n.aria/runtime/memory/episodic.db-shm.bak.*\n' >> .gitignore
git add .gitignore
git commit -m "chore(memory): ignore episodic DB recovery backups"
```

### Task 0.2: Context7 verification gate

**Files:** scratch notes only (kept out of repo).

- [ ] **Step 1: Resolve and query FastMCP**

Manually invoke (in this Claude session, before writing code) the Context7 tools:
- `context7_resolve-library-id` with `name="fastmcp"`, `query="tool decorator optional parameters and signature changes"`.
- `context7_query-docs` with the returned ID and the same question.

Record the verified ID and the relevant snippet in `docs/llm_wiki/wiki/memory-subsystem.md` under a new `## Context7 Verification (memory-recovery)` section in Task 4.2.

- [ ] **Step 2: Resolve and query aiosqlite**

- `context7_resolve-library-id` with `name="aiosqlite"`, `query="concurrent connections WAL checkpoint VACUUM"`.
- `context7_query-docs` with the returned ID asking specifically how to coordinate `PRAGMA wal_checkpoint(TRUNCATE)` and `VACUUM` when another connection holds an open read transaction.

Record verbatim guidance in the same wiki section.

- [ ] **Step 3: Resolve and query Kilo CLI**

- `context7_resolve-library-id` with `name="kilocode"` (fall back to `kilo-org/kilocode`), `query="agent allowed-tools front-matter, run --auto session lifecycle, hooks"`.
- `context7_query-docs` to confirm: (a) the canonical front-matter keys; (b) any hook for `before-turn` / `after-turn`; (c) how env vars set by the parent `bin/aria` reach the agent's MCP server children.

If no per-turn hook exists, the plan's persistence policy stays in the agent prompt + `ARIA_SESSION_ID` env. If a hook does exist, add a follow-up task in Phase 4 (after-the-fact) to migrate the persistence to the hook.

- [ ] **Step 4: Commit the wiki note placeholder**

(The wiki edits land in Task 4.2; this step only verifies the Context7 calls completed without errors. Do not commit yet — proceed to Phase 1.)

---

## Phase 1 — Stop the Bleeding (auto-persist new turns)

### Task 1.1: Stable per-session `ARIA_SESSION_ID` from `bin/aria`

**Files:**
- Modify: `bin/aria` (set `ARIA_SESSION_ID` for `repl` and `run` subcommands)
- Modify: `src/aria/memory/mcp_server.py:78-84` (`_get_session_id`)
- Test: `tests/unit/memory/test_session_id_resolver.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/memory/test_session_id_resolver.py`:

```python
"""Unit tests for ARIA_SESSION_ID resolution in the memory MCP server."""

from __future__ import annotations

import os
import uuid

import pytest

from aria.memory import mcp_server


def _restore_env(name: str, original: str | None) -> None:
    if original is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = original


def test_get_session_id_uses_env_when_valid() -> None:
    original = os.environ.get("ARIA_SESSION_ID")
    sid = uuid.uuid4()
    os.environ["ARIA_SESSION_ID"] = str(sid)
    try:
        assert mcp_server._get_session_id() == sid
    finally:
        _restore_env("ARIA_SESSION_ID", original)


def test_get_session_id_raises_when_missing_in_strict_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_SESSION_ID", raising=False)
    monkeypatch.setenv("ARIA_MEMORY_STRICT_SESSION", "1")
    with pytest.raises(RuntimeError, match="ARIA_SESSION_ID"):
        mcp_server._get_session_id()


def test_get_session_id_falls_back_to_random_when_lax(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_SESSION_ID", raising=False)
    monkeypatch.delenv("ARIA_MEMORY_STRICT_SESSION", raising=False)
    sid = mcp_server._get_session_id()
    assert isinstance(sid, uuid.UUID)
```

- [ ] **Step 2: Run the test (must fail)**

```bash
uv run pytest tests/unit/memory/test_session_id_resolver.py -q
```

Expected: 2 of 3 tests fail (`test_get_session_id_raises_when_missing_in_strict_mode` not implemented; deterministic case may pass already if env happens to be set).

- [ ] **Step 3: Implement `_get_session_id` strict mode**

Replace `src/aria/memory/mcp_server.py:78-84` with:

```python
def _get_session_id() -> uuid.UUID:
    """Return the active ARIA session id.

    Priority:
      1. `ARIA_SESSION_ID` env var (UUID)
      2. `uuid.uuid4()` fallback when `ARIA_MEMORY_STRICT_SESSION` is unset/false

    Raises:
        RuntimeError: when strict mode is requested but no env var is set.
            Strict mode is enabled by setting `ARIA_MEMORY_STRICT_SESSION=1` and
            is required for interactive (REPL/Telegram) sessions so every
            `remember` lands in the same session bucket.
    """
    session_str = os.environ.get("ARIA_SESSION_ID", "").strip()
    if session_str:
        try:
            return uuid.UUID(session_str)
        except ValueError as exc:
            raise RuntimeError(
                f"ARIA_SESSION_ID is set but not a valid UUID: {session_str!r}"
            ) from exc
    if os.environ.get("ARIA_MEMORY_STRICT_SESSION", "").lower() in {"1", "true", "yes"}:
        raise RuntimeError(
            "ARIA_SESSION_ID is required when ARIA_MEMORY_STRICT_SESSION=1"
        )
    return uuid.uuid4()
```

Also update `remember()` to use `_get_session_id()` when `session_id` argument is empty/missing instead of generating a fresh UUID inline (replace lines 124-125 of the current file with):

```python
        sess_uuid = uuid.UUID(session_id) if session_id else _get_session_id()
```

(That call site already exists; this step double-checks that it points at the new resolver.)

- [ ] **Step 4: Re-run the unit tests (must pass)**

```bash
uv run pytest tests/unit/memory/test_session_id_resolver.py -q
```

Expected: 3 passed.

- [ ] **Step 5: Wire `bin/aria` to export `ARIA_SESSION_ID` for every Kilo invocation**

In `bin/aria`, locate the dispatch for `repl` and `run` subcommands. Immediately before the `exec`/`spawn` of the Kilo command, insert:

```bash
# ARIA memory-recovery: deterministic per-process session id
if [[ -z "${ARIA_SESSION_ID:-}" ]]; then
  if command -v uuidgen >/dev/null 2>&1; then
    ARIA_SESSION_ID="$(uuidgen)"
  else
    ARIA_SESSION_ID="$(python3 -c 'import uuid;print(uuid.uuid4())')"
  fi
fi
export ARIA_SESSION_ID
export ARIA_MEMORY_STRICT_SESSION=1
```

The exported var must propagate into the env that `kilo run` / `kilo` inherits, so the spawned MCP server child sees the same value (Kilo passes parent env unless explicitly stripped — confirm via Context7 in Task 0.2 step 3; if Kilo strips env, additionally write the value into the MCP `env` block of `.aria/kilocode/mcp.json` using `${ARIA_SESSION_ID}`).

- [ ] **Step 6: Smoke-test from a fresh shell**

```bash
unset ARIA_SESSION_ID
ARIA_HOME=/home/fulvio/coding/aria bin/aria repl --print-logs 2>&1 | head -30
```

Expected: no startup error; the printed env (or the MCP debug log) contains a valid `ARIA_SESSION_ID` UUID.

Then read the latest MCP log line:

```bash
tail -3 .aria/runtime/logs/mcp-aria-memory-$(date -u +%Y-%m-%d).log
```

Expected: a log entry referring to the new session id (or, at minimum, a `CallToolRequest` with the env present). Quit the REPL when verified.

- [ ] **Step 7: Commit**

```bash
git add tests/unit/memory/test_session_id_resolver.py src/aria/memory/mcp_server.py bin/aria
git commit -m "fix(memory): deterministic ARIA_SESSION_ID and strict-mode resolver"
```

### Task 1.2: Make `aria-conductor` persist every turn

**Files:**
- Modify: `.aria/kilocode/agents/aria-conductor.md`
- Test: `tests/unit/agents/test_aria_conductor_prompt.py` (new — static lint of the agent file)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/agents/test_aria_conductor_prompt.py`:

```python
"""Static checks on the aria-conductor agent prompt to enforce memory persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

AGENT_FILE = Path(".aria/kilocode/agents/aria-conductor.md")


@pytest.fixture(scope="module")
def agent_text() -> str:
    return AGENT_FILE.read_text(encoding="utf-8")


def test_remember_tool_is_allowed(agent_text: str) -> None:
    assert "aria-memory/remember" in agent_text, (
        "aria-conductor must declare aria-memory/remember in allowed-tools"
    )


def test_remember_user_input_is_mandatory(agent_text: str) -> None:
    must_contain = [
        "PRIMA di rispondere",
        "aria-memory/remember",
        "actor=user_input",
    ]
    for fragment in must_contain:
        assert fragment in agent_text, f"missing required fragment: {fragment!r}"


def test_remember_assistant_output_is_mandatory(agent_text: str) -> None:
    assert "actor=agent_inference" in agent_text


def test_session_id_env_is_documented(agent_text: str) -> None:
    assert "ARIA_SESSION_ID" in agent_text


def test_mcp_dependency_declared(agent_text: str) -> None:
    assert "mcp-dependencies:" in agent_text
    assert "aria-memory" in agent_text.split("mcp-dependencies:", 1)[1].splitlines()[0:3].__str__()
```

- [ ] **Step 2: Run the test (must fail)**

```bash
uv run pytest tests/unit/agents/test_aria_conductor_prompt.py -q
```

Expected: at least three failures (`remember` policy missing, env not documented, dependency empty).

- [ ] **Step 3: Update the agent file**

Replace the front-matter `allowed-tools` and `mcp-dependencies` sections of `.aria/kilocode/agents/aria-conductor.md` with:

```yaml
allowed-tools:
  - aria-memory/remember
  - aria-memory/recall
  - aria-memory/recall_episodic
  - aria-memory/distill
  - aria-memory/stats
  - sequential-thinking/*
  - spawn-subagent
mcp-dependencies:
  - aria-memory
```

(Keep `required-skills` and other front-matter keys intact.)

Then, in the body of the file, append the following section verbatim (Italian to match the existing prompt language):

```markdown
## Persistenza obbligatoria della memoria (memory-recovery)

ARIA-Conductor opera in modalità auto. Per ogni turno deve:

1. **PRIMA di rispondere** all'utente, chiamare:
   ```
   aria-memory/remember(
     content="<testo verbatim del messaggio utente>",
     actor=user_input,
     role=user,
     session_id="${ARIA_SESSION_ID}",
     tags=["repl_message"]
   )
   ```
   `ARIA_SESSION_ID` è esportato da `bin/aria` ed è valido per l'intera
   sessione Kilo. Se manca, l'MCP server in modalità strict restituirà un
   errore: in tal caso interrompi il turno e segnala il problema all'utente.

2. **DOPO aver ottenuto la risposta finale** (anche se proviene da un
   sub-agente), chiamare:
   ```
   aria-memory/remember(
     content="<testo finale della risposta>",
     actor=agent_inference,
     role=assistant,
     session_id="${ARIA_SESSION_ID}",
     tags=["repl_message", "conductor_response"]
   )
   ```

3. Se il turno include un tool output rilevante (output di sub-agente,
   ricerca web, ecc.), persisti anche quello:
   ```
   aria-memory/remember(
     content="<<TOOL_OUTPUT>><contenuto>><</TOOL_OUTPUT>>",
     actor=tool_output,
     role=tool,
     session_id="${ARIA_SESSION_ID}",
     tags=["tool_output_framed"]
   )
   ```

4. Continua a chiamare `aria-memory/recall` (o `recall_episodic` con `query`)
   prima di pianificare la risposta, per agganciare il nuovo turno al
   contesto storico.

Non saltare mai i passi 1 e 2: la mancata persistenza è un bug bloccante.
```

- [ ] **Step 4: Re-run the static prompt test (must pass)**

```bash
uv run pytest tests/unit/agents/test_aria_conductor_prompt.py -q
```

Expected: 5 passed.

- [ ] **Step 5: Smoke-test the new behaviour from REPL**

```bash
unset ARIA_SESSION_ID
ARIA_HOME=/home/fulvio/coding/aria bin/aria repl
# inside the TUI, send: "ricorda che mi piace il barbecue di pesce"
# wait for the agent reply, then quit
```

Then verify:

```bash
sqlite3 .aria/runtime/memory/episodic.db "
  SELECT actor, role, substr(content,1,80) AS preview, datetime(ts,'unixepoch') AS ts
  FROM episodic
  ORDER BY ts DESC LIMIT 5;
"
```

Expected: at least one `user_input` row with the BBQ preference and one `agent_inference` row with the conductor reply, both timestamped seconds ago.

- [ ] **Step 6: Commit**

```bash
git add .aria/kilocode/agents/aria-conductor.md tests/unit/agents/test_aria_conductor_prompt.py
git commit -m "fix(agent): enforce aria-conductor memory persistence per turn"
```

---

## Phase 2 — Repair Existing Code Paths

### Task 2.1: Fix `ConductorBridge` `_store.add` → `insert(EpisodicEntry)`

**Files:**
- Modify: `src/aria/gateway/conductor_bridge.py:140-202`
- Test: `tests/unit/gateway/test_conductor_bridge_persistence.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/gateway/test_conductor_bridge_persistence.py`:

```python
"""Verify ConductorBridge persists user/assistant/tool turns via EpisodicStore.insert."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aria.gateway.conductor_bridge import ConductorBridge
from aria.memory.schema import Actor


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        self.events.append((topic, payload))


@pytest.mark.asyncio
async def test_handle_user_message_inserts_user_then_assistant(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MagicMock()
    store.insert = AsyncMock()
    bus = _FakeBus()
    config = MagicMock()
    bridge = ConductorBridge(bus=bus, store=store, config=config, clm=None)

    async def _fake_spawn(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "text": "ok",
            "child_session_id": "ses_x",
            "tokens_used": 0,
            "framed_tool_output": "<<TOOL_OUTPUT>>foo<</TOOL_OUTPUT>>",
        }

    monkeypatch.setattr(bridge, "_spawn_conductor", _fake_spawn)

    await bridge.handle_user_message(
        {"text": "hello", "session_id": "abc", "telegram_user_id": "1", "trace_id": "t"}
    )

    assert store.insert.await_count == 3
    actors = [call.args[0].actor for call in store.insert.await_args_list]
    assert actors == [Actor.USER_INPUT, Actor.TOOL_OUTPUT, Actor.AGENT_INFERENCE]
```

- [ ] **Step 2: Run the test (must fail)**

```bash
uv run pytest tests/unit/gateway/test_conductor_bridge_persistence.py -q
```

Expected: AttributeError or AssertionError because the bridge currently calls `store.add(...)` (no such method) instead of `store.insert(EpisodicEntry(...))`.

- [ ] **Step 3: Replace the three call sites**

In `src/aria/gateway/conductor_bridge.py`, replace lines 140-202 with the version below:

```python
        # Step 1: Save user message to episodic (actor=USER_INPUT)
        from datetime import UTC, datetime as _dt
        from aria.memory.schema import EpisodicEntry as _Entry, content_hash as _hash

        await self._store.insert(
            _Entry(
                session_id=uuid.UUID(aria_session_id),
                ts=_dt.now(UTC),
                actor=Actor.USER_INPUT,
                role="user",
                content=text,
                content_hash=_hash(text),
                tags=["gateway_message"],
                meta={
                    "telegram_user_id": telegram_user_id,
                    "gateway_session_id": gateway_session_id,
                    "trace_id": trace_id,
                },
            )
        )

        # Step 2: Spawn KiloCode child session
        try:
            result = await self._spawn_conductor(
                input_text=text,
                session_id=aria_session_id,
                trace_id=trace_id,
            )
        except Exception as exc:
            logger.error("Conductor spawn failed: %s", exc)
            await self._bus.publish(
                "gateway.reply",
                {
                    "text": f"Mi dispiace, ho incontrato un errore: {exc}",
                    "session_id": gateway_session_id,
                    "trace_id": trace_id,
                },
            )
            return

        # Step 3: Save assistant response to episodic (actor=AGENT_INFERENCE)
        safe_result_text = redact_secrets(result.get("text", ""))

        framed_tool_output = result.get("framed_tool_output")
        if isinstance(framed_tool_output, str) and framed_tool_output:
            await self._store.insert(
                _Entry(
                    session_id=uuid.UUID(aria_session_id),
                    ts=_dt.now(UTC),
                    actor=Actor.TOOL_OUTPUT,
                    role="tool",
                    content=framed_tool_output,
                    content_hash=_hash(framed_tool_output),
                    tags=["tool_output_framed"],
                    meta={
                        "trace_id": trace_id,
                        "child_session_id": result.get("child_session_id"),
                    },
                )
            )

        await self._store.insert(
            _Entry(
                session_id=uuid.UUID(aria_session_id),
                ts=_dt.now(UTC),
                actor=Actor.AGENT_INFERENCE,
                role="assistant",
                content=safe_result_text,
                content_hash=_hash(safe_result_text),
                tags=["conductor_response"],
                meta={
                    "trace_id": trace_id,
                    "child_session_id": result.get("child_session_id"),
                    "tokens_used": result.get("tokens_used", 0),
                },
            )
        )
```

Note: `aria_session_id` is currently `str(uuid.uuid4())` if `gateway_session_id` is empty; either keep it as a UUID-formatted string (the call sites above wrap it with `uuid.UUID(...)`), or change the assignment a few lines above to always produce a `uuid.UUID`. Choose one and stay consistent — the test above assumes the wrapping form.

Move the import lines (`from datetime ...`, `from aria.memory.schema ...`) to the top of the module rather than inline if mypy or ruff complains; the inline form is shown only for readability of this diff.

- [ ] **Step 4: Re-run the test (must pass)**

```bash
uv run pytest tests/unit/gateway/test_conductor_bridge_persistence.py -q
```

Expected: 1 passed.

- [ ] **Step 5: Run the full memory + gateway unit subset**

```bash
uv run pytest tests/unit/memory tests/unit/gateway -q
```

Expected: all green (no regressions).

- [ ] **Step 6: Commit**

```bash
git add src/aria/gateway/conductor_bridge.py tests/unit/gateway/test_conductor_bridge_persistence.py
git commit -m "fix(gateway): persist user/tool/assistant via EpisodicStore.insert"
```

### Task 2.2: Add `query` parameter and benchmark exclusion to `recall_episodic`

**Files:**
- Modify: `src/aria/memory/mcp_server.py:223-277`
- Modify: `src/aria/memory/episodic.py` (`list_by_time_range`, new `exclude_tags` parameter)
- Test: `tests/integration/memory/test_recall_episodic_query.py` (new)

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/memory/test_recall_episodic_query.py`:

```python
"""recall_episodic must support topic queries and exclude benchmark tags."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash


@pytest.mark.asyncio
async def test_list_by_time_range_excludes_tags(tmp_path: Path) -> None:
    db_path = tmp_path / "episodic.db"
    cfg = type("Cfg", (), {"paths": type("P", (), {"runtime": tmp_path})()})()
    store = EpisodicStore(db_path, cfg)
    await store.connect()

    sid = uuid.uuid4()
    now = datetime.now(UTC)
    await store.insert(
        EpisodicEntry(
            session_id=sid, ts=now, actor=Actor.USER_INPUT, role="user",
            content="benchmark row", content_hash=content_hash("benchmark row"),
            tags=["benchmark"], meta={},
        )
    )
    await store.insert(
        EpisodicEntry(
            session_id=sid, ts=now, actor=Actor.USER_INPUT, role="user",
            content="real chat about barbecue", content_hash=content_hash("real chat about barbecue"),
            tags=["repl_message"], meta={},
        )
    )

    rows = await store.list_by_time_range(
        since=datetime.fromtimestamp(0, UTC),
        until=datetime.now(UTC),
        limit=10,
        exclude_tags=["benchmark"],
    )
    contents = [row.content for row in rows]
    assert "real chat about barbecue" in contents
    assert "benchmark row" not in contents

    matches = await store.search_text("barbecue", top_k=5)
    assert any("barbecue" in entry.content for entry in matches)
```

- [ ] **Step 2: Run the test (must fail)**

```bash
uv run pytest tests/integration/memory/test_recall_episodic_query.py -q
```

Expected: `TypeError: list_by_time_range() got an unexpected keyword argument 'exclude_tags'`.

- [ ] **Step 3: Extend `EpisodicStore.list_by_time_range`**

In `src/aria/memory/episodic.py:281-314`, replace the method with:

```python
    async def list_by_time_range(
        self,
        since: datetime,
        until: datetime,
        limit: int = 500,
        exclude_tags: list[str] | None = None,
    ) -> list[EpisodicEntry]:
        """List entries in a time range, optionally excluding tagged rows.

        Args:
            since: Start time (inclusive).
            until: End time (inclusive).
            limit: Max entries to return.
            exclude_tags: When provided, drops rows whose `tags` JSON array
                contains any of the listed tags. Useful to filter out
                benchmark/test sessions without tombstoning them.

        Returns:
            List of EpisodicEntry.
        """
        conn = await self._ensure_connected()
        since_int = int(since.timestamp())
        until_int = int(until.timestamp())

        cursor = await conn.execute(
            """
            SELECT e.* FROM episodic e
            LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
            WHERE e.ts >= ? AND e.ts <= ? AND t.episodic_id IS NULL
            ORDER BY e.ts ASC
            LIMIT ?
            """,
            (since_int, until_int, limit),
        )
        rows = await cursor.fetchall()
        entries = [self._row_to_entry(row) for row in rows]
        if exclude_tags:
            blocked = set(exclude_tags)
            entries = [e for e in entries if not blocked.intersection(e.tags)]
        return entries
```

- [ ] **Step 4: Update `recall_episodic` to accept `query` and apply exclusion by default**

In `src/aria/memory/mcp_server.py:223-277`, replace the function with:

```python
@mcp.tool
async def recall_episodic(
    session_id: str | None = None,
    since: str | None = None,
    limit: int = 50,
    query: str | None = None,
    include_benchmark: bool = False,
) -> list[dict]:
    """Recall episodic entries chronologically, optionally filtered by topic.

    Args:
        session_id: Optional session filter (UUID).
        since: Optional ISO8601 lower bound. Defaults to 7 days ago.
        limit: Max results (default 50).
        query: Optional FTS5 query. When provided, performs a full-text
            search over the episodic content within the chosen window.
        include_benchmark: When False (default) drops entries tagged with
            "benchmark" or "test_seed".

    Returns:
        List of EpisodicEntry serialized to dict.
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    excluded = None if include_benchmark else ["benchmark", "test_seed"]

    try:
        store, _, _ = await _ensure_store()

        if query:
            # Topic search: FTS5 on content; tag filter applied client-side
            entries = await store.search_text(query, top_k=max(limit, 1))
            if excluded:
                blocked = set(excluded)
                entries = [e for e in entries if not blocked.intersection(e.tags)]
            entries = entries[:limit]
        elif session_id:
            sess_uuid = uuid.UUID(session_id)
            entries = await store.list_by_session(sess_uuid, limit=limit)
            if excluded:
                blocked = set(excluded)
                entries = [e for e in entries if not blocked.intersection(e.tags)]
        else:
            now = datetime.now(UTC)
            since_dt = (
                datetime.fromisoformat(since.replace("Z", "+00:00"))
                if since
                else datetime.fromtimestamp(now.timestamp() - 7 * 86400, tz=UTC)
            )
            entries = await store.list_by_time_range(
                since_dt, now, limit=limit, exclude_tags=excluded
            )

        return [
            {
                "id": str(entry.id),
                "session_id": str(entry.session_id),
                "ts": entry.ts.isoformat(),
                "actor": entry.actor.value if isinstance(entry.actor, Actor) else entry.actor,
                "role": entry.role,
                "content": entry.content,
                "content_hash": entry.content_hash,
                "tags": entry.tags,
            }
            for entry in entries
        ]

    except Exception as e:
        return [{"error": str(e)}]
```

- [ ] **Step 5: Re-run the integration test**

```bash
uv run pytest tests/integration/memory/test_recall_episodic_query.py -q
```

Expected: 1 passed.

- [ ] **Step 6: Run the full memory test subset**

```bash
uv run pytest tests/unit/memory tests/integration/memory -q
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/aria/memory/episodic.py src/aria/memory/mcp_server.py tests/integration/memory/test_recall_episodic_query.py
git commit -m "feat(memory): recall_episodic accepts topic query and excludes benchmark tags"
```

### Task 2.3: Inclusive CLM distillation (cover assistant turns + topic fallback)

**Files:**
- Modify: `src/aria/memory/clm.py:184-294`
- Test: `tests/unit/memory/test_clm_inclusive_distillation.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/memory/test_clm_inclusive_distillation.py`:

```python
"""CLM must produce chunks for general topics and assistant turns."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from aria.memory.clm import CLM
from aria.memory.schema import Actor, EpisodicEntry, content_hash


class _StubSemantic:
    def __init__(self) -> None:
        self.chunks: list = []

    async def list_by_session(self, *_a, **_kw):  # noqa: D401
        return []

    async def insert_many(self, chunks):
        self.chunks.extend(chunks)


@pytest.fixture
def make_entry():
    def _factory(actor: Actor, role: str, content: str) -> EpisodicEntry:
        return EpisodicEntry(
            session_id=uuid.uuid4(),
            ts=datetime.now(UTC),
            actor=actor,
            role=role,
            content=content,
            content_hash=content_hash(content),
        )

    return _factory


def test_topic_fallback_chunk_for_user_input(make_entry):
    clm = CLM(store=None, semantic=_StubSemantic())  # type: ignore[arg-type]
    entries = [make_entry(Actor.USER_INPUT, "user", "Cerca una guida sul barbecue di pesce")]
    chunks = clm._distill_entries(entries)
    assert chunks, "expected at least one fallback topic chunk"
    assert any("barbecue" in c.text.lower() for c in chunks)


def test_assistant_turn_yields_concept_chunk(make_entry):
    clm = CLM(store=None, semantic=_StubSemantic())  # type: ignore[arg-type]
    entries = [
        make_entry(
            Actor.AGENT_INFERENCE,
            "assistant",
            "Riassunto della ricerca sul barbecue: tre tecniche di affumicatura.",
        )
    ]
    chunks = clm._distill_entries(entries)
    assert chunks
    assert any(c.kind == "concept" for c in chunks)
```

- [ ] **Step 2: Run the test (must fail)**

```bash
uv run pytest tests/unit/memory/test_clm_inclusive_distillation.py -q
```

Expected: 2 failures — current `_distill_entries` skips both.

- [ ] **Step 3: Update `_distill_entries` to include assistant turns + topic fallback**

In `src/aria/memory/clm.py`, replace `_distill_entries` (lines 184-229) with:

```python
    def _distill_entries(self, entries: list[EpisodicEntry]) -> list[SemanticChunk]:
        """Distill episodic entries into semantic chunks.

        Rules (extractive, no LLM):
            * USER_INPUT entries are scanned for action_item / preference /
              decision / fact patterns. When no rule matches, a fallback
              ``concept`` chunk is created from the most informative keywords
              so generic topics (e.g. "barbecue") remain searchable.
            * AGENT_INFERENCE entries (assistant responses) are persisted as
              ``concept`` chunks so summaries/answers are recoverable. P5 is
              respected because we do not infer new facts on the user's
              behalf — we just index what the assistant wrote.
            * TOOL_OUTPUT and SYSTEM_EVENT remain off-limits (P5).
        """
        chunks: list[SemanticChunk] = []
        now = datetime.now(UTC)

        by_session: dict[UUID, list[EpisodicEntry]] = {}
        for entry in entries:
            by_session.setdefault(entry.session_id, []).append(entry)

        for _session_id, session_entries in by_session.items():
            session_entries.sort(key=lambda e: e.ts)
            for entry in session_entries:
                if entry.actor == Actor.USER_INPUT:
                    rule_chunks = self._extract_from_entry(entry, now)
                    if rule_chunks:
                        chunks.extend(rule_chunks)
                    else:
                        keywords = self._extract_keywords(entry.content)
                        if keywords:
                            chunks.append(
                                self._make_chunk(
                                    source_ids=[entry.id],
                                    actor=entry.actor,
                                    kind="concept",
                                    text=entry.content,
                                    now=now,
                                )
                            )
                elif entry.actor == Actor.AGENT_INFERENCE:
                    keywords = self._extract_keywords(entry.content)
                    if keywords:
                        chunks.append(
                            self._make_chunk(
                                source_ids=[entry.id],
                                actor=entry.actor,
                                kind="concept",
                                text=entry.content,
                                now=now,
                            )
                        )
                # TOOL_OUTPUT / SYSTEM_EVENT intentionally not chunked

        seen: set[tuple[str, str]] = set()
        unique_chunks: list[SemanticChunk] = []
        for chunk in chunks:
            key = (
                str(chunk.source_episodic_ids[0]) if chunk.source_episodic_ids else "",
                chunk.text[:50],
            )
            if key not in seen:
                seen.add(key)
                unique_chunks.append(chunk)

        return unique_chunks
```

- [ ] **Step 4: Re-run the new tests**

```bash
uv run pytest tests/unit/memory/test_clm_inclusive_distillation.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Run the full memory test subset (regression check)**

```bash
uv run pytest tests/unit/memory tests/integration/memory -q
```

Expected: all green. If the existing `test_remember_distill_recall.py` asserts a specific chunk count, update that assertion to match the new behaviour (more chunks per session) — keep the original semantic intent (`assert chunks` rather than `assert len(chunks) == 2`).

- [ ] **Step 6: Commit**

```bash
git add src/aria/memory/clm.py tests/unit/memory/test_clm_inclusive_distillation.py
git commit -m "feat(memory): inclusive CLM distillation for assistant turns and topic fallback"
```

---

## Phase 3 — Data Hygiene + Scheduler Safety

### Task 3.1: Tombstone benchmark pollution

**Files:**
- Create: `scripts/memory/cleanup_benchmark_entries.py`
- Test: `tests/unit/memory/test_cleanup_benchmark_entries.py` (new)

- [ ] **Step 1: Write the failing unit test**

Create `tests/unit/memory/test_cleanup_benchmark_entries.py`:

```python
"""cleanup_benchmark_entries.py must tombstone only benchmark rows."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash
from scripts.memory.cleanup_benchmark_entries import cleanup_benchmark_entries


@pytest.mark.asyncio
async def test_only_benchmark_rows_are_tombstoned(tmp_path: Path) -> None:
    db_path = tmp_path / "episodic.db"
    cfg = type("Cfg", (), {"paths": type("P", (), {"runtime": tmp_path})()})()
    store = EpisodicStore(db_path, cfg)
    await store.connect()

    sid = uuid.uuid4()
    now = datetime.now(UTC)
    keep = EpisodicEntry(
        session_id=sid, ts=now, actor=Actor.USER_INPUT, role="user",
        content="real chat about barbecue", content_hash=content_hash("a"),
    )
    drop = EpisodicEntry(
        session_id=sid, ts=now, actor=Actor.USER_INPUT, role="user",
        content="test content entry 42 for memory recall benchmark",
        content_hash=content_hash("b"),
    )
    await store.insert(keep)
    await store.insert(drop)

    report = await cleanup_benchmark_entries(store, dry_run=False)
    assert report["tombstoned"] == 1
    assert report["scanned"] == 2

    survivors = await store.search_text("barbecue", top_k=5)
    assert any(e.id == keep.id for e in survivors)
```

- [ ] **Step 2: Run the test (must fail — script does not exist)**

```bash
uv run pytest tests/unit/memory/test_cleanup_benchmark_entries.py -q
```

Expected: ImportError.

- [ ] **Step 3: Implement the cleanup script**

Create `scripts/memory/__init__.py` (empty file) and `scripts/memory/cleanup_benchmark_entries.py`:

```python
"""Tombstone benchmark/test pollution from the episodic store.

Idempotent. Tombstones (P6) only — never hard-deletes.

Usage:
    uv run python -m scripts.memory.cleanup_benchmark_entries [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from typing import Any

from aria.config import get_config
from aria.memory.episodic import create_episodic_store, EpisodicStore

BENCHMARK_PATTERN = re.compile(
    r"^test\s+content\s+entry\s+\d+\s+for\s+memory\s+recall\s+benchmark$",
    re.IGNORECASE,
)
BENCHMARK_TAGS = {"benchmark", "test_seed"}


async def cleanup_benchmark_entries(store: EpisodicStore, *, dry_run: bool) -> dict[str, Any]:
    conn = await store._ensure_connected()
    cursor = await conn.execute(
        """
        SELECT e.id, e.content, e.tags
        FROM episodic e
        LEFT JOIN episodic_tombstones t ON e.id = t.episodic_id
        WHERE t.episodic_id IS NULL
        """
    )
    rows = await cursor.fetchall()
    scanned = len(rows)
    targets: list[str] = []
    for row in rows:
        tags = json.loads(row["tags"] or "[]")
        if BENCHMARK_TAGS.intersection(tags) or BENCHMARK_PATTERN.match(row["content"] or ""):
            targets.append(row["id"])

    if not dry_run:
        import time, uuid as _uuid
        now = int(time.time())
        await conn.executemany(
            """
            INSERT OR IGNORE INTO episodic_tombstones (episodic_id, tombstoned_at, reason)
            VALUES (?, ?, 'benchmark_cleanup')
            """,
            [(tid, now, ) for tid in targets],
        )
        await conn.commit()

    return {"scanned": scanned, "tombstoned": len(targets), "dry_run": dry_run}


async def _amain(dry_run: bool) -> int:
    config = get_config()
    store = await create_episodic_store(config)
    try:
        report = await cleanup_benchmark_entries(store, dry_run=dry_run)
    finally:
        await store.close()
    print(json.dumps(report, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Tombstone benchmark/test rows in episodic.db")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return asyncio.run(_amain(dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
```

(The `INSERT OR IGNORE` against a `PRIMARY KEY` makes the operation idempotent; the wrong `(tid, now,)` tuple in the executemany is intentional — keep `(tid, now)`. Drop the trailing comma when transcribing.)

- [ ] **Step 4: Re-run the unit test**

```bash
uv run pytest tests/unit/memory/test_cleanup_benchmark_entries.py -q
```

Expected: 1 passed.

- [ ] **Step 5: Dry-run the script against the real DB**

```bash
uv run python -m scripts.memory.cleanup_benchmark_entries --dry-run
```

Expected JSON output similar to:

```json
{ "scanned": 1008, "tombstoned": 1000, "dry_run": true }
```

If `tombstoned` is materially different from `1000`, inspect the discrepancy with:

```bash
sqlite3 .aria/runtime/memory/episodic.db \
  "SELECT COUNT(*) FROM episodic WHERE content LIKE 'test content entry % for memory recall benchmark';"
```

Resolve before proceeding.

- [ ] **Step 6: Apply the cleanup for real**

```bash
uv run python -m scripts.memory.cleanup_benchmark_entries
sqlite3 .aria/runtime/memory/episodic.db \
  "SELECT COUNT(*) FROM episodic e LEFT JOIN episodic_tombstones t ON e.id=t.episodic_id WHERE t.episodic_id IS NULL;"
```

Expected: live (non-tombstoned) count drops to ~8 (the real Apr 23-24 conversation entries) plus any new entries written during smoke tests in Phase 1.

- [ ] **Step 7: Commit**

```bash
git add scripts/memory/__init__.py scripts/memory/cleanup_benchmark_entries.py tests/unit/memory/test_cleanup_benchmark_entries.py
git commit -m "feat(memory): cleanup script tombstones benchmark entries (P6 compliant)"
```

### Task 3.2: Scheduler vacuum-without-deadlock

**Files:**
- Modify: `src/aria/memory/episodic.py:482-489` (`vacuum_wal`)
- Modify: `src/aria/scheduler/reaper.py` (graceful skip on busy)
- Test: `tests/unit/scheduler/test_reaper_no_vacuum_deadlock.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/scheduler/test_reaper_no_vacuum_deadlock.py`:

```python
"""Reaper must skip VACUUM gracefully when the DB is busy."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from aria.memory.episodic import EpisodicStore


@pytest.mark.asyncio
async def test_vacuum_wal_skips_on_busy(tmp_path: Path) -> None:
    db_path = tmp_path / "episodic.db"
    cfg = type("Cfg", (), {"paths": type("P", (), {"runtime": tmp_path})()})()
    store = EpisodicStore(db_path, cfg)
    await store.connect()

    # Hold a read transaction on a SECOND connection so VACUUM cannot run.
    other = await aiosqlite.connect(db_path)
    await other.execute("BEGIN")
    await other.execute("SELECT 1 FROM sqlite_master")

    try:
        # Must not raise; should checkpoint then return.
        await store.vacuum_wal()
    finally:
        await other.execute("ROLLBACK")
        await other.close()
        await store.close()
```

- [ ] **Step 2: Run the test (must fail or hang then fail)**

```bash
uv run pytest tests/unit/scheduler/test_reaper_no_vacuum_deadlock.py -q --timeout=30
```

Expected: failure with `cannot VACUUM - SQL statements in progress` or similar `OperationalError`.

- [ ] **Step 3: Make `vacuum_wal()` defensive**

Replace `EpisodicStore.vacuum_wal` (`src/aria/memory/episodic.py:482-489`) with:

```python
    async def vacuum_wal(self) -> None:
        """Checkpoint the WAL and best-effort VACUUM.

        Per Context7-confirmed aiosqlite guidance, ``VACUUM`` requires that no
        other connection holds an open transaction. In ARIA the long-lived MCP
        server connection makes this race common, so VACUUM is wrapped in a
        single try/except and logged as a skip on busy. WAL checkpointing is
        always attempted because it is safe under contention.
        """
        conn = await self._ensure_connected()
        try:
            await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as exc:  # noqa: BLE001 — checkpoint is best-effort
            logging.warning("wal_checkpoint(TRUNCATE) failed: %s", exc)
            return

        try:
            await conn.execute("VACUUM")
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "sql statements in progress" in msg or "database is locked" in msg:
                logging.info("VACUUM skipped (DB busy): %s", exc)
                return
            raise
```

- [ ] **Step 4: Update the reaper to log instead of erroring out**

In `src/aria/scheduler/reaper.py`, locate the call site of `vacuum_wal()` (around line 64) and confirm it is wrapped in a try/except that logs and continues (not raises). If it currently re-raises, change to:

```python
            try:
                await self._episodic_store.vacuum_wal()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Reaper vacuum_wal raised unexpectedly: %s", exc)
```

- [ ] **Step 5: Re-run the new test**

```bash
uv run pytest tests/unit/scheduler/test_reaper_no_vacuum_deadlock.py -q --timeout=30
```

Expected: 1 passed.

- [ ] **Step 6: Restart the scheduler unit and watch for cycling errors**

```bash
systemctl --user start aria-scheduler.service
sleep 5
journalctl --user -u aria-scheduler.service -n 30 --no-pager
```

Expected: no `cannot VACUUM` lines; the unit reaches `Status: "ARIA Scheduler alive"` and stays `active (running)`.

- [ ] **Step 7: Commit**

```bash
git add src/aria/memory/episodic.py src/aria/scheduler/reaper.py tests/unit/scheduler/test_reaper_no_vacuum_deadlock.py
git commit -m "fix(scheduler): vacuum_wal skips gracefully when episodic DB is busy"
```

---

## Phase 4 — Verification + Wiki

### Task 4.1: Round-trip integration test (REPL → episodic → distill → recall)

**Files:**
- Create: `tests/integration/memory/test_repl_persistence_roundtrip.py`

- [ ] **Step 1: Write the test**

Create `tests/integration/memory/test_repl_persistence_roundtrip.py`:

```python
"""End-to-end test: a simulated REPL turn must survive write → distill → recall."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aria.memory.clm import CLM
from aria.memory.episodic import EpisodicStore
from aria.memory.schema import Actor, EpisodicEntry, content_hash
from aria.memory.semantic import SemanticStore


@pytest.mark.asyncio
async def test_barbecue_topic_recall_after_distillation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIA_HOME", str(tmp_path))
    db_path = tmp_path / "episodic.db"
    cfg = type("Cfg", (), {"paths": type("P", (), {"runtime": tmp_path})()})()
    episodic = EpisodicStore(db_path, cfg)
    await episodic.connect()
    semantic = SemanticStore(db_path, cfg)
    await semantic.connect(episodic._conn)
    clm = CLM(episodic, semantic)

    sid = uuid.uuid4()
    now = datetime.now(UTC)

    user_msg = "Cerca informazioni sul barbecue di pesce siciliano"
    assistant_msg = "Ecco una sintesi: ricette tradizionali, tecniche e tempi di cottura per il barbecue di pesce."
    for actor, role, text in (
        (Actor.USER_INPUT, "user", user_msg),
        (Actor.AGENT_INFERENCE, "assistant", assistant_msg),
    ):
        await episodic.insert(
            EpisodicEntry(
                session_id=sid, ts=now, actor=actor, role=role,
                content=text, content_hash=content_hash(text),
                tags=["repl_message"],
            )
        )

    chunks = await clm.distill_session(sid)
    assert chunks, "distillation must produce at least one chunk"

    matches = await semantic.search("barbecue", top_k=10)
    assert matches, "semantic recall must surface the barbecue chunk"
    assert any("barbecue" in c.text.lower() for c in matches)

    fts = await episodic.search_text("barbecue", top_k=10)
    assert any("barbecue" in e.content.lower() for e in fts)
```

- [ ] **Step 2: Run the test**

```bash
uv run pytest tests/integration/memory/test_repl_persistence_roundtrip.py -q
```

Expected: passes after Phase 2 changes are in place. If it fails, do **not** patch the test — return to Task 2.3 and inspect the CLM rules.

- [ ] **Step 3: Run the full quality gate**

```bash
make lint
make typecheck
make test
```

Expected: all green. Address any lint/type issues introduced by the new modules.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/memory/test_repl_persistence_roundtrip.py
git commit -m "test(memory): roundtrip episodic→distill→recall covers conversational topics"
```

### Task 4.2: Live REPL acceptance check

**Files:** none modified — manual verification only.

- [ ] **Step 1: Apply the cleanup if not already done**

```bash
sqlite3 .aria/runtime/memory/episodic.db "SELECT COUNT(*) FROM episodic_tombstones WHERE reason='benchmark_cleanup';"
```

If 0, re-run `uv run python -m scripts.memory.cleanup_benchmark_entries` (Task 3.1 step 6).

- [ ] **Step 2: Restart the scheduler so the new memory tasks run on a clean DB**

```bash
systemctl --user restart aria-scheduler.service
journalctl --user -u aria-scheduler.service -n 20 --no-pager
```

Expected: no errors.

- [ ] **Step 3: Hold a fresh REPL conversation about a topic**

```bash
unset ARIA_SESSION_ID
ARIA_HOME=/home/fulvio/coding/aria bin/aria repl
# inside the TUI:
#   "Voglio fare una ricerca sul barbecue di pesce."
#   wait for the conductor's reply
#   quit (Ctrl+C / :q depending on TUI)
```

- [ ] **Step 4: Verify persistence**

```bash
sqlite3 .aria/runtime/memory/episodic.db "
  SELECT actor, role, substr(content,1,80), datetime(ts,'unixepoch')
  FROM episodic
  WHERE ts > strftime('%s','now','-10 minutes')
  ORDER BY ts;
"
```

Expected: at least one `user_input` row + one `agent_inference` row, both within the last 10 minutes, and tagged `repl_message`.

- [ ] **Step 5: Verify recall in a follow-up REPL session**

```bash
unset ARIA_SESSION_ID
ARIA_HOME=/home/fulvio/coding/aria bin/aria repl
# inside the TUI:
#   "Abbiamo mai parlato di barbecue?"
```

Expected: the conductor calls `aria-memory/recall(query="barbecue")` (or `recall_episodic(query="barbecue")`) and returns a non-empty answer that references the earlier session.

- [ ] **Step 6: If recall still misses**, return to Phase 1 with the systematic-debugging skill — do not work around with manual seeds.

### Task 4.3: Wiki + log refresh

**Files:**
- Modify: `docs/llm_wiki/wiki/memory-subsystem.md`
- Modify: `docs/llm_wiki/wiki/index.md`
- Modify: `docs/llm_wiki/wiki/log.md`

- [ ] **Step 1: Update the memory subsystem page status**

In `docs/llm_wiki/wiki/memory-subsystem.md`, replace the top header with:

```markdown
# Memory Subsystem — Architecture, Gaps, and Tools

**Last Updated**: 2026-04-26
**Status**: REMEDIATED — see Memory Recovery Plan
**Source**: `src/aria/memory/`, `docs/plans/memory_recovery.md`
```

Append a new section at the end:

```markdown
## Memory Recovery (2026-04-26)

| Issue | Resolution |
|-------|------------|
| Conductor never persisted REPL turns | aria-conductor agent prompt now mandates `aria-memory/remember` for every user/assistant turn |
| ARIA_SESSION_ID drifted per call | `bin/aria` exports a stable UUID; MCP server runs in `ARIA_MEMORY_STRICT_SESSION` mode |
| ConductorBridge crashed on `_store.add` | Replaced with proper `EpisodicEntry` + `insert()` calls |
| `recall_episodic` ignored topic queries | Added `query` parameter (FTS5) and benchmark exclusion |
| CLM produced 0 chunks for general topics | Inclusive distillation: assistant turns + topic-fallback chunks |
| 1000 benchmark entries polluted recall | One-shot tombstone via `scripts/memory/cleanup_benchmark_entries.py` |
| Scheduler stuck on `cannot VACUUM` | `vacuum_wal()` skips gracefully on busy DB |

### Context7 Verification (memory-recovery)

| Library | Verified ID | Notes |
|---------|-------------|-------|
| fastmcp | <fill in from Task 0.2 step 1> | Adding optional kwargs to `@mcp.tool` is backward-compatible |
| aiosqlite | <fill in from Task 0.2 step 2> | `VACUUM` requires no concurrent transaction; checkpoint is safe |
| kilo-org/kilocode | <fill in from Task 0.2 step 3> | Env vars exported by parent shell propagate to MCP children unless explicitly stripped |
```

- [ ] **Step 2: Add the plan to the index**

Append a row to the Raw Sources table in `docs/llm_wiki/wiki/index.md`:

```markdown
| `docs/plans/memory_recovery.md` | Piano di recupero memoria (auto-persistence, VACUUM safety, CLM inclusivo) | 2026-04-26 |
```

Bump the file's `**Last Updated**` line to `2026-04-26`.

- [ ] **Step 3: Append a log entry**

Prepend to `docs/llm_wiki/wiki/log.md`:

```markdown
## 2026-04-26 — Memory Recovery Plan Implemented

**Operation**: INVESTIGATE + FIX + VERIFY
**Branch**: `fix/memory-recovery`
**Plan**: `docs/plans/memory_recovery.md`

### Symptom
- REPL session about barbecue not retrievable later via `recall` / `recall_episodic`.
- All real-conversation persistence stopped after 2026-04-24 10:54:15.
- Scheduler unit cycling on `cannot VACUUM - SQL statements in progress`.

### Root causes
12 distinct issues spanning agent prompts, MCP server signatures, CLM rules,
data hygiene and scheduler concurrency. See plan §"Investigation Summary".

### Fix
- Conductor now writes every turn to `aria-memory/remember` with a stable
  `ARIA_SESSION_ID` exported by `bin/aria`.
- `ConductorBridge` calls the real `EpisodicStore.insert(EpisodicEntry)` API.
- `recall_episodic` accepts `query` (FTS5) and excludes benchmark tags.
- `CLM` produces concept chunks for assistant turns and topic-fallback
  chunks for user turns, lifting the keyword-only restriction.
- 1000 benchmark rows tombstoned via `scripts/memory/cleanup_benchmark_entries.py`.
- `vacuum_wal()` skips gracefully when the DB is busy.

### Quality gates
- `make lint` ✓
- `make typecheck` ✓
- `make test` ✓ (incl. new round-trip integration test)
- Live REPL recall ✓ (Task 4.2)
```

- [ ] **Step 4: Commit the wiki updates**

```bash
git add docs/plans/memory_recovery.md docs/llm_wiki/wiki/memory-subsystem.md docs/llm_wiki/wiki/index.md docs/llm_wiki/wiki/log.md
git commit -m "docs(memory): document recovery plan and wiki refresh"
```

### Task 4.4: Open the PR

**Files:** none modified.

- [ ] **Step 1: Push the branch**

```bash
git push -u origin fix/memory-recovery
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --base main --head fix/memory-recovery \
  --title "fix(memory): restore REPL persistence and recall" \
  --body "$(cat <<'EOF'
## Summary
- Conductor now writes every REPL turn to T0 episodic with a stable session id.
- `recall_episodic` accepts topic queries and excludes benchmark pollution.
- CLM produces semantic chunks for assistant turns and generic conversational topics.
- Benchmark rows tombstoned (P6); scheduler `VACUUM` no longer deadlocks against the live MCP connection.

## Test plan
- [ ] `make lint`
- [ ] `make typecheck`
- [ ] `make test`
- [ ] Manual REPL roundtrip: ask "abbiamo parlato di barbecue?" after seeding a barbecue conversation.

Closes the regression observed on 2026-04-26 where new conversations were silently dropped from memory.
EOF
)"
```

- [ ] **Step 3: Stop here and wait for human review.** Do not merge — `main` is protected and a human must approve per `CLAUDE.md` §Pull Request Workflow.

---

## Self-review checklist (already applied)

- **Spec coverage:** every root cause from the Investigation Summary maps to a task (R1→1.2, R2→2.1, R3 acknowledged but out of scope — Telegram adapter rewrite tracked separately, R4→2.2, R5→3.1, R6→2.3, R7→3.2, R8→1.1, R9→2.3, R10→4.1, R11→4.3, R12→1.2).
- **Placeholder scan:** all code blocks contain real code; no "TBD"/"add validation"/"similar to". Wiki Context7 IDs are explicit "fill in" markers tied to a specific task — that is by design (Context7 must be queried at implementation time per `CLAUDE.md`).
- **Type/method consistency:** `EpisodicStore.insert(entry: EpisodicEntry)` is the only write call site used. `_get_session_id` returns `uuid.UUID` everywhere. `recall_episodic` `query` parameter is the same name across MCP signature and tests. `cleanup_benchmark_entries(store, *, dry_run)` signature matches between the script and its test.
