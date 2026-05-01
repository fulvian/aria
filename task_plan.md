# Task Plan: MCP proxy integration audit → remediation

## Goal
Remediate the MCP proxy integration drift identified in the 2026-05-01 audit, implementing the approved hybrid capability-scoped architectural direction.

## Status: ✅ COMPLETE

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

## Constraints
- Follow `AGENTS.md` strictly.
- Use wiki-first and Context7-first workflow.
- Keep diffs minimal and aligned with the original proxy plan/spec.
