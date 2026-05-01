# Findings — REPL Search-Agent Debug (2026-05-01)

## Wiki-first context
- Read first: `docs/llm_wiki/wiki/index.md`, `docs/llm_wiki/wiki/log.md`, `docs/llm_wiki/wiki/mcp-proxy.md`
- Relevant raw/implementation sources:
  - `.aria/kilocode/agents/aria-conductor.md`
  - `.aria/kilocode/agents/search-agent.md`
  - `src/aria/gateway/conductor_bridge.py`
  - `src/aria/gateway/session_manager.py`
  - `src/aria/mcp/proxy/server.py`
  - `src/aria/agents/coordination/registry.py`
  - `.aria/config/mcp_catalog.yaml`
  - `.aria/config/agent_capability_matrix.yaml`

## Session-specific evidence
- User session: `ses_21d455d0dffeeWTujS4HWQVNJv`
- Search-agent child session: `ses_21d25c813ffe5QGLVPfITbeU8c`
- Log path: `.aria/kilo-home/.local/share/kilo/log/2026-05-01T091326.log`

## Root-cause findings

### 1) Search grounding is prompt-only, not enforced
- `aria-conductor.md` instructs memory recall and subagent delegation, but runtime does not enforce grounded answers.
- `search-agent.md` has provider tier rules, but no strict instruction such as:
  - every substantive claim must map to a fetched source
  - no schedule/orari if not explicitly present in source output
  - if data is incomplete, answer with uncertainty instead of synthesis
- `ConductorBridge` trusts `output_data["result"]` and does not compare it to tool evidence.

### 2) Follow-up continuity is broken in gateway execution
- `ConductorBridge._spawn_conductor()` always creates a fresh `child_session_id` and does not pass `--session`.
- Fallback mode sets `KILOCODE_SESSION_ID`, but again to a fresh child session.
- This makes follow-ups like `continua` rely on fuzzy model context instead of the original grounded subagent run.

### 3) Search sessions still wake irrelevant MCP backends
- `.aria/config/mcp_catalog.yaml` includes both search and productivity backends in one enabled catalog.
- `build_proxy()` loads all enabled backends regardless of caller.
- Logs show search-only work still hits:
  - repeated `Failed to parse JSONRPC message from server`
  - Google Workspace OAuth server errors (`Port 8000 is already in use`)
- This indicates backend isolation is still missing at proxy boot/index time.

### 4) Coordination enforcement is logically wrong
- `YamlCapabilityRegistry.validate_delegation()` currently returns true if either node exists.
- This is weaker than the intended parent→child delegation graph.

## Context7 verification
- Library resolved: `/prefecthq/fastmcp`
- FastMCP docs confirm search transforms expose only `search_tools` and `call_tool` for discovery.
- The underlying tools remain callable; search transforms do not validate factual correctness of answers.
- Therefore ARIA must handle grounding discipline and backend-selection logic itself.

## Working hypotheses for fixes
1. Reuse a stable child Kilo session per ARIA/gateway session.
2. Filter proxy backends by caller/tool capability prefix before creating the proxy.
3. Harden conductor/search-agent prompts to require source-grounded reporting and explicit uncertainty.
4. Fix delegation validation to check actual allowed edges.

## Pre-existing quality-gate baseline cleanup

### Pytest
- The `proxy.conftest` collision was caused by missing package markers above the proxy trees. Adding `tests/__init__.py`, `tests/e2e/__init__.py`, and `tests/*/mcp/__init__.py` fixed fully-qualified imports.
- Adding `tests/conftest.py` to prepend the repo root restored `scripts.*` imports when pytest runs via the console entrypoint.
- After collection was fixed, 17 prompt-config tests were stale vs the proxy cutover. Minimal expectation updates aligned them with wildcard proxy tool exposure (`server__*`) and proxy-only MCP dependencies.

### Mypy
- `src/aria/launcher/__init__.py` still re-exported the removed `lazy_loader`; replacing it with an empty importable package resolved the import-untyped failure.
- The `croniter` error was only a missing-stubs problem. A narrow mypy override for `croniter` fixed `mypy src` without code churn.

### Ruff
- Repo-wide Ruff noise was concentrated in tests and standalone utility scripts, not production `src/` code.
- Minimal repo cleanup used: safe `ruff --fix`, a few real test fixes (`Any` imports), and scoped `per-file-ignores` for test-only annotation/type-check/style noise plus script-oriented `print`/complexity rules.
