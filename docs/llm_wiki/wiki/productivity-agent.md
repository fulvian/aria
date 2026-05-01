# Productivity-Agent

**Status**: Active ✅
**Created**: 2026-04-29
**Updated**: 2026-05-01T18:37+02:00
**Source**: `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md`, `docs/foundation/aria_foundation_blueprint.md`, `.aria/config/agent_capability_matrix.yaml`, `.aria/kilocode/agents/productivity-agent.md`
**Branch**: `feat/mcp-tool-search-proxy`

## Overview

`productivity-agent` is no longer only the “office ingest + briefing” agent. After
proxy remediation and the ADR-0008 amendment, it is now the **surviving unified
work-domain agent** for:

- local files
- office ingestion
- multi-document briefing
- meeting preparation
- email drafting
- Google Workspace operations via proxy policy

`workspace-agent` still exists, but only as a transitional compatibility surface.

## Architecture

```text
utente
  └─→ aria-conductor
       └─→ productivity-agent
              ├─ aria-mcp-proxy__search_tools
              ├─ aria-mcp-proxy__call_tool
              ├─ aria-memory__wiki_*
              ├─ sequential-thinking__*
              ├─ hitl-queue__ask
              └─ spawn-subagent (rare compatibility fallback only)
```

### Effective backend reachability (via proxy + capability matrix)
- `markitdown-mcp__*`
- `filesystem__*`
- `google_workspace__*`
- `fetch__*`

## Canonical invocation model

`productivity-agent` does not call backend MCP tools directly in prompt contract.
It uses the proxy synthetic tools and always passes:

- `_caller_id: "productivity-agent"`

Canonical sequence:
1. discover with `aria-mcp-proxy__search_tools`
2. execute with `aria-mcp-proxy__call_tool`

## Capability scope

### Read-oriented flows
- local file inspection
- office → markdown conversion
- Drive/Gmail/Calendar read access through proxy policy
- context fetch / URL scrape

### Write / side-effect flows
- send email
- create/update calendar events
- create/update Drive/Docs/Sheets artifacts
- wiki updates that persist durable knowledge

All side-effectful operations remain HITL-gated.

## Skills

| Skill | Version | Role |
|-------|---------|------|
| `office-ingest` | 3.0.0 | convert and normalize office/local documents into markdown-ready text |
| `consultancy-brief` | 1.0.0 | compose executive multi-document briefs |
| `meeting-prep` | 2.0.0 | assemble meeting briefing using calendar/doc/work context |
| `email-draft` | 2.0.0 | draft email with dynamic style, now aligned to proxy/GW direct path |
| `planning-with-files` | current | planning discipline for multi-step workflows |

## Boundary evolution

### Old model (superseded)
- `productivity-agent` handled local docs and briefing only
- all Gmail/Calendar/Drive actions were delegated to `workspace-agent`
- rationale: hard MCP exclusivity + tool-count concerns

### New model (current)
- `productivity-agent` handles the whole adjacent work domain directly
- `workspace-agent` is compatibility-only
- safety comes from proxy policy, caller identity, HITL, and audit — not from
  permanent MCP exclusivity

## Tool budget / governance

- P9 now applies as **scoped active capabilities per task/session**
- effective backend access is authorized in `.aria/config/agent_capability_matrix.yaml`
- prompt/frontmatter intentionally stays narrow even if policy can reach broader
  backend families

## Key decisions now in force

- surviving unified work-domain agent name remains **`productivity-agent`**
- direct Google Workspace reachability is allowed through proxy policy
- `workspace-agent` is not the long-term canonical work agent
- no local DOCX/PPTX/XLSX generation mandate was introduced; Google Workspace
  remains the preferred write surface for structured office artifacts

## Provenance and related pages

- ADR-0008 amendment records the boundary change
- `mcp-proxy.md` explains the canonical invocation/enforcement contract
- `agent-capability-matrix.md` mirrors the current per-agent reachability model
