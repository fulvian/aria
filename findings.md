# Findings — Stabilization Audit

## Session: 2026-04-30

### Repository facts
- `docs/plans/stabilizzazione_aria.md` is missing, despite multiple wiki/log/runbook references.
- Working tree was clean at session start.
- Current remediation branch: `fix/stabilization-remediation`.

### Context7 verification
- `/pydantic/pydantic`: Pydantic v2 recommends `ConfigDict` for `extra='forbid'` and strict model configuration; `model_validate()` remains the canonical validation API.
- `/hynek/structlog`: recommended stdlib/contextvars integration preserves bound fields by using contextvar merge processors instead of overwriting explicit event fields.

### High-priority implementation gaps
1. `src/aria/launcher/lazy_loader.py`
   - Loads catalog assuming `servers` is a mapping.
   - Actual `.aria/config/mcp_catalog.yaml` stores `servers` as a list of objects.
   - Result: lazy-loading filter cannot operate on the real catalog.

2. `src/aria/mcp/capability_probe.py`
   - Parses only JSON/JSONC runtime config.
   - Cannot consume `.aria/config/mcp_catalog.yaml` directly.
   - Needs YAML support plus runtime command resolution from `.aria/kilocode/mcp.json`.

3. `src/aria/agents/coordination/registry.py`
   - Only defines a `Protocol`; no real registry implementation exists.
   - Repo already has canonical data in `.aria/config/agent_capability_matrix.yaml`.

4. `.aria/kilocode/agents/aria-conductor.md`
   - Handoff JSON example uses `timeout` instead of `timeout_seconds`.
   - Omits required `parent_agent` field.

5. `src/aria/agents/coordination/spawn.py`
   - Uses `aria.utils.metrics.incr`, which is a stub/no-op.
   - Should use `aria.observability.metrics` and emit richer validation telemetry without faking actual spawn execution.

### Documentation drift
- Wiki pages claim missing artifacts such as `scripts/check_mcp_drift.py` and the stabilization plan file.
- `docs/operations/baseline_lkg_v1/mcp_baseline.md` contains stale commit/tool-count facts.
- `docs/plans/stabilizzazione_aria.md` is useful as reconstructed direction, but several sections describe historical branch divergence rather than current repository state.
- `workspace-agent.md` was still a 25-line stub before this pass, despite the plan and wiki expecting an enforced coordination layer.

### YAGNI guardrails for this remediation
- Do not invent a full runtime spawn executor in Python; only repair validation, registry, and observability around the existing wrapper.
- Do not force full Phase 2 LLM-router activation; keep fixes limited to correctness, testability, and truthfulness of docs.
