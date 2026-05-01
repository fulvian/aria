# MCP Refoundation — Rollback-First

> **Architettura**: L2 — MCP Plane  
> **Stato**: ✅ v6.3 (2026-05-01) — Proxy-native baseline after remediation  
> **Source**: `.aria/config/mcp_catalog.yaml`, `.aria/kilocode/mcp.json`, `src/aria/mcp/proxy/`, `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`  
> **Plan**: `docs/plans/mcp_search_tool_plan_1.md`

> **⚠️ DEPRECATED — Lazy Loader rimosso in F4.**  
> Il `lazy_loader.py` e i campi `lazy_load`/`intent_tags` nel catalog sono
> stati sostituiti dal `aria-mcp-proxy` (FastMCP-native). Vedi
> `docs/llm_wiki/wiki/mcp-proxy.md` e ADR-0015.

## Overview

Il MCP Plane implementa la Refoundation v2 dell'infrastruttura MCP ARIA.
Principio guida: **rollback-first**, baseline protetta (LKG), config-plane only.

Componenti attivi:
1. **MCP Catalog YAML** — source of truth per i backend MCP
2. **Drift Validator** — confronto catalog ↔ prompt ↔ runtime ↔ policy
3. **Capability Probe** — snapshot e quarantena schema/tool drift
4. **aria-mcp-proxy** — surface sintetica `search_tools` + `call_tool`
5. **Capability Matrix** — policy per-agent/per-backend enforcement

## Runtime baseline

### Kilo-visible runtime
- `aria-memory`
- `aria-mcp-proxy`

### Proxy-managed backend families
- search-domain servers
- productivity-domain servers
- selected system-domain servers from catalog

### Contract summary
- prompts/skills call the proxy synthetic tools
- `_caller_id` is mandatory in proxy requests
- capability matrix decides backend reachability
- `workspace-agent` is transitional; `productivity-agent` is the surviving
  unified work-domain agent

## MCP Catalog

**File**: `.aria/config/mcp_catalog.yaml`

Il catalogo resta la descrizione canonica dei backend disponibili. Dopo F4:
- `lazy_load` e `intent_tags` non sono più parte del modello attivo
- `owner_agent` non implica più esclusività architetturale assoluta del backend
- la condivisione tra agenti adiacenti è permessa se il proxy/policy layer la
  restringe correttamente

### Interpretazione aggiornata dei campi
- `domain`: dominio principale del backend
- `owner_agent`: ownership logica/operativa, non vincolo assoluto di esclusività
- `lifecycle`: enabled / disabled / quarantined
- `expected_tools`: utile per probe/drift validation
- `source_of_truth`: wrapper/server source

## Drift Validator

**File**: `scripts/check_mcp_drift.py`

Confronta:
1. Catalog YAML → runtime config / enabled servers
2. Agent prompts → canonical proxy contract
3. Capability matrix → effective backend access
4. Wiki pages ↔ filesystem `wiki/*.md`

Con il proxy attivo, un drift importante non è più solo “server missing”, ma anche:
- prompt che espongono backend wildcard dirette invece dei tool sintetici,
- skill che istruiscono chiamate backend bypassando il proxy,
- matrix/prompt incoerenti sul boundary `productivity-agent` / `workspace-agent`.

## Capability Probe

**File**: `src/aria/mcp/capability_probe.py`

Funzionalità principali:
- legge il catalog MCP YAML
- esegue `initialize` + `tools/list` per ogni server enabled
- salva snapshot in `.aria/runtime/mcp-schema-snapshots/`
- confronta `expected_tools` del catalog con i tool reali
- supporta quarantena operativa su mismatch

## Proxy-native cutover

### Completed milestones
- F0 smoke: proxy stdio verificato
- F1 core modules: implementati
- F2 shadow: proxy introdotto accanto al vecchio setup
- F3 cutover: `mcp.json` ridotto a 2 entry
- F4 cleanup: lazy loader rimosso
- F5 observability/skills updates
- F6 stabilization: stdio filter, naming normalization, matrix wildcards
- F7 caller-aware backend boot filtering
- F8 remediation: fail-closed middleware + canonical proxy contract + productivity/workspace convergence

## Governance updates introduced after remediation

- Prompt frontmatter now advertises proxy synthetic tools instead of backend
  families.
- The capability matrix, not prompt wildcards, is the effective authorization
  plane for backend calls.
- Blueprint P9 is now **Scoped Active Capabilities**, not static exclusive tool
  ownership.
- ADR-0008 amendment records the boundary change: `productivity-agent` is the
  unified work-domain agent; `workspace-agent` is transitional.

## Rollback matrix

| Trigger | Rollback | Blast | MTTR |
|---------|----------|:-----:|:----:|
| Drift legittimo bloccato | Modalità `--shadow` | server | <5 min |
| Falso positivo quarantena | `lifecycle=enabled` forzato | server | <2 min |
| Proxy fallisce al boot | `bin/aria start --emergency-direct` | proxy | <30 s |
| Canonical proxy contract regression | restore last-known-good prompt/matrix/ADR state | config plane | <10 min |

## Runbook

**File**: `docs/operations/mcp_cutover_rollback.md`

Procedura base:
1. restore config/branch baseline as needed
2. `bin/aria start --profile baseline` or `--emergency-direct`
3. verify smoke test domain
4. log cutover/rollback in wiki log + operations docs
