# MCP Productivity Coordination + Academic MCP Hardening — Findings

## Primary Findings

1. **Drift search-agent → policy**: search-agent dichiarava tier policy con `pubmed` e `scientific_papers` ma non li esponeva in `allowed-tools` né `mcp-dependencies`. Policy non pienamente eseguibile. **Fixato v4.0**: aggiunti 9+5 tool.

2. **Gap conductor → productivity-agent**: `aria-conductor.md` elencava solo search-agent e workspace-agent come sub-agenti. Productivity-agent esisteva ma non era dispatchabile. **Fixato v4.0**: aggiunto con dispatch rules.

3. **PubMed wrapper monocultura bunx**: wrapper usava solo `bunx`, se bun non presente → crash. **Fixato v4.0**: fallback automatico a `npx` con log WARN.

4. **Scientific papers cache mutation fragile**: patching basato su copia file JS in cache npx, senza version pin né checksum verification. **Fixato v4.0**: version pinned 0.1.40, SHA256 checksum pre/post, hard fail su mismatch.

5. **Originali npm non preservati**: i file `.original.js` in `docs/patches/scientific-papers-mcp/` erano duplicati dei patched (stessi checksum). **Fixato v4.0**: scaricati veri originali da `npm pack @futurelab-studio/latest-science-mcp@0.1.40`.

## Context7-Verified Tool Names

### PubMed MCP (9 tools)
- `pubmed_search_articles`, `pubmed_fetch_articles`, `pubmed_fetch_fulltext`
- `pubmed_format_citations`, `pubmed_find_related`, `pubmed_spell_check`
- `pubmed_lookup_mesh`, `pubmed_lookup_citation`, `pubmed_convert_ids`

### Scientific Papers MCP (5 tools)
- `search_papers`, `fetch_content`, `fetch_latest`, `list_categories`, `fetch_top_cited`

## Key Decisions
- Pubmed tool names use `pubmed_` prefix (confirmed by Context7)
- Scientific papers tools use unprefixed names (no prefix, confirmed by Context7)
- Version pin scelto invece di `@latest` per evitare drift patch/npm
- Checksum verification eseguita sia pre-patch (originale npm match) sia post-patch (patched match)
- SCIENTIFIC_PAPERS_SKIP_PATCH=1 per bypassare hard fail in emergenza

## P2 Findings — Benchmark & Gateway

### Startup Latency (9 MCP servers, 2026-04-29)
- **Cold start total**: 6.5s (avg 722ms/server)
- **Warm start total**: 6.1s (avg 680ms/server)
- **Tools total**: 49 (14 filesystem + 1 seq-thinking + 10 aria-memory + 1 fetch + 1 searxng + 6 reddit + 9 pubmed + 6 scientific-papers + 1 markitdown)
- **tools/list**: 1-11ms per server (bottleneck non e' la negoziazione capability)
- **Slowest**: searxng-script (1.45s, invariato cold/warm — backend Docker)
- **Fastest**: fetch (342ms cold, 329ms warm — uvx con caching efficace)

### Gateway Evaluation: ❌ NON giustificato
- Overhead startup accettabile (~700ms medio)
- Warm start gia' veloce (~680ms medio)
- Gateway aggiunge: latenza, complessita', single point of failure
- Alternativa migliore: **lazy loading per intent** (caricare solo server necessari per l'intent corrente)
- Soglia per riconsiderare: >25 server, >20s startup, >200 tool count
