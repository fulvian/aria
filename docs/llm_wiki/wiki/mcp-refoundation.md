# MCP Refoundation — Rollback-First

> **Architettura**: L2 — MCP Plane  
> **Stato**: ✅ v6.0 (2026-05-01) — Proxy-native  
> **Source**: `.aria/config/mcp_catalog.yaml`, `src/aria/mcp/proxy/`  
> **Plan**: `docs/plans/mcp_search_tool_plan_1.md`  

> **⚠️ DEPRECATED — Lazy Loader rimosso in F4.**
> Il `lazy_loader.py` e i campi `lazy_load`/`intent_tags` nel catalog sono
> stati sostituiti dal `aria-mcp-proxy` (FastMCP-native). Vedi
> `docs/llm_wiki/wiki/mcp-proxy.md` e ADR-0015.

## Overview

Il MCP Plane implementa la Refoundation v2 dell'infrastruttura MCP ARIA.
Principio guida: **rollback-first**, baseline protetta (LKG), config-plane only.

Componenti:
1. **MCP Catalog YAML** — single source of truth per tutti i server MCP
2. **Drift Validator** — confronto catalog ↔ mcp.json ↔ agent prompt ↔ router code
3. **Capability Probe** — generalizzato a tutti i server, snapshot e quarantena
4. ~~**Lazy Loader**~~ (RIMOSSO in F4) — sostituito da `aria-mcp-proxy`
5. **NEW: aria-mcp-proxy** — FastMCP-native multi-server proxy (ADR-0015)

## MCP Catalog

**File**: `.aria/config/mcp_catalog.yaml`

Catalogo canonico per tutti i 14 server MCP. Schema:

```yaml
servers:
  - name: scientific-papers-mcp
    domain: search
    owner_agent: search-agent
    tier: 2
    transport: stdio
    lifecycle: enabled  # enabled | disabled | quarantined
    auth_mode: keyless
    statefulness: stateless
    expected_tools:
      - search_papers
      - fetch_content
      - fetch_latest
      - list_categories
      - fetch_top_cited
    risk_level: low
    cost_class: free
    source_of_truth: scripts/wrappers/scientific-papers-wrapper.sh
    rollback_class: server  # server | domain | session
    baseline_status: lkg  # lkg | candidate | shadow | disabled
    intent_tags: [academic]
    lazy_load: true
    intent_required: [academic]
    notes: "patched npm v0.1.40, version pin via wrapper checksum"
```

### Server classificati (14)

| Server | Domain | Tier | Lazy Load | Baseline |
|--------|--------|:---:|:---------:|:--------:|
| filesystem | system | 0 | ❌ | lkg |
| sequential-thinking | system | 0 | ❌ | lkg |
| aria-memory | memory | 0 | ❌ | lkg |
| fetch | search | 3 | ✅ | lkg |
| searxng-script | search | 1 | ✅ | lkg |
| reddit-search | search | 1 | ✅ | lkg |
| scientific-papers-mcp | search | 2 | ✅ | lkg |
| brave-mcp | search | 4 | ✅ | lkg |
| exa-script | search | 5 | ✅ | lkg |
| tavily-mcp | search | 3 | ✅ | lkg |
| google_workspace | productivity | 0 | ❌ | lkg |
| playwright | system | 0 | ❌ | lkg |
| markitdown-mcp | productivity | 0 | ✅ | lkg |
| github-discovery | search | 0 | ✅ | lkg |

### Cutover Policy

- Tutti i cambi a `mcp.json` passano via catalog → generatore
- Drift validator in CI come gate bloccante (`make check-drift`)
- Schema snapshot mismatch → quarantena server (lifecycle=quarantined)
- Gateway PoC search: dietro flag `ARIA_GATEWAY_SEARCH=1`, bypass = unset

## Drift Validator

**File**: `scripts/check_mcp_drift.py`

Confronta:
1. Catalog YAML → `mcp.json` enabled servers
2. Agent prompts `allowed-tools` → `mcp_dependencies` → `mcp.json`
3. Router code (Provider enum) → search-agent `allowed-tools`
4. Wiki index pages ↔ filesystem `wiki/*.md`

Modalità:
- `--shadow`: warning only (default per F2)
- `--enforce`: exit 1 su drift (default per F3+)
- `--baseline-mode`: exit 0 anche con issue P1

## Capability Probe

**File**: `src/aria/mcp/capability_probe.py`

Generalizzazione del probe originale (`src/aria/agents/search/capability_probe.py`).

Funzionalità:
- Legge catalog MCP YAML
- Esegue `initialize` + `tools/list` per ogni server enabled
- Salva snapshot in `.aria/runtime/mcp-schema-snapshots/{server}-{date}.json`
- Confronta `expected_tools` del catalog con i tool reali
- Quarantena automatica su mismatch (lifecycle=quarantined, NON modifica catalog SoT)
- CLI: `bin/aria probe-mcp` (one-shot) + `bin/aria start --probe` (pre-flight)

## ~~Lazy Loader~~ (RIMOSSO in F4)

~~**File**: `src/aria/launcher/lazy_loader.py`~~ (rimosso in F4/commit 0457044)

Sostituito da `aria-mcp-proxy` (ADR-0015). I campi `lazy_load` e `intent_tags`
sono stati rimossi da `.aria/config/mcp_catalog.yaml`.

## ADR

| ADR | Titolo | Status |
|-----|--------|:------:|
| ADR-0009 | MCP catalog as single source of truth | ✅ Accepted |
| ADR-0010 | Lazy loading per intent enablement | 🗑️ Deprecated (F4) |
| ADR-0012 | MCP cutover and rollback policy | ✅ Accepted |
| ADR-0015 | FastMCP-native multi-server proxy | ✅ Implemented (F1-F3) |

## Rollback Matrix

| Trigger | Rollback | Blast | MTTR |
|---------|----------|:-----:|:----:|
| Drift legittimo bloccato | Modalità `--shadow` | server | <5 min |
| Falso positivo quarantena | lifecycle=enabled forzato | server | <2 min |
| Proxy fallisce al boot | `bin/aria start --emergency-direct` | proxy | <30 s |
| Gateway PoC errori | Unset `ARIA_GATEWAY_SEARCH` | domain | <2 min |

## Runbook

**File**: `docs/operations/mcp_cutover_rollback.md`

Procedura:
1. `git checkout baseline-LKG-v1 -- .aria/config/mcp_catalog.yaml`
2. `bin/aria start --profile baseline` (ripristina mcp.json originale)
3. Verifica smoke test dominio
4. Logga cutover/rollback in `docs/operations/mcp_cutover_rollback.md`
