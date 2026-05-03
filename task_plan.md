# Task Plan: productivity-agent Google Workspace debug → remediation

## Goal
Diagnose and remediate the productivity-agent / Google Workspace regression cluster reported on 2026-05-02:
- malformed proxy invocation guidance causing the agent to call `call_tool` incorrectly;
- stale Google Workspace tool names in catalog, skills, tests, and docs;
- missing end-to-end coverage for `productivity-agent -> aria-mcp-proxy -> google_workspace`;
- source-of-truth drift between wiki, prompts, runtime copies, catalog metadata, and tests.

## Status: ✅ IMPLEMENTATION + VERIFICATION COMPLETE

## Phases

### Phase 1: Wiki-first reconstruction
- [x] Read `AGENTS.md`
- [x] Read `docs/llm_wiki/wiki/index.md`
- [x] Read `docs/llm_wiki/wiki/log.md`
- [x] Read `docs/llm_wiki/wiki/productivity-agent.md`
- [x] Read `docs/llm_wiki/wiki/google-workspace-mcp-write-reliability.md`
- [x] Read `docs/llm_wiki/wiki/mcp-proxy.md`
- [x] Read `docs/llm_wiki/wiki/agent-capability-matrix.md`

### Phase 2: Forensic diagnosis / PRD
- [x] Inspect productivity-agent prompt + runtime copy
- [x] Inspect Google Workspace skills, proxy catalog, capability matrix, and wrapper
- [x] Verify upstream `workspace-mcp` tool names with Context7
- [x] Inspect real Kilo runtime logs for Google Workspace failures
- [x] Audit proxy broker/server resolution behavior against those failures
- [x] Freeze final defect inventory and remediation scope

### Phase 3: Technical design
- [x] Define canonical proxy invocation syntax for productivity/search/workspace prompts
- [x] Define authoritative Google Workspace tool-name mapping from upstream to catalog/skills/tests
- [x] Define regression suite for proxy + productivity-agent + google_workspace e2e semantics
- [x] Define wiki/catalog provenance corrections

### Phase 4: Implementation
- [x] Apply selected fixes
- [x] Add/extend regression tests
- [x] Update wiki + state + provenance docs

### Phase 5: Verification
- [x] Run targeted regression tests
- [x] Run `ruff check .`
- [x] Run `mypy src`
- [x] Run `pytest -q` or constrained subset if full suite is noisy

## Constraints
- Follow `AGENTS.md` strictly.
- Use wiki-first and Context7-first workflow.
- Do not perform destructive git recovery without explicit approval.
- Keep fixes minimal and aligned with the proxy architecture and trader-agent protocol.

## Current suspected root causes
- `productivity-agent.md` and its runtime copy document malformed synthetic proxy calls (`aria-mcp-proxy__call_tool("search_tools", ...)` and `aria-mcp-proxy__call_tool("call_tool", ...)`), which match the live `ToolError: Cannot resolve backend for tool: call_tool` failure.
- `.aria/config/mcp_catalog.yaml` advertises stale/non-upstream Google Workspace tool names (`gmail_send`, `drive_list`, `docs_create`, etc.) that do not match current `workspace-mcp` canonical tools.
- `meeting-prep` and `email-draft` skills encode those stale names directly, so the agent is trained toward failing runtime calls even when the proxy is healthy.
- Proxy unit/integration tests preserve the same stale names, so regressions remain green while the real runtime fails with `Unknown tool: 'drive_list'`.
- There is no strong repository test covering `productivity-agent -> aria-mcp-proxy -> google_workspace` with the current upstream tool contract.

## Final remediation applied
- Corrected canonical proxy usage examples in active and runtime prompt copies.
- Updated the `google_workspace` catalog metadata to the official upstream `workspace-mcp` tool names.
- Corrected work-domain skills (`meeting-prep`, `email-draft`) and their runtime copies to the live tool names.
- Added broker-side legacy alias normalization for stale `google_workspace` names as a runtime backstop.
- Extended regression tests to lock the corrected contract.
