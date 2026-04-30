# Agent Capability Matrix

**Status**: Active ✅  
**Source**: `docs/foundation/agent-capability-matrix.md` (canonical)  
**Created**: 2026-04-29

## Purpose

Wiki mirror della capability matrix canonica. Il canonical source è
`docs/foundation/agent-capability-matrix.md`; questa pagina è un mirror
aggiornato per il LLM Wiki.

## Capability Matrix

| Agent | Type | Allowed Tools | MCP Dependencies | Delegation Targets | HITL Required |
|-------|------|--------------|------------------|-------------------|---------------|
| **aria-conductor** | primary (orchestrator) | 12 | `aria-memory` | search-agent, workspace-agent, productivity-agent | Su decisioni distruttive/costose |
| **search-agent** | subagent (research) | 23 | `tavily-mcp, brave-mcp, exa-script, searxng-script, reddit-search, scientific-papers-mcp` | Nessuna (leaf agent) | No |
| **workspace-agent** | subagent (productivity) | 8 | `google_workspace` | Nessuna (leaf agent) | Su write Gmail/Drive |
| **productivity-agent** | subagent (productivity) | 11 | `markitdown-mcp, aria-memory, filesystem` | workspace-agent (2-hop) | Su write wiki immutable, send mail |

## Handoff Protocol

Payload minimo per `spawn-subagent`:

```json
{
  "goal": "descrizione del task (obbligatorio, max 500 char)",
  "constraints": "vincoli specifici (opzionale)",
  "required_output": "formato atteso risultato (opzionale)",
  "timeout_seconds": 120,
  "trace_id": "trace_xxx",
  "parent_agent": "aria-conductor",
  "spawn_depth": 1,
  "envelope_ref": "env_uuid_opzionale"
}
```

Vedi `docs/foundation/agent-capability-matrix.md` §2 per dettagli ed esempi.

## Routing Policy

| Condizione | Agente primario | Note |
|------------|-----------------|------|
| Ricerca informazioni online | search-agent | Intent classification automatica |
| File office locali | productivity-agent | markitdown-mcp |
| Briefing multi-documento | productivity-agent | consultancy-brief skill |
| Preparazione meeting | productivity-agent | meeting-prep skill |
| Bozze email | productivity-agent | email-draft skill |
| Gmail/Calendar/Drive | workspace-agent | OAuth richiesto |
| Task misti (file→email) | productivity-agent → workspace-agent | 2-hop delega |
| Analisi + report | search-agent → productivity-agent | Chain 2-hop |

Vedi `docs/foundation/agent-capability-matrix.md` §3 per dettagli completi.
