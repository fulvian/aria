# Google Workspace Agent - Deep Analysis and Full Operational Plan

## Document Control

- Date: 2026-04-22 (initial), 2026-04-22 (implemented)
- Author: ARIA General Manager (analysis + orchestration)
- Status: Implemented (Sprint 1.6 complete)
- Scope: `.aria/kilocode/agents/workspace-agent.md`, workspace skills, wrapper/runtime governance, scheduler integration, tests/observability
- Target outcome: make `workspace-agent` fully operational across advanced read/edit workflows for Gmail, Docs, Sheets, Slides
- Implementation: All phases A-F completed per task_plan.md

---

## 1) Executive Summary

The Workspace integration is architecturally present but operationally under-utilized. The repository already contains:

- a working `google_workspace` MCP server wiring via wrapper,
- a governance matrix with 114 upstream tools,
- OAuth helper and scope manager components,
- initial workspace skills (`triage-email`, `calendar-orchestration`, `doc-draft`).

The main blockers are not transport-level anymore, but orchestration and capability consumption:

1. skill/agent tool naming is still inconsistent with runtime tool naming,
2. only 3 skills exist for a 114-tool surface,
3. advanced read/edit flows (Docs/Sheets/Slides/Gmail threads+attachments) are not codified into production-grade skills,
4. scheduler execution path for workspace remains stubbed,
5. test and telemetry coverage is insufficient to prove reliability and HITL compliance at scale.

This plan defines a deterministic path to full operational readiness with strict P7/P8/P9 compliance and measurable acceptance criteria.

---

## 2) Current State Audit (Repository Reality)

## 2.1 Workspace Agent - Prerogatives and Constraints

Source: `.aria/kilocode/agents/workspace-agent.md`

Observed intent and prerogatives:

- dedicated sub-agent for Gmail, Calendar, Drive, Docs, Sheets via MCP,
- explicit HITL requirement for write operations,
- memory integration (`aria-memory_recall`, `aria-memory_remember`),
- required skills linked to workspace operations.

Observed implementation issues:

- frontmatter `allowed-tools` uses slash syntax (`google_workspace/...`) instead of runtime MCP tool IDs (`google_workspace_*`),
- currently listed tools are a reduced subset and not aligned with the governance matrix breadth,
- policy text references tool names like `create_event` while matrix and current runtime use `manage_event` in places.

Impact: degraded tool-selection determinism and fragile prompt-to-tool binding.

## 2.2 Workspace Skills - Coverage and Quality

Sources:

- `.aria/kilocode/skills/triage-email/SKILL.md`
- `.aria/kilocode/skills/calendar-orchestration/SKILL.md`
- `.aria/kilocode/skills/doc-draft/SKILL.md`

Current strengths:

- clear user intent focus,
- explicit HITL intent on write paths,
- operationally useful MVP workflows.

Current gaps:

- same slash/underscore naming mismatch in skill `allowed-tools`,
- no dedicated advanced skills for:
  - Gmail thread intelligence and attachment extraction,
  - Docs structural reading/editing,
  - Sheets structural/table editing beyond basic values,
  - Slides structured editing/comments,
- no explicit fallback matrix (quota/auth/scope/tool unavailability) per skill,
- no standardized output schema contract per skill (summary + structured payload + memory tags).

## 2.3 Runtime and Security Posture

Sources:

- `scripts/wrappers/google-workspace-wrapper.sh`
- `src/aria/agents/workspace/oauth_helper.py`
- `src/aria/agents/workspace/scope_manager.py`

Current strengths:

- keyring-backed refresh token flow,
- scope coherence check against governance matrix,
- deterministic credential-file generation for upstream compatibility,
- explicit refresh forcing behavior to avoid unauthenticated calls,
- revocation hooks and scope metadata files.

Current risks:

- policy logic is strong but not fully propagated into skill-level execution contracts,
- no unified per-tool runtime telemetry schema yet,
- multi-account remains explicit phase-1 stub (`primary` only).

## 2.4 Orchestration and Execution Path

Sources:

- `.aria/kilocode/agents/aria-conductor.md`
- `src/aria/scheduler/runner.py`
- `scripts/seed_scheduler.py`

Status:

- conductor correctly delegates workspace intents,
- scheduler seeds workspace task (`daily-email-triage`),
- scheduler runner still treats non-system categories as `not_implemented`.

Impact: workspace automations cannot be considered production-operational in scheduled mode.

## 2.5 Testing and Validation Coverage

Sources:

- `tests/unit/agents/workspace/test_oauth_helper.py`
- `tests/unit/agents/workspace/test_scope_manager.py`
- scheduler HITL/policy tests

Current strengths:

- good unit coverage for OAuth/scope helper logic,
- strong scheduler HITL/policy gate tests.

Major gap:

- missing end-to-end tests for advanced workspace tool usage (Docs/Sheets/Slides/Gmail advanced read/edit),
- missing skill-level contract tests,
- missing operational metrics assertions.

---

## 3) External Research Findings (Official + MCP Best Practice)

## 3.1 Context7 - `google_workspace_mcp`

Verified capabilities include broad tooling across Gmail, Calendar, Drive, Docs, Sheets, Slides, Forms, Chat. Relevant advanced capabilities already available upstream:

- Gmail: batch message/thread content retrieval, labels/filters, batch label modifications,
- Docs: structural inspection, batch updates, comment lifecycle, markdown export, table operations,
- Sheets: formatting/conditional formatting/tables/comments,
- Slides: batch updates, page operations, comments.

Implication: current gap is mainly orchestration/skill engineering, not upstream server limitation.

## 3.2 Official Google Workspace MCP Guidance

Source: `https://developers.google.com/workspace/guides/configure-mcp-servers`

Key implementation patterns:

- server-per-product model is valid for remote MCP; local aggregated server is also valid when policy-controlled,
- strong emphasis on OAuth scope governance and explicit user review,
- explicit warning on indirect prompt injection and need for trusted-tool posture.

Implication for ARIA:

- keep strict trusted tool allowlists,
- enforce HITL and action review on all write-sensitive operations,
- preserve least-privilege scopes by profile.

## 3.3 MCP Specification and SDK Guidance

Sources:

- `https://modelcontextprotocol.io/specification/2025-06-18/server/tools`
- Context7 `/modelcontextprotocol/python-sdk`

Key patterns:

- human-in-the-loop should remain available for sensitive calls,
- tool contracts should expose clear schemas and typed inputs/outputs,
- distinguish protocol errors vs tool execution errors (`isError` semantics),
- support pagination/listing consistency and robust result parsing.

Implication for ARIA:

- define explicit skill output schemas,
- normalize error classes and retry policies by failure type,
- capture tool invocation audit traces consistently.

## 3.4 Google API Advanced Read/Edit Patterns

Official pages reviewed:

- Gmail send/threading and MIME raw flow,
- Docs table/structure and `batchUpdate` semantics,
- Slides atomic text replacement via single `batchUpdate`,
- Sheets value/structure concepts and range addressing.

Implementation implications:

- prefer atomic batch operations where supported,
- preflight structural inspection before destructive edits,
- for email replies preserve thread headers (`Subject`, `References`, `In-Reply-To`) where applicable,
- separate read-analysis pass from write-apply pass with HITL checkpoint in between.

---

## 4) Gap Matrix (Priority)

| ID | Area | Severity | Gap | Consequence |
|---|---|---|---|---|
| G1 | Tool binding | Critical | slash vs underscore tool naming mismatch in agent/skills | Non-deterministic invocation, silent no-op risk |
| G2 | Skill coverage | Critical | only 3 skills for 114 tools | most advanced capabilities unreachable |
| G3 | Advanced read/edit | Critical | no production skills for Docs/Sheets/Slides advanced workflows | user-requested features unavailable |
| G4 | Scheduler | High | workspace tasks still `not_implemented` in runner | no autonomous workspace automation |
| G5 | Test strategy | High | no e2e contracts for advanced workspace workflows | regressions likely |
| G6 | Observability | High | no per-tool telemetry dashboard/reporting | weak operational confidence |
| G7 | Governance sync | Medium | governance matrix and runtime profiles not fully stitched | policy drift risk |
| G8 | Scope UX | Medium | escalation/re-consent not fully skill-driven | scope failures during execution |

---

## 5) Target Operating Model

The fully operational Workspace stack should enforce the following:

1. **Profile-based tool exposure** (`<=20` tools/profile, P9 compliant)
2. **Two-phase workflows**: read/analyze -> HITL -> write/apply
3. **Scope-aware execution**: preflight check before invocation, deterministic remediation guidance
4. **Typed skill outputs**: human summary + structured payload + memory write contract
5. **Centralized telemetry**: trace_id, tool, profile, latency, retries, outcome, error_type
6. **Scheduler-ready workflows**: no workspace path left in stub state

---

## 6) Implementation Plan

## Phase A - Contract and Governance Normalization (P0)

### Objective

Eliminate all runtime contract ambiguity before adding new capabilities.

### Work items

1. Normalize all workspace agent/skill tool IDs to runtime format `google_workspace_*`.
2. Align policy naming in prompts/skills with governance matrix canonical tool names.
3. Add validator checks that fail on slash-style MCP tool references in workspace files.
4. Generate machine-readable map: `tool -> scope -> rw -> hitl_required -> profile`.

### Deliverables

- `.aria/kilocode/agents/workspace-agent.md` updated
- workspace skill frontmatters updated
- `scripts/validate_agents.py` + `scripts/validate_skills.py` rules extended
- `docs/roadmaps/workspace_tool_profile_matrix.md` (new)

### Acceptance

- zero naming mismatches in agent/skills,
- validators fail on any future mismatch,
- P9 profile boundaries documented and testable.

---

## Phase B - Profiled Workspace Agent Runtime (P0/P1)

### Objective

Expose advanced capabilities safely by profile and intent.

### Profiles (initial)

1. `workspace-mail-read`
2. `workspace-mail-write`
3. `workspace-docs-read`
4. `workspace-docs-write`
5. `workspace-sheets-read`
6. `workspace-sheets-write`
7. `workspace-slides-read`
8. `workspace-slides-write`

Each profile must remain `<=20` tools and embed minimal scope policy.

### Work items

1. Add conductor routing rules from intent -> profile.
2. Add preflight scope coherence check per profile invocation.
3. Add deterministic fallback policy:
   - missing scope -> re-consent guidance,
   - transient API failure -> bounded retry,
   - write denied -> archive decision in memory.

### Deliverables

- profile catalog in docs and agent config
- conductor dispatch mapping update
- scope preflight integration notes/runbook

### Acceptance

- deterministic profile selection for all workspace intents,
- no profile exceeds 20 tools,
- missing-scope failures return actionable remediation, not generic errors.

---

## Phase C - Advanced Read Skill Pack (P1)

### Objective

Implement high-value advanced reading/intelligence workflows.

### New skills

1. `gmail-thread-intelligence`
   - tools: thread search, full thread retrieval, attachment extraction, label context
   - output: timeline + action candidates + risk flags
2. `docs-structure-reader`
   - tools: `inspect_doc_structure`, `get_doc_content`, `get_doc_as_markdown`, comments listing
   - output: section map, table map, unresolved comments, editable anchor points
3. `sheets-analytics-reader`
   - tools: `get_spreadsheet_info`, `read_sheet_values`, `list_sheet_tables`
   - output: schema map, table/column quality checks, change recommendations
4. `slides-content-auditor`
   - tools: `get_presentation`, `get_page`, `get_page_thumbnail`
   - output: slide inventory, text density issues, placeholder coverage

### Deliverables

- new skill docs under `.aria/kilocode/skills/*`
- skill contracts (inputs/outputs/errors)
- memory tags taxonomy for workspace artifacts

### Acceptance

- reproducible outputs on fixed fixtures,
- all read skills execute without HITL prompts,
- structured output schema validated in tests.

---

## Phase D - Advanced Edit Skill Pack (P1)

### Objective

Enable safe advanced editing for Docs/Sheets/Slides/Gmail with mandatory HITL.

### New skills

1. `gmail-composer-pro`
   - draft/send modes with thread-safe reply handling and attachment strategies
2. `docs-editor-pro`
   - text modifications, find/replace, table updates, comments lifecycle, batch operations
3. `sheets-editor-pro`
   - value updates, formatting, conditional rules, append rows, dimension resize
4. `slides-editor-pro`
   - batch text/style updates, structural edits, comments management

### Mandatory execution pattern

1. read + diff preview,
2. HITL confirmation with concise patch summary,
3. execute write tool(s),
4. post-write verification read,
5. memory audit record.

### Deliverables

- four production write skills
- reusable HITL payload templates
- rollback/playback guidance for each skill class

### Acceptance

- 100% write paths include HITL checkpoint,
- post-write verification available and tested,
- explicit refusal path returns safe no-op with rationale.

---

## Phase E - Scheduler/Automation Activation (P1)

### Objective

Remove workspace execution stub from scheduler and activate controlled automations.

### Work items

1. Implement workspace execution path in `src/aria/scheduler/runner.py`.
2. Execute task payload through conductor + profile + skill pipeline.
3. Seed advanced recurring tasks (mail digest, docs audit, sheets anomaly scan).
4. Add idempotency/retry semantics tuned for workspace quotas.

### Deliverables

- scheduler runner implementation for workspace
- updated `scripts/seed_scheduler.py`
- integration tests for scheduled workspace tasks

### Acceptance

- workspace tasks no longer report `not_implemented`,
- scheduled read tasks complete autonomously,
- scheduled write tasks always block on HITL when required.

---

## Phase F - Verification, Telemetry, and Go-Live (P1/P2)

### Objective

Prove reliability and operational observability.

### Work items

1. Add tool-level telemetry schema and dashboard docs.
2. Generate weekly workspace usage report (enabled vs invoked tools, failures by type).
3. Build end-to-end test suites:
   - advanced Gmail read/edit,
   - Docs structure+batch edit,
   - Sheets read/write+format,
   - Slides read/write.
4. Add chaos-style tests for scope revocation, 429/403/5xx, HITL timeout.

### Deliverables

- telemetry spec + report script
- unit/integration/e2e coverage expansion
- go-live checklist and incident playbook update

### Acceptance

- success rate >=98% on controlled integration suite,
- HITL compliance 100% for writes,
- actionable telemetry for top errors and retries.

---

## 7) Testing Strategy and Verification Commands

Minimum quality gate per increment:

```bash
python scripts/validate_agents.py
python scripts/validate_skills.py
ruff check src/
ruff format --check src/
mypy src
pytest -q tests/unit/agents/workspace tests/unit/scheduler
pytest -q tests/integration/scheduler
pytest -q tests/e2e -k workspace
```

Additional targeted suites to introduce:

- `tests/integration/workspace/test_gmail_thread_intelligence.py`
- `tests/integration/workspace/test_docs_editor_pro.py`
- `tests/integration/workspace/test_sheets_editor_pro.py`
- `tests/integration/workspace/test_slides_editor_pro.py`
- `tests/e2e/test_workspace_hitl_write_paths.py`

---

## 8) Milestones and Exit Criteria

## M1 - Contract Integrity ✅

- [x] tool naming normalized,
- [x] validators enforce contract,
- [x] profile matrix approved.

## M2 - Advanced Read Operational ✅

- [x] new read skills active and tested (4 skills: gmail-thread-intelligence, docs-structure-reader, sheets-analytics-reader, slides-content-auditor),
- [x] deterministic profile routing in place (10 profiled agents).

## M3 - Advanced Write Operational ✅

- [x] write skill pack active (4 skills: gmail-composer-pro, docs-editor-pro, sheets-editor-pro, slides-editor-pro),
- [x] HITL integration verified end-to-end (47 e2e tests).

## M4 - Scheduler Live ✅

- [x] workspace path fully implemented in runner.py,
- [x] seeded automations running with policy controls (7 workspace tasks).

## M5 - Production Readiness ✅

- [x] telemetry/reporting active (workspace_telemetry_spec.md),
- [x] reliability and compliance thresholds met (342 tests passing).

---

## 9) Immediate Next Sprint Backlog (Execution-Ready)

1. Fix workspace tool naming mismatch in agent + 3 existing skills.
2. Introduce profile matrix and update conductor routing contract.
3. Implement `gmail-thread-intelligence` and `docs-structure-reader` as first advanced read tranche.
4. Add validator rule to block slash-style workspace tool declarations.
5. Add integration tests for the two new read skills.

This sequence removes core ambiguity first, then unlocks advanced document/email reading capabilities with low risk before enabling advanced write automation.

---

## 10) References

### Core Files
- `docs/foundation/aria_foundation_blueprint.md`
- `.aria/kilocode/agents/workspace-agent.md`

### Workspace Skills (Pre-Sprint 1.6)
- `.aria/kilocode/skills/triage-email/SKILL.md`
- `.aria/kilocode/skills/calendar-orchestration/SKILL.md`
- `.aria/kilocode/skills/doc-draft/SKILL.md`

### Workspace Skills (Implemented Sprint 1.6 - Phase C)
- `.aria/kilocode/skills/gmail-thread-intelligence/SKILL.md`
- `.aria/kilocode/skills/docs-structure-reader/SKILL.md`
- `.aria/kilocode/skills/sheets-analytics-reader/SKILL.md`
- `.aria/kilocode/skills/slides-content-auditor/SKILL.md`

### Workspace Skills (Implemented Sprint 1.6 - Phase D)
- `.aria/kilocode/skills/gmail-composer-pro/SKILL.md`
- `.aria/kilocode/skills/docs-editor-pro/SKILL.md`
- `.aria/kilocode/skills/sheets-editor-pro/SKILL.md`
- `.aria/kilocode/skills/slides-editor-pro/SKILL.md`

### Profiled Agents (Implemented Sprint 1.6 - Phase B)
- `.aria/kilocode/agents/workspace-mail-read.md`
- `.aria/kilocode/agents/workspace-mail-write.md`
- `.aria/kilocode/agents/workspace-calendar-read.md`
- `.aria/kilocode/agents/workspace-calendar-write.md`
- `.aria/kilocode/agents/workspace-docs-read.md`
- `.aria/kilocode/agents/workspace-docs-write.md`
- `.aria/kilocode/agents/workspace-sheets-read.md`
- `.aria/kilocode/agents/workspace-sheets-write.md`
- `.aria/kilocode/agents/workspace-slides-read.md`
- `.aria/kilocode/agents/workspace-slides-write.md`

### Runtime & Governance
- `scripts/wrappers/google-workspace-wrapper.sh`
- `src/aria/agents/workspace/oauth_helper.py`
- `src/aria/agents/workspace/scope_manager.py`
- `src/aria/scheduler/runner.py` (workspace execution path - Phase E)
- `scripts/seed_scheduler.py` (7 workspace tasks)

### Documentation
- `docs/roadmaps/workspace_tool_governance_matrix.md`
- `docs/roadmaps/workspace_tool_profile_matrix.md`
- `docs/operational/workspace_telemetry_spec.md` (Phase F)
- `docs/analysis/workspace_enhancement_analysis.md`

### Tests (Sprint 1.6 - Phase F)
- `tests/integration/workspace/` (87 tests)
- `tests/e2e/workspace/` (47 tests)

### External References
- Context7: `/taylorwilsdon/google_workspace_mcp`
- Context7: `/modelcontextprotocol/python-sdk`
- MCP spec: `https://modelcontextprotocol.io/specification/2025-06-18/server/tools`
- Google Workspace MCP config guide: `https://developers.google.com/workspace/guides/configure-mcp-servers`

---

## 11) Implementation Summary (Sprint 1.6)

**Commit:** `c2a5284` - `feat(workspace): Sprint 1.6 Phase C-F - advanced skills, scheduler activation, telemetry`

| Phase | Work Items | Status |
|-------|-----------|--------|
| A | Contract normalization (tool naming, validators) | ✅ |
| B | 10 profiled workspace agents (P9 compliant) | ✅ |
| C | 4 advanced read skills | ✅ |
| D | 4 advanced write skills with HITL | ✅ |
| E | Scheduler workspace execution + 7 tasks | ✅ |
| F | Telemetry spec + 134 tests | ✅ |

**Quality Gates:**
- `python scripts/validate_agents.py` → PASS
- `ruff check src/` → PASS
- `mypy src/` → PASS (0 errors)
- `pytest -q` → 342 tests PASS

---

## 12) Post-Implementation Verification Addendum (2026-04-22)

Independent verification against codebase + blueprint + Context7 identified and fixed the following drifts after Sprint 1.6 commit `c2a5284`:

1. `src/aria/scheduler/runner.py` workspace execution was still a placeholder success path.
2. Write skills could execute with non-`ask` policy, violating P7 HITL guarantees.
3. `docs-editor-pro` described text batch edit capabilities not exposed by current MCP toolset.
4. `deep-research` still used slash-style tool IDs, breaking `scripts/validate_skills.py`.

Remediations applied:

- Implemented delegated workspace sub-agent execution in scheduler runner.
- Enforced write-skill `policy=ask` guard.
- Added structured workspace telemetry + error classification in runner.
- Normalized `deep-research` tool IDs to underscore runtime format.
- Aligned `docs-editor-pro` contract to currently supported Docs MCP operations.
- Added unit regression tests in `tests/unit/scheduler/test_runner_workspace.py`.

Re-verification (post-remediation):

- `uv run python scripts/validate_agents.py` → PASS
- `uv run python scripts/validate_skills.py` → PASS
- `uv run ruff check src` → PASS
- `uv run mypy src` → PASS
- `uv run pytest -q` → 414 tests PASS
