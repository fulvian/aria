---
name: deep-research
version: 3.0.0
description: Ricerca web approfondita multi-provider con deduplica e sintesi. Usa il proxy MCP per tutte le chiamate backend.
trigger-keywords: [ricerca, search, approfondisci, analizza tema, deep, research, reddit, social]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - aria-memory__wiki_update_tool
  - aria-memory__wiki_recall_tool
max-tokens: 50000
estimated-cost-eur: 0.10
---

# Deep Research Skill

## Obiettivo
Condurre una ricerca tematica su N query, deduplicare risultati, estrarre
contenuti, sintetizzare report strutturato.

## Proxy invocation rule

Tutte le chiamate ai backend MCP passano dal proxy. Ogni chiamata deve includere
`_caller_id: "search-agent"`:

```
aria-mcp-proxy__call_tool(
  name="<server__tool>",
  arguments={
    <tool params>,
    "_caller_id": "search-agent"
  }
)
```

Per scoprire tool disponibili:
```
aria-mcp-proxy__search_tools(query="<descrizione>", _caller_id="search-agent")
```

## REGOLA FISSA — Dual Tier 1 (gratuiti e illimitati)

**searxng** (self-hosted) e **reddit-search** (keyless scraper) sono SEMPRE i primi due provider
da tentare per TUTTI gli intent (eccetto deep_scrape). Entrambi sono **gratuiti e illimitati**:
- searxng: nessuna API key, self-hosted, privacy-first
- reddit-search: nessuna API key, scraping old.reddit.com, 6 tool di ricerca
- Non passare mai a provider a pagamento senza prima aver tentato entrambi.

## Tier Ladder (SOTA April 2026 — ordine obbligatorio)

| Intent | 1a 🆓 | 1b 🆓 | 2 | 3 | 4 | 5 | 6 | 7 |
|--------|-------|-------|---|---|---|---|---|---|
| `general/news` | **searxng** | **reddit** | **tavily** | **exa** | **brave** | **fetch** | — | — |
| `academic` | **searxng** | **reddit** | **scientific_papers** | **tavily** | **exa** | **brave** | **fetch** | — |
| `social` | **reddit** | **searxng** | **tavily** | **brave** | — | — | — | — |
| `deep_scrape` | **fetch** | **webfetch** | — | — | — | — | — | — |

## Procedura

### Fase 1 — Pianificazione Query
1. Identifica l'intent della ricerca (general/academic/social/deep_scrape) basandoti sulla richiesta
2. Pianifica 3-7 sub-query diverse che coprono il tema da angolazioni distinte
3. Per ogni intent, parti DAI DUE TIER 1 GRATUITI in sequenza:
   - Prova prima searxng (tier 1a) per risultati web generali
   - Poi reddit-search (tier 1b) per discussioni social e opinioni
   - Solo dopo il fallimento di entrambi, scala a provider a pagamento

### Fase 2 — Esecuzione Multi-Provider
1. Per ogni sub-query, segui il tier ladder nell'ordine ESATTO:
   ```
   general/news: searxng(1a) → reddit(1b) → tavily(2) → exa(3) → brave(4) → fetch(5)
   social:      reddit(1a) → searxng(1b) → tavily(2) → brave(3)
    academic:    searxng(1a) → reddit(1b) → scientific_papers(2) → tavily(3) → exa(4) → brave(5) → fetch(6)
   ```
2. Se un provider fallisce (rate_limit/crediti/circuito aperto), scala immediatamente al prossimo
3. **Non saltare mai l'ordine dei tier**

### PubMed content via Scientific Papers (academic tier 2)
PubMed e' coperto da `scientific-papers-mcp` tramite la sorgente `source="europepmc"`.
Non esiste piu' un MCP server pubmed separato (RIMOSSO 2026-04-30).

Invoca tramite proxy:
```
call_tool(name="scientific-papers-mcp__search_papers", arguments={"source": "europepmc", "query": "machine learning cancer", "count": 10}, _caller_id="search-agent")
```

### Fase 3 — Deduplica e Arricchimento
1. Deduplica URL (Levenshtein title + URL canonicalization)
2. Per post Reddit rilevanti: usa `reddit-search__get_post` via proxy per ottenere l'albero commenti completo
3. Per pagine web: usa `fetch__fetch` via proxy per estrarre contenuto full-text
4. Classifica per rilevanza e data

### Fase 4 — Sintesi Report
1. Sintesi report con sezioni: TL;DR, Findings, Open Questions, Sources
2. Per fonti Reddit: cita subreddit, autore, punteggio updoot
3. Salva report in memoria episodica con tag `research_report`
4. Aggiorna wiki con `aria-memory__wiki_update_tool` per scoperte significative

## Invarianti (SOTA April 2026)
- **Cita SEMPRE le fonti con URL completo** — anche per post Reddit usa permalink
- **Se fonti contraddittorie**, riportale entrambe con contesto
- **Se meno di 3 fonti trovate**, dichiara "ricerca povera" nel report
- **Rate limiting**: rispetta i limiti impliciti — non fare piu di 1 richiesta Reddit al secondo
- **Privacy**: Reddit e read-only. Non postare mai contenuti su Reddit.
- **Fallback**: Se tutti i provider di un intent falliscono, entra in modalita `degraded`
