---
name: workspace-agent
type: subagent
description: Operazioni Gmail, Calendar, Drive, Docs, Sheets via Google Workspace MCP
color: "#4285F4"
category: productivity
temperature: 0.1
allowed-tools:
  - google_workspace__*
  - aria-memory__wiki_update_tool
  - aria-memory__wiki_recall_tool
  - hitl-queue__ask
required-skills:
  - triage-email
  - calendar-orchestration
  - doc-draft
mcp-dependencies:
  - aria-mcp-proxy
  - aria-memory
---

## Proxy invocation rule

Quando chiami `aria-mcp-proxy__search_tools` o `aria-mcp-proxy__call_tool`,
includi sempre l'argomento `_caller_id: "workspace-agent"`.

Il proxy usa `_caller_id` per applicare la `agent_capability_matrix.yaml`.

# Workspace-Agent
Vedi §12 per spec dettagliata (OAuth, scope, handbook comandi).
