# MCP Baseline — baseline-LKG-v1

**Data**: 2026-04-30T19:52+02:00  
**Tag**: `baseline-LKG-v1`  
**Commit**: ef0e5e66faad200056e1c0fba345b1f927d7ad24

## MCP Server Inventory

Fonte: `.aria/config/mcp_catalog.yaml` (stabilization scope) con riscontro runtime su `.aria/kilocode/mcp.json`.

Nota: il runtime `mcp.json` include anche i server compatibilita' `git` e `github`.
La baseline di stabilizzazione sotto riporta i 14 server catalogati nel piano v5.0.

| Server | Transport | Tools | Enabled |
|--------|-----------|-------|:-------:|
| filesystem | stdio | 14 | Si |
| sequential-thinking | stdio | 1 | Si |
| aria-memory | stdio | 10 | Si |
| fetch | stdio | 1 | Si |
| searxng-script | stdio | 1 | Si |
| reddit-search | stdio | 6 | Si |
| scientific-papers-mcp | stdio | 5 | Si |
| markitdown-mcp | stdio | 1 | Si |
| brave-mcp | stdio | 5+ | Si |
| exa-script | stdio | 2 | Si |
| tavily-mcp | stdio | 5+ | Si |
| google_workspace | stdio | 20+ | Si |
| playwright | stdio | ~15 | No |
| github-discovery | stdio | 10+ | Si |

**Totale server catalogati**: 14  
**Tool stimate**: ~75+

## Startup Latency (riferimento)

Da benchmark 2026-04-29 su 9 server:

| Server | Cold (ms) | Warm (ms) | Tools |
|--------|-----------|-----------|-------|
| filesystem | 633 | 626 | 14 |
| sequential-thinking | 608 | 613 | 1 |
| aria-memory | 546 | 572 | 10 |
| fetch | 342 | 329 | 1 |
| searxng-script | 1453 | 1452 | 1 |
| reddit-search | 510 | 526 | 6 |
| scientific-papers-mcp | 1137 | 670 | 5 |
| markitdown-mcp | 632 | 676 | 1 |
| **Total (9 server)** | **~6.5s** | **~6.1s** | **49** |

## Agent Prompt Baseline

| Agent | File | Lines |
|-------|------|:-----:|
| aria-conductor | `.aria/kilocode/agents/aria-conductor.md` | ~120 |
| search-agent | `.aria/kilocode/agents/search-agent.md` | ~128 |
| workspace-agent | `.aria/kilocode/agents/workspace-agent.md` | ~25 (STUB) |
| productivity-agent | `.aria/kilocode/agents/productivity-agent.md` | ~109 |

## Test Count Baseline

```
pytest -q: 548 passed, 21 skipped
```
