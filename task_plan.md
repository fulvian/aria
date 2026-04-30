# Task Plan: Audit and Remediate ARIA Stabilization

## Goal
Verify the actual implementation of the pre-Phase-2 ARIA stabilization work, identify gaps versus repository claims and source-of-truth expectations, and fix the concrete breakages with robust, minimal, April-2024-compliant changes.

## Constraints
- Follow `AGENTS.md` strictly.
- Wiki-first: update `docs/llm_wiki/wiki/` after meaningful changes.
- Context7-first for libraries touched by code/config changes.
- Prefer minimal, reviewable diffs; avoid speculative Phase 2 implementation.

## Phase Breakdown

### Phase 1 — Audit and scope
- [x] Recover session context and read wiki index/log
- [x] Audit implementation areas and identify concrete breakages
- [x] Verify relevant libraries via Context7

### Phase 2 — Functional remediation
- [x] Restore missing stabilization plan source file
- [x] Implement real coordination registry loader/validator
- [x] Fix handoff contract drift in prompt and code
- [x] Fix lazy loader to parse actual MCP catalog schema
- [x] Fix generalized MCP capability probe to support YAML catalog + runtime resolution
- [x] Replace spawn stub metrics usage with observability-aware instrumentation
- [x] Add missing drift-check script entrypoint / alias if needed
- [x] Reconcile reconstructed stabilization plan with actual repository state and wiki evidence
- [x] Replace workspace-agent stub prompt with operational prompt aligned to current constraints

### Phase 3 — Test coverage
- [x] Add/update unit tests for registry
- [x] Add/update unit tests for lazy loader
- [x] Add/update unit tests for generalized MCP probe
- [x] Add/update unit tests for spawn observability/validation changes

### Phase 4 — Documentation and wiki alignment
- [x] Correct baseline and rollback documentation inconsistencies
- [x] Update wiki index/log and affected pages with provenance
- [x] Update `.workflow/state.md`, `findings.md`, `progress.md`

### Phase 5 — Verification
- [x] Run targeted pytest for touched areas
- [ ] Run `ruff check .`
- [ ] Run `mypy src`
- [x] Run `pytest -q`

## Follow-up — Full-suite warning cleanup
- [x] Identify source of remaining `PytestUnhandledThreadExceptionWarning` warnings
- [x] Tighten memory-store cursor/connection cleanup paths
- [x] Apply test-only compatibility shim for upstream `aiosqlite` teardown race
- [x] Re-run full suite warning-free

## Known Audit Findings to Address
1. `docs/plans/stabilizzazione_aria.md` is missing but referenced as source-of-truth.
2. `src/aria/launcher/lazy_loader.py` assumes `servers` is a dict, while `.aria/config/mcp_catalog.yaml` uses a list.
3. `src/aria/mcp/capability_probe.py` only parses JSON/JSONC runtime config and cannot consume the YAML catalog it claims to support.
4. `src/aria/agents/coordination/registry.py` is only a protocol; no real loader exists.
5. `src/aria/agents/coordination/spawn.py` uses stub metrics and is not aligned with observability package.
6. `.aria/kilocode/agents/aria-conductor.md` documents an invalid handoff schema (`timeout` vs `timeout_seconds`, missing `parent_agent`).
7. Baseline/wiki docs overstate completion or reference missing artifacts.
8. Reconstructed stabilization plan contains historical branch assumptions that no longer match the current repository state.
