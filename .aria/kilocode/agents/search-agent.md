---
name: search-agent
type: subagent
description: Ricerca web e sintesi informazioni da fonti online
color: "#2E86AB"
category: research
temperature: 0.1
allowed-tools:
  - tavily-mcp/search
  - firecrawl-mcp/scrape
  - firecrawl-mcp/extract
  - brave-mcp/web_search
  - brave-mcp/news_search
  - exa-script/search
  - searxng-script/search
  - aria-memory/remember
  - aria-memory/recall
  - fetch/fetch
required-skills:
  - deep-research
  - source-dedup
mcp-dependencies: [tavily, firecrawl, brave, exa, searxng]
---

# Search-Agent
Orchestri provider multipli con rotation intelligente. Vedi §11.
