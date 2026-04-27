# ADR-0006 — Research Agent Academic + Social Provider Expansion

**Status**: Accepted
**Date**: 2026-04-27
**Supersedes**: —
**Related**: ADR-0001 (dependency baseline)

## Context

Blueprint §11.1 elenca 6 provider MVP (Tavily, Firecrawl, Brave, Exa, SearXNG, SerpAPI)
e §11.2 definisce 3 intent (general/news, academic, deep_scrape).
Firecrawl rimosso 2026-04-27 (esaurimento crediti lifetime). Necessità operativa di:

- Provider accademici dedicati (PubMed, Europe PMC, arXiv)
- Provider social (Reddit) per intent SOCIAL
- Adesione a P8 (Tool Priority Ladder: MCP > Python) e P10 (Self-Documenting Evolution)

## Decision

1. **Aggiungere 3 MCP server**:
   - `@cyanheads/pubmed-mcp-server` (v2.6.4) — Ricerca biomedica PubMed con 9 tool specializzati
   - `benedict2310/scientific-papers-mcp` — Ricerca multi-sorgente accademica (arXiv, Europe PMC, OpenAlex, biorxiv, PMC, CORE) tramite tool `search_papers(source, query)`
   - `jordanburke/reddit-mcp-server` (OAuth obbligatorio) — Lettura contenuti Reddit
2. **Introdurre `Intent.SOCIAL`** con tier ladder: `REDDIT > SEARXNG > TAVILY > BRAVE`
3. **Riordinare `Intent.ACADEMIC`**: `SEARXNG > PUBMED > SCIENTIFIC_PAPERS > TAVILY > EXA > BRAVE > FETCH`
4. **Europe PMC**: via `scientific-papers-mcp` MCP, NON via provider Python nativo (P8 compliance)
5. **Reddit OAuth obbligatorio**: nessuna modalità anonima (verificato Context7)
6. **Pattern wrapper + CredentialManager + SOPS** per tutte le chiavi (P4 compliance)
7. **arXiv standalone** (`blazickjp/arxiv-mcp-server[pdf]`) opzionale Phase 2 solo per PDF pipeline

## Consequences

- Blueprint §11.1 e §11.2 divergenti dal codice (registrato qui per P10 compliance)
- 3 nuovi MCP in mcp.json (~150 MB RAM stimati aggiuntivi)
- Reddit gated su HITL OAuth setup; fallback SearXNG sufficiente via engine `reddit`
- PubMed key facoltativa (3 req/s senza chiave, 10 req/s con chiave NCBI)
- `scientific-papers-mcp` è keyless (Europe PMC 10 req/min senza chiave)
- arXiv standalone (`blazickjp`) NON installato inizialmente; solo se serve `download_paper`/`read_paper`
- `Intent.SOCIAL` separato da `GENERAL_NEWS` con tier dedicato

## Verification

| Provider | Context7 ID | Snippets | Benchmark | Stato |
|----------|-------------|----------|-----------|-------|
| PubMed | `/cyanheads/pubmed-mcp-server` | 1053 | 83.7 | ✅ Verified 2026-04-27 |
| Scientific Papers | `/benedict2310/scientific-papers-mcp` | 5319 | 67.0 | ✅ Verified 2026-04-27 |
| Reddit | `/jordanburke/reddit-mcp-server` | 39 | — | ✅ Verified 2026-04-27 |
| arXiv standalone | `/blazickjp/arxiv-mcp-server` | 112 | 76.1 | ✅ Verified 2026-04-27 |
