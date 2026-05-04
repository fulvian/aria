# Progress — MCP Proxy Integration Audit

## 2026-05-01T17:14+02:00 — Session start
- User request: audit the implementation of `docs/plans/mcp_search_tool_plan_1.md` and verify deep integration of the new MCP proxy across ARIA conductor, the three current sub-agents, and their skills.
- Constraint: follow `AGENTS.md`, especially LLM wiki-first and Context7-first rules.

## 2026-05-01T17:15+02:00 — Context recovery complete
- Ran `planning-with-files` catchup script.
- Recovered existing branch context: `feat/mcp-tool-search-proxy`.
- Detected 2 uncommitted changes already present in conductor prompt files.

## 2026-05-01T17:16+02:00 — Wiki-first read complete
- Read `docs/llm_wiki/wiki/index.md`.
- Read `docs/llm_wiki/wiki/log.md`.
- Read `docs/llm_wiki/wiki/mcp-proxy.md`.
- Read existing planning files and replaced stale task framing with a new audit-focused plan.

## 2026-05-01T17:18+02:00 — Plan/spec/ADR audit complete
- Read the implementation plan sections covering F3 agent prompts and F5 skills normalization.
- Read the proxy design spec caller identity model and impact-on-agents sections.
- Read ADR-0015 for the intended proxy contract.

## 2026-05-01T17:20+02:00 — Runtime/prompt/skill inspection complete
- Inspected current proxy runtime files: `server.py`, `middleware.py`, `registry.py`, `conductor_bridge.py`.
- Inspected current runtime config: `mcp.json`, `agent_capability_matrix.yaml`.
- Inspected active prompts for conductor, search-agent, workspace-agent, productivity-agent.
- Inspected skills inventory and key skill files: `deep-research`, `office-ingest`, `meeting-prep`, `email-draft`.

## 2026-05-01T17:22+02:00 — Context7 verification complete
- Resolved FastMCP docs via Context7 (`/prefecthq/fastmcp`).
- Verified that search transforms expose only `search_tools` and `call_tool` and that middleware hooks are the intended enforcement point.

## 2026-05-01T17:24+02:00 — Main audit findings frozen
- Prompt frontmatter does not match the F3 proxy-only frontmatter design.
- Caller-aware backend filtering depends on `ARIA_CALLER_ID` but no inspected runtime path actually sets it.
- Middleware remains permissive when caller identity is missing.
- Skills still instruct direct backend or pseudo-tool invocation, not the canonical proxy contract.
- Some required skills referenced by prompts are missing from the skills tree.
- Observability/docs promise caller-anomaly handling stronger than what the inspected middleware currently appears to perform.

## 2026-05-01T17:26+02:00 — Wiki/state maintenance complete
- Updated `docs/llm_wiki/wiki/mcp-proxy.md` with an audit note on remaining mixed-state integration drift.
- Updated `docs/llm_wiki/wiki/index.md` status to reflect the post-cutover audit.
- Appended a timestamped audit entry to `docs/llm_wiki/wiki/log.md`.
- Updated `.workflow/state.md`, `task_plan.md`, and `findings.md` for the current analysis phase.

## 2026-05-01T17:34+02:00 — Architectural boundary research complete
- Read the relevant blueprint sections around P9, agent hierarchy, skills, and scoped toolsets.
- Read ADR-0008 and the canonical capability matrix to understand why `productivity-agent` and `workspace-agent` were originally separated.
- Performed external best-practice research via web sources (Microsoft, IBM, Knostic, arXiv orchestration paper).
- Synthesized the result into 3 candidate models:
  1. strict tool-exclusive agents,
  2. shared MCP/domain-capability agents,
  3. hybrid model.
- Current recommendation from the analysis: adopt the **hybrid** model and plan a controlled convergence of `workspace-agent` + `productivity-agent` toward a unified work-domain agent governed by proxy policy rather than hard MCP exclusivity.

## 2026-05-01T17:43+02:00 — User direction applied
- User approved proceeding with the hybrid architecture direction.
- Naming constraint fixed: the unified surviving work-domain agent must remain named **`productivity-agent`**.
- `workspace-agent` is now treated as transitional/deprecation-target in the design, not as the long-term canonical work agent.

## 2026-05-01T17:57+02:00 — Final convergence pass completed
- Applied the missing blueprint updates for P9 and the workspace/productivity boundary so the governance source of truth now reflects the approved architecture.
- The work-domain convergence is now documented consistently as: `workspace-agent` transitional, `productivity-agent` surviving unified agent.

## 2026-05-01T18:51+02:00 — Real CLI validation exposed remaining behavioral gaps
- User ran a real ARIA CLI scenario intended to validate the unified `productivity-agent`.
- The transcript showed that the conductor still completed the workflow directly instead of spawning `productivity-agent`.
- The flow also relied on direct `glob`/`read` style operational work, did not exercise a real HITL tool gate, and persisted an architecturally invalid success path into wiki memory.
- Next action: targeted remediation of conductor dispatch discipline, HITL enforcement, proxy-path verification, and wiki-write safety for invalid flows.

## 2026-05-01T19:02+02:00 — Behavioral remediation completed
- Hardened the runtime conductor template under `.aria/kilo-home/.kilo/agents/_aria-conductor.template.md` and synced the active runtime conductor file.
- Added an explicit `NESSUN lavoro diretto` section forbidding conductor-side operational work for file/search/GW/briefing/email tasks.
- Rewrote dispatch guidance so mixed work-domain tasks and Google Workspace operations route to `productivity-agent`, while `workspace-agent` is fallback-only and never a direct conductor target.
- Added a wiki validity guard forbidding memorialization of architecturally invalid direct-conductor execution paths.
- Expanded conductor dispatch tests and fixed prompt tests to read the stable runtime template used by prompt injection.
- Re-ran validation gates: `ruff check .`, `ruff format --check .`, `uv run mypy src`, `uv run pytest -q` all passed.

## 2026-05-01T19:50+02:00 — Runtime/source-of-truth drift fixed
- Realized the previous fix was still bypassed in CLI because ARIA CLI loads `.aria/kilocode/agents/aria-conductor.md`, not only the Kilo-home runtime files previously hardened.
- Found and fixed a test-isolation bug in `src/aria/memory/wiki/prompt_inject.py`: tests using `agent_dir=<tmp>` were still overwriting the real `.aria/kilocode/agents/aria-conductor.md` with a tiny fixture stub.
- Restored three aligned conductor files:
  - `.aria/kilo-home/.kilo/agents/_aria-conductor.template.md` with `{{ARIA_MEMORY_BLOCK}}`
  - `.aria/kilo-home/.kilo/agents/aria-conductor.md`
  - `.aria/kilocode/agents/aria-conductor.md`
- Switched conductor prompt tests to validate the real Kilo-loaded conductor file.
- Re-ran full gates successfully: `ruff`, `mypy`, `pytest` all green (`690 passed, 23 skipped, 3 warnings`).

## 2026-05-01T20:20+02:00 — Productivity-agent hardening completed
- Hardened `.aria/kilocode/agents/productivity-agent.md` and Kilo-home runtime copy to forbid ordinary use of host-native helpers (`Glob`, `Read`, `Write`, `TodoWrite`) when proxy-backed MCP routes exist.
- Added explicit requirements for real `hitl-queue__ask` gating on Google Workspace write operations and for a single valid `wiki_update_tool` call per turn.
- Clarified core work-domain skills (`office-ingest`, `consultancy-brief`, `email-draft`, `meeting-prep`) to reduce drift toward native host tools and pseudo-HITL text.
- Added new static contract tests in `tests/unit/agents/productivity/test_prompt_contract.py`.
- Re-ran full validation successfully: `ruff`, `mypy`, `pytest` all green (`700 passed, 23 skipped, 3 warnings`).

## 2026-05-01T22:48+02:00 — Definitive proxy/runtime hardening completed
- Applied the actual proxy fix for nested `_caller_id` extraction in `CapabilityMatrixMiddleware` and added a unit test covering the `call_tool(name=..., arguments={_caller_id,...})` pattern.
- Re-restored all conductor source-of-truth files (`.aria/kilocode`, Kilo-home active, Kilo-home template) after discovering stale Kilo-home prompt artifacts still contradicted the intended routing rules.
- Added explicit "no code edits / no config edits / no process killing / no auto-remediation" behavioral guardrails to conductor and productivity-agent user workflows.
- Re-ran all targeted and full gates successfully: `ruff`, `mypy`, `pytest` all green (`703 passed, 23 skipped, 3 warnings`).

## 2026-05-01T23:58+02:00 — Protocollo unico per futuri agenti creato
- User requested to stop the infinite testing loop and codify the lessons learned into a future-proof protocol.
- Read again the governing sources: `AGENTS.md`, blueprint, wiki index/log, capability matrix, ADR-0008.
- Asked a `system-analyst` sub-agent to synthesize the mandatory structure and hard gates for the future agent-creation workflow.
- Created `docs/protocols/protocollo_creazione_agenti.md` as the unique reference workflow for future sub-agent creation.
- Updated wiki `index.md` and `log.md` so the new protocol is now part of the documented source-of-truth set.

## Pending
- Produce a concise audit PRD / design delta for approval before any code changes.
- Do not implement until the target canonical contract is explicitly chosen and approved.

## 2026-05-04T00:31+02:00 — Traveller remediation session start
- Recovered branch context `feature/traveller-agent-f1` and verified clean working tree.
- Re-read wiki `index.md` and `log.md` first, then `traveller-agent.md`, `.workflow/state.md`, and planning files.

## 2026-05-04T00:36+02:00 — Context7 + local contract verification complete
- Verified FastMCP search transform contract via Context7 (`/prefecthq/fastmcp/v3.2.4`).
- Inspected live proxy tool schemas locally: `search_tools` requires only `query`; `call_tool` requires `name` plus optional `arguments`.
- Confirmed traveller prompt/skills were instructing the wrong payload shape.

## 2026-05-04T00:44+02:00 — Traveller runtime fixes implemented
- Rewrote traveller prompt and all 6 travel skills to use the real direct proxy contract.
- Hardened `CapabilityMatrixMiddleware` so backend execution via `call_tool` fails closed without caller identity, rejects synthetic recursion, and restores backend capability checks.
- Corrected booking catalog note drift and updated traveller wiki/index/log.
- Restored execute permission on `scripts/wrappers/aria-amadeus-wrapper.sh` and added regression coverage.

## 2026-05-04T00:46+02:00 — Verification complete
- Targeted traveller/proxy suite: `99 passed`.
- Targeted `ruff check` on changed code/tests: PASS.
- Repository-wide gates executed for transparency:
  - `ruff check .` fails for pre-existing unrelated issues (`src/aria/mcp/proxy/provider.py`, legacy traveller/conductor tests)
  - `ruff format --check .` fails for pre-existing unrelated files
  - `mypy src` fails for pre-existing unrelated proxy typing issue in `server.py` and stale ignores in `provider.py`
  - `pytest -q` fails mainly on pre-existing conductor prompt contract tests unrelated to the traveller remediation

## 2026-05-04T01:10+02:00 — Sessione 8 deep-debug: fallback gaps confirmed
- User provided live autoanalysis showing:
  - Amadeus `nearest_airport` failed but `locations_search` fallback was not attempted
  - 4 parallel `flight_offers_search` calls amplified `500/429`
  - `hotel_offers_search(city_code=...)` fallback not attempted after `hotel_list_by_geocode` failure
  - OSM route tools were skipped, so itinerary timings were estimated rather than computed
  - Booking remained the only healthy accommodation backend but sort/filter tools were not used

## 2026-05-04T01:18+02:00 — Deep-debug remediation implemented
- Hardened `aria-amadeus-mcp` server error semantics:
  - added retryable metadata, fallback hints, provider reason classification
  - added one lightweight retry on transient `429/5xx`
  - separated quota pre-check from actual outbound call accounting
- Updated traveller prompt + runtime mirror to continue in degraded mode when partial backend coverage survives.
- Updated travel skill runtime/source mirrors for explicit fallback order:
  - transport: `nearest_airport -> locations_search`, no aggressive parallel Amadeus burst
  - accommodation: `robots.txt` handling, `city_code` retry path, Booking sort/filter fallback
  - budget: partial budget mode + grounded web fallback for flight pricing

## 2026-05-04T01:22+02:00 — Deep-debug verification complete
- `uv run ruff check ...` on changed traveller/Amadeus files: PASS
- `uv run pytest -q tests/integration/agents/traveller/test_aria_amadeus_mcp_server.py tests/unit/agents/traveller/test_traveller_agent_prompt.py tests/unit/agents/traveller/test_traveller_skills.py`: `80 passed`

## 2026-05-04T07:34+02:00 — New live evidence: search-agent still touched Amadeus path
- User provided live logs showing `search-agent` attempted `aria-amadeus-mcp_flight_offers_search` before falling back to web search.
- This indicated a second-class problem beyond traveller degraded mode: search-agent needed a stronger explicit prompt boundary against travel MCP backends.

## 2026-05-04T07:38+02:00 — Local reproduction of persistent Amadeus failure completed
- Reproduced with real local credentials under project venv:
  - `nearest_airport`, `locations_search`, `hotel_list_by_geocode`, `flight_offers_search` all return `500` / provider code `38189`
- Confirmed with Context7 that the Python client methods and parameter shapes currently used are formally correct.
- Compared environments:
  - default test env → systematic `38189 Internal error`
  - `hostname='production'` → `401 invalid_client`
- Conclusion: credentials are not valid for production and the test environment/application state is unhealthy, not merely mis-parameterized.

## 2026-05-04T07:43+02:00 — Final remediation for persistent Amadeus 38189
- Added backend self-quarantine when Amadeus repeats provider code `38189`.
- Reclassified `38189` as `upstream_internal_error` non-retryable, with `upstream_service_quarantined` local cooldown after threshold.
- Added explicit `search-agent` prompt boundary forbidding travel MCP backends via proxy.
- Verification:
  - `uv run ruff check ...` PASS
  - `uv run pytest -q tests/integration/agents/traveller/test_aria_amadeus_mcp_server.py tests/unit/agents/search/test_prompt_grounding.py` → `25 passed`

## 2026-05-04T09:15+02:00 — Proxy caller contamination root fix completed
- User supplied live logs showing research sessions correctly tagged as `search-agent` but proxy behavior still acting as `traveller-agent`.
- Root cause isolated to legacy ambient `ARIA_CALLER_ID` fallback:
  - boot-time backend filtering in `src/aria/mcp/proxy/server.py`
  - request-time caller fallback in `src/aria/mcp/proxy/middleware.py`
- Implemented fix:
  - boot-time filtering moved to explicit `ARIA_PROXY_BOOT_CALLER_ID`
  - legacy `ARIA_CALLER_ID` ignored unless explicitly re-enabled
  - `call_tool` no longer borrows ambient env caller identity
  - search/discovery prompt examples now include `_caller_id`
- Verification:
  - `pytest -q tests/unit/mcp/proxy/test_server.py tests/unit/mcp/proxy/test_middleware.py tests/unit/agents/search/test_prompt_grounding.py` → `21 passed`
  - `pytest -q tests/integration/mcp/proxy/test_proxy_e2e_stdio.py` → `3 passed`
  - `uv run ruff check .` → PASS
  - `uv run ruff format --check ...` on modified files → PASS
  - `uv run mypy src` → PASS
  - `uv run pytest -q` → still red for pre-existing conductor-prompt drift tests unrelated to this fix
