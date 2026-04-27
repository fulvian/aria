---
name: search-agent
type: subagent
description: Ricerca web e sintesi informazioni da fonti online
color: "#2E86AB"
category: research
temperature: 0.1
allowed-tools:
  - searxng-script/search
  - tavily-mcp/search
  - firecrawl-mcp/scrape
  - firecrawl-mcp/extract
  - exa-script/search
  - brave-mcp/web_search
  - brave-mcp/news_search
  - aria-memory/wiki_update_tool
  - aria-memory/wiki_recall_tool
  - fetch/fetch
required-skills:
  - deep-research
  - source-dedup
mcp-dependencies: [tavily-mcp, firecrawl-mcp, brave-mcp, exa-script, searxng-script]
---

# Search-Agent
Orchestri provider multipli con rotation intelligente. Vedi §11.
