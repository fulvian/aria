# Task Plan: trader-agent forensic debug → remediation

## Goal
Diagnose and remediate the trader-agent regression cluster reported on 2026-05-02:
- missing/unclear original implementation plan provenance;
- routing drift causing finance requests to miss trader-agent;
- MCP proxy/tool-surface regressions preventing financial backends from being used reliably;
- source-of-truth drift between wiki, active prompts, generated prompts, and tests.

## Status: 🔄 FORENSIC ANALYSIS IN PROGRESS

## Phases

### Phase 1: Wiki-first reconstruction
- [x] Read `AGENTS.md`
- [x] Read `docs/llm_wiki/wiki/index.md`
- [x] Read `docs/llm_wiki/wiki/log.md`
- [x] Read `docs/llm_wiki/wiki/trader-agent.md`
- [x] Read `docs/llm_wiki/wiki/mcp-proxy.md`
- [x] Read `docs/llm_wiki/wiki/agent-capability-matrix.md`
- [x] Read `docs/protocols/protocollo_creazione_agenti.md`

### Phase 2: Forensic diagnosis / PRD
- [x] Recover branch and commit lineage for trader-agent
- [x] Verify whether the original trader plan exists in the working tree or git history
- [x] Inspect active conductor/trader prompts, proxy config, and trader skills
- [x] Verify FastMCP middleware/search behavior with Context7
- [x] Run targeted tests to validate suspected runtime/source-of-truth drift
- [ ] Freeze final defect inventory and remediation scope

### Phase 3: Technical design
- [ ] Define canonical conductor source-of-truth regeneration model
- [ ] Define trader-agent prompt/skill contract corrections
- [ ] Define capability-matrix / boot-filter fix for finance backends
- [ ] Define missing-plan recovery and wiki provenance corrections

### Phase 4: Implementation
- [ ] Apply selected fixes
- [ ] Add/extend regression tests
- [ ] Update wiki + state + provenance docs

### Phase 5: Verification
- [ ] Run targeted regression tests
- [ ] Run `ruff check .`
- [ ] Run `mypy src`
- [ ] Run `pytest -q` or constrained subset if full suite is noisy

## Constraints
- Follow `AGENTS.md` strictly.
- Use wiki-first and Context7-first workflow.
- Do not perform destructive git recovery without explicit approval.
- Keep fixes minimal and aligned with the proxy architecture and trader-agent protocol.

## Current suspected root causes
- Generated conductor prompt drift: `.aria/kilocode/agents/aria-conductor.md` has been overwritten from a stale Kilo-home template missing trader-agent and prior hardening.
- Trader-agent docs/wiki point to `docs/plans/agents/trader_agent_foundation_plan.md`, but no such file exists in the worktree or recovered trader commit.
- Trader-agent prompt/skills still contain invalid proxy examples (`call_tool("search_tools", ...)`) and legacy slash-form backend names.
- Trader-agent prompt/skills reference disabled HTTP finance backends (`financial-modeling-prep-mcp`, `helium-mcp`) as if they were primary live paths.
- Capability boot filtering by `ARIA_CALLER_ID` would load zero finance backends for `trader-agent` because its matrix entry contains only synthetic proxy tools, not backend wildcard reach.
- HITL tool naming is inconsistent (`hitl-queue__ask` in prompts/tests vs live `aria-memory__hitl_*` tool surface in this environment).
