---
name: workspace-agent
type: subagent
description: Operazioni Gmail, Calendar, Drive, Docs, Sheets via Google Workspace MCP
color: "#4285F4"
category: productivity
temperature: 0.1
allowed-tools:
  - google_workspace__gmail.*
  - google_workspace__calendar.*
  - google_workspace__drive.*
  - google_workspace__docs.*
  - google_workspace__sheets.*
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

# Workspace-Agent
Vedi §12 per spec dettagliata (OAuth, scope, handbook comandi).
