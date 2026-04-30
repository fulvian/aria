# LLM Routing Plane

> **Architettura**: L3 — LLM Routing Plane  
> **Stato**: ✅ v1.0 (2026-04-30)  
> **Source**: `.aria/config/llm_routing.yaml`, `src/aria/routing/llm_router.py`  
> **Plan**: `docs/plans/stabilizzazione_aria.md` §F4.4

## Overview

Sistema dichiarativo di routing LLM: matrice task→modello con fallback chain,
budget gate e prompt caching strategy.

## Matrice Dichiarativa

**File**: `.aria/config/llm_routing.yaml`

### Modelli disponibili
| Model ID | Cost Tier | Capabilities |
|----------|:---------:|--------------|
| `claude-opus-4-7` | high | orchestration, deep_reasoning, planning |
| `claude-sonnet-4-6` | medium | research, synthesis, drafting, tool_use |
| `claude-haiku-4-5-20251001` | low | classification, triage, formatting, cheap_calls |

### Routing per agente
| Agent | Primary | Fallback | Cache Strategy | Max Tokens |
|-------|---------|----------|:--------------:|:----------:|
| aria-conductor | opus_4_7 | sonnet_4_6 | long (≥1024) | 8192 |
| search-agent | sonnet_4_6 | haiku_4_5 | medium | 4096 |
| workspace-agent | sonnet_4_6 | haiku_4_5 | medium | 4096 |
| productivity-agent | sonnet_4_6 | haiku_4_5 | long (ingest) | 6144 |

### Intent Override
| Intent | Model |
|--------|-------|
| triage | haiku_4_5 |
| deep_reasoning | opus_4_7 |

### Policy
| Parametro | Valore |
|-----------|--------|
| Daily token cap (USD) | $5.00 |
| Overflow action | degrade (→ fallback, mai block) |
| Fallback chain max | 2 hops |

## Router Python

**File**: `src/aria/routing/llm_router.py`

### API
```python
class LlmRouter:
    def __init__(self, config_path: str = ...): ...
    def select_model(agent: str, intent: str | None = None) -> ModelSpec: ...
    def apply_fallback(prev_model: ModelSpec, error: str) -> ModelSpec | None: ...
    def enforce_budget(estimated_tokens: int, model: ModelSpec) -> bool: ...
    def get_model_for_agent(agent: str) -> ModelSpec: ...
```

### Fallback Logic
```
attempt primary → on error → attempt fallback → on error → attempt fallback[1]
                                                              ↓
                                                     degrade o block
                                                     (degrade = return last working)
```

### Budget Gate
- Tracciamento token giornaliero per modello
- Cap USD configurabile (`daily_token_cap_usd`)
- Overflow action = `degrade` (usa fallback invece di primary costoso)
- `ARIA_LLM_ROUTING=0` disabilita (KiloCode usa default)

## Prompt Caching Strategy

Basata su Anthropic prompt caching (2026).

| Agent | System Prompt Size | Cache Strategy |
|-------|:-----------------:|:--------------:|
| aria-conductor | ~3-4K token (profile + memory contract) | cache-control prefix >1024 token |
| search-agent | ~2K token | cache-control prefix >1024 token |
| workspace-agent | ~2K token | cache-control prefix >1024 token |
| productivity-agent | ~3K token | cache-control prefix >1024 token |

## ADR

| ADR | Titolo | Status |
|-----|--------|:------:|
| ADR-0013 | LLM routing as declarative matrix | ✅ Accepted |
| ADR-0014 | Observability schema and trace propagation | ✅ Accepted |

## Env Flag Rollback

| Flag | Effetto |
|------|---------|
| `ARIA_LLM_ROUTING=0` | Disabilita LLM router (KiloCode usa default) |
