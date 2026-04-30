# Observability Plane

> **Architettura**: L4 — Observability Plane  
> **Stato**: ✅ v1.0 (2026-04-30)  
> **Source**: `src/aria/observability/`  
> **Plan**: `docs/plans/stabilizzazione_aria.md` §F4.1-F4.3

## Overview

Sistema di observability end-to-end per ARIA: structured logging JSON,
metriche Prometheus-ready, eventi tipati con trace_id propagato.

Componenti:
1. **Logger** — wrapper structlog con fallback stdlib
2. **Metrics** — registry Prometheus textfile collector
3. **Events** — emitter eventi tipati (cutover, rollback, drift)
4. **Trace propagation** — trace_id contestuale propagato via `contextvars`

## Logger

**File**: `src/aria/observability/logger.py`

### Schema evento JSON
```json
{
  "ts": "2026-04-30T12:34:56.789Z",
  "level": "INFO",
  "event": "agent.spawn.completed",
  "trace_id": "01HXY...",
  "session_id": "kilo_2026-04-30_xxx",
  "agent": "search-agent",
  "tool": null,
  "duration_ms": 1842,
  "outcome": "success",
  "metadata": {...}
}
```

### Categorie eventi
| Categoria | Esempi |
|-----------|--------|
| `agent.*` | spawn, handoff, complete, error |
| `tool.*` | call, result, timeout, error |
| `hitl.*` | request, approve, reject, timeout |
| `mcp.*` | startup, probe, drift, quarantine |
| `cutover.*` | activate, rollback |
| `drift.*` | detected, resolved |
| `llm.*` | select, fallback, budget |

### Funzionamento
- Prova `structlog` prima (import condizionale)
- Fallback stdlib con formattatore JSON custom
- Env `ARIA_STRUCTLOG=0` forza fallback stdlib
- Output: `.aria/runtime/logs/aria.jsonl` (rotazione giornaliera, `backupCount=90`)
- `AriaLogger` class: `.info()`, `.warning()`, `.error()`, `.bind()`
- `get_aria_logger(name)` factory singleton

## Metrics

**File**: `src/aria/observability/metrics.py`

### Metriche Prometheus
| Metric | Type | Labels |
|--------|------|--------|
| `aria_agent_spawn_total` | Counter | agent, parent |
| `aria_agent_spawn_duration_seconds` | Histogram | agent |
| `aria_tool_call_total` | Counter | agent, tool, outcome |
| `aria_hitl_request_total` | Counter | agent, action_type, outcome |
| `aria_mcp_startup_seconds` | Histogram | server |
| `aria_llm_tokens_total` | Counter | agent, model, kind |

### Output
- Formato: Prometheus textfile collector (`.prom`)
- Scrittura: `.aria/runtime/metrics/aria.prom`
- Disabilitabile: `ARIA_METRICS_ENABLED=0`
- Libreria: `prometheus_client` (Counter, Histogram, write_to_textfile)

## Events

**File**: `src/aria/observability/events.py`

Eventi tipati per azioni significative:
- `CutoverEvent` — attivazione nuova configurazione
- `RollbackEvent` — rollback a baseline
- `DriftDetected` — mismatch catalog↔runtime
- `QuarantineTriggered` — server messo in quarantena

Ogni evento ha: `ts`, `event_type`, `agent`, `trace_id`, `metadata`.

## Trace Propagation

```
Gateway (entrypoint)
    │ genera trace_id contestuale
    │ include in messaggio → conductor
    ▼
Conductor
    │ passa trace_id a HandoffRequest di ogni spawn
    ▼
Sub-Agent
    │ passa trace_id come tool_metadata in MCP call
    │ (se server lo supporta) oppure in argomenti tool
    ▼
ARIA-Memory MCP
    │ registra trace_id su pagine event/log
```

## Architettura Output

```
.aria/runtime/
├── logs/
│   └── aria.jsonl         # JSON lines, rotated
└── metrics/
    └── aria.prom           # Prometheus textfile, rigenerato ogni 10s
runtime/envelopes/
    └── {envelope_id}.json  # ContextEnvelope (TTL 10 min)
```

## Env Flag Rollback

| Flag | Effetto |
|------|---------|
| `ARIA_STRUCTLOG=0` | Forza fallback a stdlib logging |
| `ARIA_METRICS_ENABLED=0` | Disabilita metrics emitter |

## Test Coverage

- Logger/Metrics/Trace propagation: verificare contro il codice sorgente e i test effettivamente presenti nel repository; questa pagina documenta il comportamento implementato, non una suite dedicata completa.
