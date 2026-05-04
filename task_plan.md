# Task Plan: MCP proxy integration audit → remediation

## Goal
Remediate the MCP proxy integration drift identified in the 2026-05-01 audit, implementing the approved hybrid capability-scoped architectural direction.

## Status: ✅ TRAVELLER REMEDIATION IMPLEMENTED / VERIFICATION COMPLETE

## 2026-05-04 — Traveller-agent remediation addendum
- [x] Reconstruct traveller-specific context from LLM wiki index/log + traveller wiki page
- [x] Verify FastMCP synthetic tool schemas with Context7 and local proxy inspection
- [x] Audit traveller prompt + 6 travel skills for proxy contract drift
- [x] Harden proxy middleware fail-closed behavior for backend execution
- [x] Restore Amadeus wrapper executability and add regression coverage
- [x] Update traveller wiki/index/log with provenance
- [x] Run targeted traveller/proxy regression suite
- [x] Run repository-wide gates and record unrelated pre-existing failures

## 2026-05-04 — Traveller deep-debug addendum (Sessione 8)
- [x] Analyze live autoanalysis log for missed tool calls vs prescribed pipeline
- [x] Freeze new root causes: incomplete fallback order, excessive Amadeus parallelism, weak error semantics
- [x] Harden Amadeus MCP server with retryable/fallback-aware structured errors
- [x] Encode degraded-mode rules in traveller prompt + critical travel skills
- [x] Add regression tests for degraded-mode guidance and Amadeus retry/quota behavior

## Phases

### Phase 1: Audit / forensic analysis
- [x] Read `AGENTS.md`
- [x] Read LLM wiki index/log first
- [x] Read proxy plan/spec/ADR
- [x] Inspect current proxy code paths
- [x] Inspect conductor + 3 sub-agent prompts
- [x] Inspect current skills inventory and content
- [x] Verify FastMCP behavior with Context7

### Phase 2: Requirements / audit PRD
- [x] Freeze the concrete integration gaps to fix
- [x] Define expected target contract for prompts, skills, caller propagation, and capability enforcement
- [x] Separate blocking defects from cleanup/documentation drift
- [x] Research the deeper architectural question behind agent boundaries and MCP exclusivity

### Phase 3: Technical design
- [x] Design fail-closed caller propagation and enforcement
- [x] Decide canonical invocation model (synthetic proxy tools vs backend names in frontmatter)
- [x] Define prompt/skill normalization strategy
- [x] Define wiki/spec/ADR reconciliation changes
- [x] Decide future agent-boundary model: strict exclusivity vs shared capability pools vs hybrid
- [x] Draft blueprint/ADR amendments for P9 and workspace/productivity convergence

### Phase 4: Implementation ✅
- [x] Apply runtime fixes in middleware (fail-closed enforcement)
- [x] Update agent prompts (canonical proxy contract + convergence)
- [x] Update affected skills (deep-research, office-ingest, meeting-prep, email-draft, triage-email)
- [x] Update capability matrix (productivity-agent gains google_workspace)
- [x] Update ADR-0008 (amendment for hybrid model)
- [x] Update wiki docs

### Phase 5: Verification ✅
- [x] Run `ruff check .` → All checks passed
- [x] Run `ruff format --check .` → 202 files already formatted
- [x] Run `mypy src` → Success: no issues found in 90 source files
- [x] Run `pytest -q` → 673 passed, 23 skipped, 3 warnings

### Phase 6: Post-CLI behavioral remediation
- [x] Force conductor delegation to `productivity-agent` for mixed work-domain tasks
- [x] Prevent conductor from satisfying this workflow with direct `glob`/`read` operational work
- [x] Verify real HITL tool path instead of textual pseudo-confirmation
- [x] Verify `search_tools` → `call_tool` canonical proxy execution under `_caller_id: "productivity-agent"`
- [x] Prevent incorrect wiki consolidation of architecturally invalid flows
- [x] Re-run behavioral test with the same CLI scenario

### Phase 7: Productivity-agent post-delegation hardening
- [x] Prevent ordinary productivity workflows from relying on host-native `Glob`/`Read` helpers where proxy-backed MCP routes exist
- [x] Strengthen productivity-agent prompt for real HITL gating and single valid wiki update call
- [x] Align core work-domain skills with the same proxy/HITL contract
- [x] Add static contract tests for productivity-agent + core skills
- [x] Re-run full gates after the hardening

## Constraints
- Follow `AGENTS.md` strictly.
- Use wiki-first and Context7-first workflow.
- Keep diffs minimal and aligned with the original proxy plan/spec.

### Phase 8: Knowledge codification for future agents
- [x] Synthesize the lessons learned from proxy/runtime remediation into a reusable protocol
- [x] Define the mandatory research branch, including optional `github-discovery` and manual ARIA prompts
- [x] Define hard gates for P8/P9, proxy compatibility, wiki.db, HITL, observability, and testability
- [x] Save the protocol to `docs/protocols/protocollo_creazione_agenti.md`
- [x] Update wiki index/log to register the new protocol as a source of truth
