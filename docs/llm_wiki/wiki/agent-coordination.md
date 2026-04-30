# Agent Coordination System

> **Architettura**: L1 — Coordinamento Agenti  
> **Stato**: ✅ v1.0 (2026-04-30)  
> **Source**: `src/aria/agents/coordination/`, `.aria/config/agent_capability_matrix.yaml`  
> **Plan**: `docs/plans/stabilizzazione_aria.md` §F2

## Overview

Il sistema di coordinamento agenti formalizza il protocollo di comunicazione tra
i 4 agenti ARIA (conductor, search, workspace, productivity) tramite:

1. **Capability Matrix** — dichiarativa YAML, single source of truth per tool/permission/limit
2. **Handoff JSON** — protocollo Pydantic per spawn-subagent
3. **Context Envelope** — contesto condiviso propagato dal conductor
4. **Agent Registry** — loader+validator runtime per capability matrix
5. **Spawn Validator** — wrapper che inietta envelope, valida payload e profondità

## Architettura

```
Gateway Telegram
    │ trace_id
    ▼
Conductor
    │ compone ContextEnvelope (wiki_recall una tantum)
    │ crea HandoffRequest {goal, constraints, required_output, trace_id, ...}
    ▼
SpawnValidator
    │ validate: handoff fields ✓
    │ validate: delegation allowed ✓ (registry)
    │ validate: spawn_depth ≤ 2 ✓
    │ inject: envelope_ref
    ▼
Sub-Agent (search / workspace / productivity)
    │ legge envelope se presente, altrimenti wiki_recall diretto
    │ esegue task
    ▼
Risultato → Conductor → Utente
```

## Capability Matrix

**File**: `.aria/config/agent_capability_matrix.yaml`

Schema:
```yaml
agents:
  - name: aria-conductor
    type: primary
    allowed_tools:
      - aria-memory/wiki_update_tool
      - aria-memory/wiki_recall_tool
      - aria-memory/hitl_ask
      - sequential-thinking/*
      - spawn-subagent
      # ... (10+ tool)
    mcp_dependencies:
      - aria-memory
    delegation_targets:
      - search-agent
      - workspace-agent
      - productivity-agent
    hitl_triggers:
      - destructive
      - costly
      - oauth_consent
    max_tools: 20
    max_spawn_depth: 2
```

Ogni agente ha:
- `allowed_tools`: lista esatta di tool MCP accessibili
- `mcp_dependencies`: server MCP richiesti
- `delegation_targets`: agenti delegabili (solo per conductor)
- `hitl_triggers`: condizioni che richiedono approvazione umana
- `max_tools`: vincolo P9 (≤20 tool per sub-agente)
- `max_spawn_depth`: profondità massima catena (≤2 hop)

## Handoff JSON Protocol

**File**: `src/aria/agents/coordination/handoff.py`

Modello Pydantic v2:
```python
class HandoffRequest(BaseModel):
    goal: str = Field(..., max_length=500)
    constraints: str | None = None
    required_output: str | None = None
    timeout_seconds: int = Field(default=120, ge=10, le=300)
    trace_id: str
    parent_agent: str
    spawn_depth: int = Field(default=1, ge=1, le=2)
    envelope_ref: str | None = None
```

Ogni chiamata `spawn-subagent` DEVE includere un `HandoffRequest` valido.
Validator runtime rifiuta payload free-form.

## Context Envelope

**File**: `src/aria/agents/coordination/envelope.py`

```python
class ContextEnvelope(BaseModel):
    envelope_id: str  # UUIDv7
    trace_id: str
    session_id: str
    wiki_pages: list[WikiPageSnapshot]
    profile_snapshot: str | None
    created_at: datetime
    expires_at: datetime  # default +5 min
```

- Composto **una volta** dal conductor (single `wiki_recall`)
- Propagato a tutta la catena di sub-agent (non rifanno `wiki_recall`)
- Iniettato via `envelope_ref` nell'HandoffRequest
- Storage: `.aria/runtime/envelopes/{envelope_id}.json` (TTL 10 min)
- Cleanup automatico via `cleanup_expired_envelopes()`

## Agent Registry

**File**: `src/aria/agents/coordination/registry.py`

Carica `.aria/config/agent_capability_matrix.yaml` al boot.
API pubblica:
- `get_agent(name) -> AgentSpec`
- `get_allowed_tools(name) -> list[str]`
- `validate_delegation(parent, target) -> bool`
- `validate_tool_count(name) -> bool`
- `get_delegation_targets(name) -> list[str]`

## Spawn Validator

**File**: `src/aria/agents/coordination/spawn.py`

Wrapper `spawn_subagent_validated()`:
1. Valida `HandoffRequest` (campi obbligatori, formati)
2. Valida `spawn_depth ≤ 2` (depth=3 → errore)
3. Valida delegazione nel registry
4. Emette evento `aria_agent_spawn_total{trace_id, parent, target}`
5. Inietta `envelope_ref` se envelope fornito
6. Costruisce payload per `spawn-subagent`

## Env Flag Rollback

| Flag | Effetto |
|------|---------|
| `ARIA_CAPABILITY_ENFORCEMENT=0` | Disabilita capability matrix validator |
| `ARIA_HANDOFF_VALIDATION=0` | Disabilita handoff JSON validator |

## Tests

| Suite | File | Count |
|-------|------|:-----:|
| Unit handoff | `tests/unit/agents/coordination/test_handoff.py` | ≥10 |
| Unit envelope | `tests/unit/agents/coordination/test_envelope.py` | ≥8 |
| Unit registry | `tests/unit/agents/coordination/test_registry.py` | ≥8 |
| Unit spawn | `tests/unit/agents/coordination/test_spawn.py` | ≥8 |
| Integration handoff | `tests/integration/coordination/test_handoff_validation.py` | 4 |
| Integration envelope | `tests/integration/coordination/test_envelope_propagation.py` | 4 |
| Integration spawn depth | `tests/integration/coordination/test_spawn_depth_guard.py` | 4 |
| Integration capability | `tests/integration/coordination/test_capability_matrix.py` | 6 |

**Totale**: 86 test di coordinamento.
