# Sprint 1.6 — Google Workspace Agent Full Operational

## Phase 1, Sprint 1.6: Workspace Agent Operationalization

**Started:** 2026-04-22
**Status:** in_progress
**Owner:** General Manager (Orchestrator)
**Blueprint:** docs/foundation/aria_foundation_blueprint.md
**Plan:** docs/plans/google_workspace_agent_full_operational_plan.md

---

## Goal

Close all workspace agent gaps (G1-G8) and achieve full operational readiness across Gmail, Calendar, Drive, Docs, Sheets, Slides with deterministic tool binding, advanced skill coverage, scheduler activation, and HITL compliance.

---

## Context7 Verified References

| Library | ID | Purpose |
|---------|-----|---------|
| Google Workspace MCP | `/taylorwilsdon/google_workspace_mcp` | Gmail, Calendar, Drive, Docs, Sheets, Slides, Forms, Chat tools |
| MCP Python SDK | `/modelcontextprotocol/python-sdk` | HITL elicitation, error handling, task support |

**Verified Tool Naming Convention** (from Context7):
- Runtime MCP tool names: `google_workspace_search_gmail_messages`, `google_workspace_get_gmail_message_content`, etc.
- Skill/Agent declarations must use underscore prefix + underscore naming

---

## Critical Gaps Analysis

| ID | Gap | Severity | Plan Phase |
|----|-----|----------|------------|
| G1 | Tool naming mismatch (slash vs underscore) | Critical | Phase A |
| G2 | Only 3 skills for 114 tools | Critical | Phase C |
| G3 | No advanced Docs/Sheets/Slides workflows | Critical | Phase C+D |
| G4 | Scheduler workspace path stubbed | High | Phase E |
| G5 | No e2e contracts for advanced workflows | High | Phase F |
| G6 | No per-tool telemetry | High | Phase F |
| G7 | Governance matrix not fully stitched | Medium | Phase B |
| G8 | Scope re-consent not skill-driven | Medium | Phase B |

---

## WBS (Work Breakdown Structure)

### Phase A — Contract and Governance Normalization (P0) ✅

#### W1.6.A1 — Fix workspace-agent.md tool naming ✅
- [x] Change slash-style (`google_workspace/search_gmail_messages`) to underscore prefix format (`google_workspace_search_gmail_messages`)
- [x] Verify all tool names match runtime MCP tool IDs from Context7
- [x] Fix `aria-memory/*` to proper format with specific tools
- **Files**: `.aria/kilocode/agents/workspace-agent.md`

#### W1.6.A2 — Fix triage-email skill tool naming ✅
- [x] Update allowed-tools to underscore prefix format
- [x] Fix `aria-memory/hitl_ask` → `aria_memory_hitl_ask`
- **Files**: `.aria/kilocode/skills/triage-email/SKILL.md`

#### W1.6.A3 — Fix calendar-orchestration skill tool naming ✅
- [x] Update allowed-tools to underscore prefix format
- [x] Fix `aria-memory/hitl_ask` → `aria_memory_hitl_ask`
- [x] Add event lifecycle tools (get_event, modify_event)
- **Files**: `.aria/kilocode/skills/calendar-orchestration/SKILL.md`

#### W1.6.A4 — Fix doc-draft skill tool naming ✅
- [x] Update allowed-tools to underscore prefix format
- [x] Fix `aria-memory/hitl_ask` → `aria_memory_hitl_ask`
- [x] Add list_docs_in_folder for folder browsing
- **Files**: `.aria/kilocode/skills/doc-draft/SKILL.md`

#### W1.6.A5 — Create validator rule for tool naming ✅
- [x] Add rule to `scripts/validate_agents.py` to block slash-style MCP tool references
- [x] Add rule to `scripts/validate_skills.py` to block slash-style tool references
- [x] Added `_is_slash_style_mcp_tool()`, `_server_exists()`, progressive prefix matching
- **Files**: `scripts/validate_agents.py`, `scripts/validate_skills.py`

#### W1.6.A6 — Create workspace tool profile matrix ✅
- [x] Document tool -> scope -> rw -> hitl_required -> profile mapping
- [x] Profile catalog for 12 profiles (8 core + 4 future expansion)
- [x] All profiles verified <= 20 tools (P9 compliant)
- **Files**: `docs/roadmaps/workspace_tool_profile_matrix.md`

### Phase B — Profiled Workspace Agent Runtime (P0/P1) ✅

#### W1.6.B1 — Create 8 profiled workspace agent files ✅
- [x] Created `workspace-mail-read.md` agent (4 tools)
- [x] Created `workspace-mail-write.md` agent (5 tools)
- [x] Created `workspace-calendar-read.md` agent (5 tools)
- [x] Created `workspace-calendar-write.md` agent (6 tools)
- [x] Created `workspace-docs-read.md` agent (6 tools)
- [x] Created `workspace-docs-write.md` agent (7 tools)
- [x] Created `workspace-sheets-read.md` agent (6 tools)
- [x] Created `workspace-sheets-write.md` agent (9 tools)
- **Files**: `.aria/kilocode/agents/workspace-*-*.md`

#### W1.6.B2 — Reduced workspace-agent to P9 compliant ✅
- [x] Reduced from 24 to 17 tools (<=20 P9 compliant)
- [x] Added reference to profiled variants in body text
- **Files**: `.aria/kilocode/agents/workspace-agent.md`

#### W1.6.B3 — Deterministic fallback policy ✅
- [x] Missing scope -> re-consent guidance
- [x] Transient API failure -> bounded retry
- [x] Write denied -> archive decision in memory
- **Files**: workspace skill error handlers

---

### Phase C — Advanced Read Skill Pack (P1) ✅

#### W1.6.C1 — gmail-thread-intelligence skill ✅
- [x] Tools: thread search, full thread retrieval, attachment extraction, label context
- [x] Output: timeline + action candidates + risk flags
- [x] Context7 verified tool names
- **Files**: `.aria/kilocode/skills/gmail-thread-intelligence/SKILL.md`

#### W1.6.C2 — docs-structure-reader skill ✅
- [x] Tools: search_docs, get_doc_content, list_docs_in_folder, read_doc_comments
- [x] Output: section map, table map, unresolved comments, editable anchor points
- [x] Context7 verified tool names
- **Files**: `.aria/kilocode/skills/docs-structure-reader/SKILL.md`

#### W1.6.C3 — sheets-analytics-reader skill ✅
- [x] Tools: list_spreadsheets, get_spreadsheet_info, read_sheet_values, read_sheet_comments
- [x] Output: schema map, table/column quality checks, change recommendations
- [x] Context7 verified tool names
- **Files**: `.aria/kilocode/skills/sheets-analytics-reader/SKILL.md`

#### W1.6.C4 — slides-content-auditor skill ✅
- [x] Tools: get_presentation, get_page, get_page_thumbnail, read_presentation_comments
- [x] Output: slide inventory, text density issues, placeholder coverage
- [x] Context7 verified tool names
- **Files**: `.aria/kilocode/skills/slides-content-auditor/SKILL.md`

---

### Phase D — Advanced Edit Skill Pack (P1) ✅

#### W1.6.D1 — gmail-composer-pro skill ✅
- [x] draft/send modes with thread-safe reply handling and attachment strategies
- [x] HITL mandatory before send (aria_memory_hitl_ask)
- [x] Thread headers preservation (References, In-Reply-To)
- [x] Post-write verification
- **Files**: `.aria/kilocode/skills/gmail-composer-pro/SKILL.md`

#### W1.6.D2 — docs-editor-pro skill ✅
- [x] Text modifications, find/replace, table updates, comments lifecycle, batch operations
- [x] HITL mandatory before write
- [x] Diff preview before HITL
- [x] Post-write verification
- **Files**: `.aria/kilocode/skills/docs-editor-pro/SKILL.md`

#### W1.6.D3 — sheets-editor-pro skill ✅
- [x] Value updates, formatting, conditional rules, append rows, dimension resize
- [x] HITL mandatory before write
- [x] Pre-edit read required
- [x] Post-write verification
- **Files**: `.aria/kilocode/skills/sheets-editor-pro/SKILL.md`

#### W1.6.D4 — slides-editor-pro skill ✅
- [x] Batch text/style updates, structural edits, comments management
- [x] HITL mandatory before batch_update
- [x] Atomic batch operations
- [x] Post-write verification
- **Files**: `.aria/kilocode/skills/slides-editor-pro/SKILL.md`

---

### Phase E — Scheduler/Automation Activation (P1) ✅

#### W1.6.E1 — Implement workspace execution path ✅
- [x] Removed `not_implemented` stub in runner.py for workspace category
- [x] Execute task payload through skill metadata mapping
- [x] Write skills properly trace HITL approval status
- **Files**: `src/aria/scheduler/runner.py`

#### W1.6.E2 — Seed advanced recurring tasks ✅
- [x] Added 5 new workspace tasks (read: thread-intel, docs-audit, sheets-analytics, slides-audit)
- [x] Added 2 write tasks with ask policy (docs-editor, sheets-editor) for HITL
- [x] Proper skill metadata mapping for all workspace skills
- **Files**: `scripts/seed_scheduler.py`

#### W1.6.E3 — Idempotency/retry semantics ✅
- [x] Skill metadata includes retry guidance (max_retries per task)
- [x] Write tasks with ask policy allow retry after human approval
- [x] Fallback to unknown skill metadata (assumes write/safer)
- **Files**: `src/aria/scheduler/runner.py`

#### W1.6.E4 — Create workspace-slides profiles ✅
- [x] Created `workspace-slides-read.md` (4 tools, P9 compliant)
- [x] Created `workspace-slides-write.md` (9 tools, P9 compliant)
- **Files**: `.aria/kilocode/agents/workspace-slides-read.md`, `workspace-slides-write.md`

---

### Phase F — Verification, Telemetry, and Go-Live (P1/P2) ✅

#### W1.6.F1 — Tool-level telemetry schema ✅
- [x] Define trace_id, tool, profile, latency, retries, outcome, error_type
- [x] Dashboard docs reference
- [x] Error type classification (auth, quota, network, tool_error)
- [x] Recovery patterns documented
- **Files**: `docs/operational/workspace_telemetry_spec.md`

#### W1.6.F2 — End-to-end test suites ✅
- [x] Advanced Gmail read/edit (gmail-thread-intelligence, gmail-composer-pro)
- [x] Docs structure+batch edit (docs-structure-reader, docs-editor-pro)
- [x] Sheets read/write+format (sheets-analytics-reader, sheets-editor-pro)
- [x] Slides read/write (slides-content-auditor, slides-editor-pro)
- [x] HITL timeout tests (chaos scenarios)
- [x] 87 integration tests in `tests/integration/workspace/`
- [x] 47 e2e tests in `tests/e2e/workspace/`
- **Files**: `tests/integration/workspace/`, `tests/e2e/workspace/`

---

## Implementation Order

1. **Phase A** (W1.6.A1-A6): Contract normalization — MUST complete first
2. **Phase B** (W1.6.B1-B2): Profile routing — depends on A6
3. **Phase C** (W1.6.C1-C4): Advanced read skills — depends on A, B
4. **Phase D** (W1.6.D1-D4): Advanced write skills — depends on C
5. **Phase E** (W1.6.E1-E3): Scheduler activation — depends on A, B
6. **Phase F** (W1.6.F1-F2): Verification/telemetry — depends on all

---

## Quality Gates

```bash
# Must pass before each phase transition
python scripts/validate_agents.py
python scripts/validate_skills.py
ruff check src/
ruff format --check src/
mypy src
pytest -q tests/unit/agents/workspace tests/unit/scheduler
pytest -q tests/integration/scheduler
pytest -q tests/e2e -k workspace
```

---

## Exit Criteria

- [x] Zero naming mismatches in agent/skills (slash-style eliminated)
- [x] Validators fail on any future mismatch
- [x] 10 profiles documented and <= 20 tools each (added workspace-slides-read/write)
- [x] gmail-thread-intelligence and docs-structure-reader operational
- [x] Scheduler workspace path no longer reports not_implemented
- [x] All write skills include HITL checkpoint
- [x] Quality gates green
- [x] Telemetry spec documented
- [x] Integration tests (87) and E2E tests (47) passing

---

## Dependencies

- Context7 `/taylorwilsdon/google_workspace_mcp` — verified tool list
- Context7 `/modelcontextprotocol/python-sdk` — HITL patterns
- MCP spec: tool naming conventions
- Google Workspace MCP security guidance

---

## Notes

- Phase A is P0 — no code is written until contract normalization is complete
- Per P9, each profile must remain <= 20 tools
- Per P7, all write operations require HITL confirmation
- All new skills must follow output schema: human summary + structured payload + memory tags
- Sprint 1.5 remains pending operator input for W1.5.D, W1.5.E, W1.5.F
