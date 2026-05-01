# Agent Capability Matrix

**Status**: Active ✅  
**Updated**: 2026-05-01T18:38+02:00  
**Source**: `docs/foundation/agent-capability-matrix.md` (canonical), `.aria/config/agent_capability_matrix.yaml`, `.aria/kilocode/agents/*.md`

## Purpose

Wiki mirror of the active capability model. The canonical governance sources are:
- `docs/foundation/agent-capability-matrix.md`
- `.aria/config/agent_capability_matrix.yaml`

This page summarizes the **post-proxy-remediation** model, where:
- prompts expose proxy synthetic tools,
- the capability matrix governs backend reachability,
- `productivity-agent` is the unified work-domain agent,
- `workspace-agent` is transitional.

## Effective matrix snapshot (2026-05-01)

| Agent | Type | Prompt surface | Effective backend/policy reach | Delegation Targets | HITL Required |
|-------|------|----------------|--------------------------------|-------------------|---------------|
| **aria-conductor** | primary | memory + sequential-thinking + spawn | no direct operational backend usage | `search-agent`, `workspace-agent`, `productivity-agent` | destructive/costly/oauth-sensitive decisions |
| **search-agent** | subagent (research) | proxy synthetic tools + memory | search-domain backends only | none | no |
| **workspace-agent** | subagent (compatibility) | proxy synthetic tools + memory + hitl | `google_workspace__*` only | none | yes on side effects |
| **productivity-agent** | subagent (work domain) | proxy synthetic tools + memory + hitl + sequential-thinking + spawn | `markitdown-mcp__*`, `filesystem__*`, `google_workspace__*`, `fetch__*` | `workspace-agent` (compatibility fallback only) | yes on side effects |

## Important interpretation changes

### 1. Prompt surface ≠ backend reachability
Prompts now advertise a narrow synthetic proxy surface. Backend access is resolved
through:
1. `_caller_id`
2. proxy middleware
3. capability matrix

### 2. Shared backend access is now allowed
A backend can be reachable by more than one agent when domains are adjacent and
policy-scoped. This is the architectural change that enabled direct Google
Workspace access for `productivity-agent`.

### 3. Search stays separate
The convergence does **not** flatten ARIA into one generalist agent. The search
boundary remains distinct because it is a genuinely separate domain with its own
provider ladder and grounding rules.

## Routing policy snapshot

| Condition | Primary agent | Notes |
|------------|---------------|------|
| Ricerca informazioni online | `search-agent` | research-domain, proxy canonical model |
| File office locali | `productivity-agent` | office-ingest / markitdown path |
| Briefing multi-documento | `productivity-agent` | consultancy-brief |
| Preparazione meeting | `productivity-agent` | may combine calendar + local/Drive context |
| Bozze email | `productivity-agent` | direct GW reach via proxy |
| Gmail/Calendar/Drive read/write | `productivity-agent` | `workspace-agent` only as compatibility fallback |
| Task misti (file → email / file → calendar / drive → brief) | `productivity-agent` | no default 2-hop required anymore |
| Analisi + report | `search-agent` → `productivity-agent` | domain chain still valid |

## Handoff protocol

Minimal payload for `spawn-subagent` remains:

```json
{
  "goal": "descrizione del task (obbligatorio, max 500 char)",
  "constraints": "vincoli specifici (opzionale)",
  "required_output": "formato atteso risultato (opzionale)",
  "timeout": 120,
  "trace_id": "trace_xxx"
}
```

## Residual transition state

- `workspace-agent` still exists because compatibility cleanup is not yet fully complete.
- `productivity-agent` still lists `workspace-agent` as delegation target in the
  YAML for a transitional fallback path.
- Long-term target remains: `productivity-agent` as the only canonical work-domain agent.
