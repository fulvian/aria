---
name: deep-research
version: 1.0.0
description: Ricerca web approfondita multi-provider con deduplica e sintesi
trigger-keywords: [ricerca, search, approfondisci, analizza tema, deep, research]
user-invocable: true
allowed-tools:
  - tavily-mcp_search
  - firecrawl-mcp_scrape
  - firecrawl-mcp_extract
  - brave-mcp_brave_web_search
  - brave-mcp_brave_news_search
  - exa-script_search
  - searxng-script_search
  - aria-memory_remember
  - aria-memory_recall
max-tokens: 50000
estimated-cost-eur: 0.10
---

# Deep Research Skill

## Obiettivo
Condurre una ricerca tematica su N query, deduplicare risultati, estrarre
contenuti, sintetizzare report strutturato.

## Procedura
1. Pianifica 3-7 sub-query diverse che coprono il tema da angolazioni distinte
2. Per ogni sub-query usa routing a tier:
   - Tier A: `searxng-script_search` (sempre first-pass)
   - Tier B: `brave-mcp_brave_web_search` poi `exa-script_search` poi `tavily-mcp_search`
   - Tier C: `fetch_fetch` per approfondire top-N URL
   - `firecrawl-mcp_scrape`/`firecrawl-mcp_extract` **SOLO** per scrape/extract esplicito di URL trovati da altri provider
   Escala al tier successivo solo se quality gate fallisce (pochi risultati, bassa coverage, bassa recency)
   Se Firecrawl tools ritornano `isError` (credits exhausted HTTP 402), salta e usa `fetch_fetch` al suo posto
3. Deduplica URL (Levenshtein title + URL canonicalization)
4. Per top-N risultati, scrape full content via `fetch_fetch` (o firecrawl se esplicitamente richiesto)
5. Classifica per rilevanza e data
6. Sintetizza report con sezioni: TL;DR, Findings, Open Questions, Sources
7. Salva report in memoria episodica con tag `research_report`

## Invarianti
- Cita SEMPRE le fonti con URL
- Se fonti contraddittorie, riportale entrambe
- Se meno di 3 fonti trovate, dichiara "ricerca povera"
- Se un provider ritorna errore di quota/API key esaurita, prova il provider successivo dello stesso tier o tier successivo
