---
name: deep-research
version: 1.0.0
description: Ricerca web approfondita multi-provider con deduplica e sintesi
trigger-keywords: [ricerca, search, approfondisci, analizza tema, deep, research]
user-invocable: true
allowed-tools:
  - tavily-mcp/search
  - firecrawl-mcp/scrape
  - firecrawl-mcp/extract
  - brave-mcp/web_search
  - brave-mcp/news_search
  - exa-script/search
  - searxng-script/search
  - aria-memory/remember
max-tokens: 50000
estimated-cost-eur: 0.10
---

# Deep Research Skill

## Obiettivo
Condurre una ricerca tematica su N query, deduplicare risultati, estrarre
contenuti, sintetizzare report strutturato.

## Procedura
1. Pianifica 3-7 sub-query diverse che coprono il tema da angolazioni distinte
2. Per ogni sub-query invoca il router: Tavily > Brave > Firecrawl > Exa
3. Deduplica URL (Levenshtein title + URL canonicalization)
4. Per top-N risultati, scrape full content via firecrawl
5. Classifica per rilevanza e data
6. Sintetizza report con sezioni: TL;DR, Findings, Open Questions, Sources
7. Salva report in memoria episodica con tag `research_report`

## Invarianti
- Cita SEMPRE le fonti con URL
- Se fonti contraddittorie, riportale entrambe
- Se meno di 3 fonti trovate, dichiara "ricerca povera"
