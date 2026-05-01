# Findings — MCP Proxy Integration Audit (2026-05-01)

## Wiki-first context
- Read first: `docs/llm_wiki/wiki/index.md`, `docs/llm_wiki/wiki/log.md`, `docs/llm_wiki/wiki/mcp-proxy.md`
- Relevant source documents:
  - `docs/plans/mcp_search_tool_plan_1.md`
  - `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`
  - `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`

## Files inspected

### Runtime / config
- `.aria/kilocode/mcp.json`
- `.aria/config/agent_capability_matrix.yaml`
- `.aria/config/mcp_catalog.yaml`
- `src/aria/mcp/proxy/server.py`
- `src/aria/mcp/proxy/middleware.py`
- `src/aria/agents/coordination/registry.py`
- `src/aria/gateway/conductor_bridge.py`

### Agent prompts
- `.aria/kilocode/agents/aria-conductor.md`
- `.aria/kilocode/agents/search-agent.md`
- `.aria/kilocode/agents/workspace-agent.md`
- `.aria/kilocode/agents/productivity-agent.md`

### Skills
- `.aria/kilocode/skills/deep-research/SKILL.md`
- `.aria/kilocode/skills/office-ingest/SKILL.md`
- `.aria/kilocode/skills/meeting-prep/SKILL.md`
- `.aria/kilocode/skills/email-draft/SKILL.md`
- skills inventory under `.aria/kilocode/skills/`

## Context7 verification
- Library resolved: `/prefecthq/fastmcp`
- Verified behavior:
  - search transforms expose synthetic `search_tools` and `call_tool`
  - middleware hooks can intercept `on_list_tools` / `on_call_tool`
  - FastMCP does not solve ARIA-side caller identity propagation or factual grounding

## Main findings

### 1) Plan/spec drift: prompts do not follow the F3 canonical tool contract
- `docs/plans/mcp_search_tool_plan_1.md` F3.3 explicitly says agent frontmatter should expose only:
  - `aria-mcp-proxy__search_tools`
  - `aria-mcp-proxy__call_tool`
  - memory tools as needed
- Current prompts instead expose backend wildcards directly:
  - `search-agent.md`: `searxng-script__*`, `tavily-mcp__*`, `exa-script__*`, etc.
  - `workspace-agent.md`: `google_workspace__*`
  - `productivity-agent.md`: `markitdown-mcp__*`, `filesystem__*`, etc.
- This is inconsistent with the proxy cutover design and weakens the “single MCP surface” abstraction.

### 2) Caller-aware backend boot filtering is implemented but not actually wired
- `src/aria/mcp/proxy/server.py` filters booted backends only when `ARIA_CALLER_ID` is present.
- `.aria/kilocode/mcp.json` does not set `ARIA_CALLER_ID` for the proxy process.
- `src/aria/gateway/conductor_bridge.py` does not inject `ARIA_CALLER_ID` when launching Kilo.
- No code path inspected sets `X-ARIA-Caller-Id` either.
- Result: the proxy likely boots the full enabled backend catalog in real sessions, contrary to the intended per-agent isolation.

### 3) Middleware is still fail-open when caller identity is absent
- `CapabilityMatrixMiddleware.on_list_tools()` returns all tools if caller resolution fails.
- `on_call_tool()` denies only when a caller is present; otherwise the call proceeds.
- The design/spec describe caller anomaly tracking, but current implementation does not fail closed and does not appear to emit the documented metric/event hooks from middleware.

### 4) `search_tools` discovery can still leak unrelated backend tools
- Synthetic tools are always visible, which is expected.
- But if caller-aware backend boot filtering is inactive, `search_tools` can search across all booted backends.
- That reintroduces the exact cross-agent noise/problem the proxy F7 fix was meant to solve.

### 5) Skills are not harmonized with the proxy invocation model
- `deep-research` still documents direct provider usage and contains no proxy `_caller_id` guidance.
- `meeting-prep` and `email-draft` still use dotted pseudo-calls like `calendar.list_events`, `gmail.search`, `gmail.get_thread`, `gmail.draft_create` instead of real proxy/backend invocation patterns.
- `office-ingest` still documents direct `markitdown-mcp__convert_to_markdown` use.
- This means agent prompts mention `_caller_id`, but skills still train agents toward non-canonical tool usage.

### 6) `deep-research` frontmatter is internally inconsistent
- It omits `scientific-papers-mcp__*` from `allowed-tools`.
- The body still requires `scientific-papers-mcp__search_papers` for academic tier 2.

### 7) Naming drift remains in prompt body examples
- `search-agent.md` still contains slash-form examples such as:
  - `scientific-papers-mcp/search_papers`
  - `scientific-papers-mcp/fetch_top_cited`
- The current proxy/matrix compatibility layer accepts multiple forms, but the prompt examples are still stale relative to the intended post-cutover convention.

### 8) Conductor prompt has unresolved tool/policy drift
- `aria-conductor.md` declares `aria-mcp-proxy` as an MCP dependency but does not expose or explain a canonical proxy usage path for the conductor.
- It instructs HITL through `hitl-queue/ask`, while the actual allowed tools/matrix entries use memory-backed HITL tools (`aria-memory__hitl_*`) and not `hitl-queue__ask` for the conductor.
- There are also live uncommitted modifications in:
  - `.aria/kilocode/agents/aria-conductor.md`
  - `.aria/kilo-home/.kilo/agents/aria-conductor.md`

### 9) Required skills inventory is incomplete vs prompt declarations
- Missing from `.aria/kilocode/skills/`:
  - `source-dedup`
  - `calendar-orchestration`
  - `doc-draft`
- Yet they are still declared in prompt frontmatter:
  - `search-agent.md` requires `source-dedup`
  - `workspace-agent.md` requires `calendar-orchestration`, `doc-draft`
- This is a concrete integration gap, not just wording drift.

### 10) Observability contract appears only partially implemented
- Docs/spec mention `aria_proxy_caller_missing_total` anomaly counting and `proxy.caller_anomaly` events.
- Metrics/events constants exist, but the inspected middleware currently only logs `proxy.tool_denied`; it does not appear to increment caller-missing metrics or emit caller-anomaly events in the missing-caller path.

## High-priority fix buckets
1. **Runtime enforcement**
   - propagate caller identity end-to-end
   - decide whether the proxy must fail closed without caller identity
2. **Canonical invocation model**
   - align prompts/matrix/tests on either synthetic proxy tools only or explicitly justified direct backend exposure
3. **Skill normalization**
   - rewrite stale dotted/slash/direct-backend instructions
   - add `_caller_id` guidance where proxy calls are expected
4. **Inventory integrity**
   - restore or remove missing required skills
5. **Docs vs runtime reconciliation**
   - update wiki/spec/ADR only after the runtime contract is made true again

## Architectural boundary research — new direction under evaluation

### Local blueprint tension
- Blueprint P9 currently encodes tool scoping as near-exclusive per sub-agent and caps sub-agent MCP tools at 20.
- Blueprint §8.3 / §8.5 and ADR-0008 intentionally separated `workspace-agent` and `productivity-agent` mainly to avoid overlap and tool-count blow-up.
- With the MCP proxy and policy layer, the original assumption “tool exclusivity = safest architecture” is now under pressure.

### External best-practice signals
- **Microsoft (2025, Designing Multi-Agent Intelligence)**
  - Avoid keeping highly similar agents separate when they overlap in knowledge/action scope.
  - Refactor or group similar agents under shared interfaces/capabilities.
  - Supervisor/group abstraction is useful as domains scale.
- **IBM (2026, AI agent security guide)**
  - Keep least privilege, permission gating, audit logging, governance, approval workflows.
  - The real control point is policy and validation, not arbitrary fragmentation.
- **Knostic (2026, multi-agent security)**
  - Capability scoping, zero-trust between agents, isolated context windows, hardened orchestrator.
  - Warns specifically about capability bleed and over-shared toolsets without policy.
- **arXiv 2601.13671 (2026)**
  - Specialized agents remain valuable, but orchestration + policy + least-privilege communication are the backbone.
  - Privacy should restrict sharing to task-relevant information, not necessarily mandate one-agent-per-tool ownership.

### Architectural synthesis
- The evidence supports **relaxing tool exclusivity**, not removing governance.
- The stronger invariant should become:
  - **workflow/domain cohesion for agent boundaries**
  - **policy-scoped active capabilities per task/session**
  - **least privilege + HITL + auditability**
- This means ARIA should likely move away from “MCP belongs to one agent” and toward “MCP can be shared, but callable operations are scoped per agent/per task”.

### Candidate models
1. **Status quo / strict exclusive MCP ownership**
   - strongest static blast-radius boundaries
   - worst for adjacent workflows; causes delegation inflation
2. **Shared MCP pools with domain-capability agents**
   - best workflow fit
   - requires strong proxy policy, caller identity, audit, read/write splitting
3. **Hybrid model (current best recommendation)**
   - keep distinct domains where they are truly distinct (`search-agent`)
   - relax exclusivity where domains are adjacent (`workspace-agent` + `productivity-agent`)
   - use shared MCP access governed by policy-scoped capability bundles

### Current recommendation for ARIA
- Prefer the **hybrid model**.
- Near-term end-state should likely evolve toward:
  - `search-agent`
  - unified **productivity** domain agent (local files + office ingest + Google Workspace)
  - existing system agents unchanged
- Safer transition path:
  1. keep both agents temporarily
  2. let `productivity-agent` acquire scoped `google_workspace` capabilities under proxy policy
  3. use `workspace-agent` only as compatibility/privileged fallback for a short migration window
  4. later merge into **`productivity-agent` as the single surviving name** if runtime and prompts stay clean

### Blueprint / ADR implications
- Preserve:
  - isolation first
  - HITL on destructive/external actions
  - conductor non-operational role
  - child-session isolation
- Reword P9 from static exclusive tool ownership to something like:
  - **"Scoped active capabilities <= 20 per task/session"**
  - cap applies to simultaneously exposed callable tools, not permanent ownership
- ADR-0008 likely needs amendment or supersession because its anti-overlap reasoning predates the proxy-era policy control plane.

### User-approved naming constraint
- The converged single work-domain agent must retain the name **`productivity-agent`**.
- `workspace-agent` should be considered transitional and later deprecated/removed, not the surviving canonical name.
