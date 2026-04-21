---
name: workspace-agent
type: subagent
description: Operazioni Gmail, Calendar, Drive, Docs, Sheets via Google Workspace MCP
color: "#4285F4"
category: productivity
temperature: 0.1
allowed-tools:
  - google_workspace/gmail.*
  - google_workspace/calendar.*
  - google_workspace/drive.*
  - google_workspace/docs.*
  - google_workspace/sheets.*
  - aria-memory/remember
  - aria-memory/recall
  - aria-memory/hitl_ask
required-skills:
  - triage-email
mcp-dependencies: [google_workspace]
disabled: true
---

# Workspace-Agent
Vedi §12 per spec dettagliata (OAuth, scope, handbook comandi).
