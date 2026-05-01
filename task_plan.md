# Task Plan: Debug real REPL search-agent sessions

## Goal
Analyze the real `bin/aria repl` cinema-session failures and implement the minimum set of fixes needed to make the research flow reliable, grounded, and session-consistent.

## Scope
Focus on defects evidenced by the attached session transcript and Kilo logs for 2026-05-01.

## Verified Problem Areas
1. **Grounding drift / over-synthesis**
   - Search answers are prompt-driven with no runtime evidence check.
   - The conductor and search-agent can overstate findings instead of explicitly reporting uncertainty.
2. **Broken follow-up continuity**
   - `ConductorBridge` creates a fresh child Kilo session every turn.
   - Follow-up turns like `continua` are not guaranteed to resume prior grounded context.
3. **Irrelevant backend startup noise**
   - Search flows still trigger unrelated proxy backends, including `google_workspace`.
   - Logs show repeated MCP stdio parse failures and OAuth port-8000 conflicts during search-only work.
4. **Weak coordination enforcement**
   - `YamlCapabilityRegistry.validate_delegation()` currently returns true if either agent exists, instead of checking an allowed edge.

## Evidence
- Transcript session: `ses_21d455d0dffeeWTujS4HWQVNJv`
- Search subagent session in logs: `ses_21d25c813ffe5QGLVPfITbeU8c`
- Log file: `.aria/kilo-home/.local/share/kilo/log/2026-05-01T091326.log`

## Phases

### Phase 1: Forensic analysis
- [x] Read `AGENTS.md`
- [x] Read LLM wiki index/log first
- [x] Inspect session transcript and Kilo logs
- [x] Inspect active prompts, proxy wiring, and gateway bridge
- [x] Verify FastMCP behavior with Context7

### Phase 2: Requirements / debug PRD
- [ ] Freeze concrete defects to fix
- [ ] Define acceptance criteria for search grounding, continuity, and backend isolation

### Phase 3: Technical design
- [ ] Design stable child-session reuse for gateway turns
- [ ] Design caller-aware backend filtering for proxy startup
- [ ] Design minimal grounding hardening for conductor/search-agent prompts
- [ ] Design fix for delegation edge validation

### Phase 4: Implementation
- [ ] Update gateway bridge code + tests
- [ ] Update proxy server code + tests
- [ ] Update coordination registry + tests
- [ ] Update agent prompt files

### Phase 5: Verification
- [x] Run targeted pytest for modified areas
- [x] Run `ruff check` on modified files
- [ ] Run `ruff check .`
- [ ] Run `ruff format --check .`
- [ ] Run `mypy src`
- [ ] Run broader pytest subset or full suite if practical

### Phase 6: Pre-existing repo failures remediation
- [x] Diagnose repo-wide `ruff check .` failures
- [x] Diagnose repo-wide `mypy src` failures
- [x] Diagnose repo-wide `pytest -q` collection/runtime failures
- [x] Implement minimal fixes for pre-existing failures without unrelated refactors
- [x] Re-run full quality gates

### Phase 7: Wiki + state maintenance
- [ ] Update `docs/llm_wiki/wiki/mcp-proxy.md`
- [x] Update `docs/llm_wiki/wiki/index.md`
- [x] Append timestamped entry to `docs/llm_wiki/wiki/log.md`
- [x] Update `.workflow/state.md`
- [x] Update `findings.md` and `progress.md`

## Constraints
- Follow `AGENTS.md` strictly.
- Keep fixes minimal and reviewable.
- Do not over-engineer a full coordinator rewrite.
- Use Context7-verified FastMCP behavior as source of truth before code changes.
