---
name: code-discovery
version: 1.0.0
description: Ricerca development-oriented con Context7 (docs lookup) e github-discovery (repo analysis). Usa il proxy MCP per tutte le chiamate backend.
trigger-keywords: [libreria, library, framework, sdk, package, dependency, docs, api reference, documentazione, repo, github, repository, maintained, compare, librerie]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - aria-memory__wiki_update_tool
  - aria-memory__wiki_recall_tool
max-tokens: 40000
estimated-cost-eur: 0.08
---

# Code Discovery Skill

## Obiettivo
Fornire un workflow specializzato per ricerca development-oriented:
- Docs lookup version-aware via Context7
- Repo discovery / screening / compare via github-discovery
- Fallback controllato su provider search standard ARIA

## Proxy invocation rule

Tutte le chiamate ai backend MCP passano dal proxy. Ogni chiamata deve includere
`_caller_id: "search-agent"`:

```
aria-mcp-proxy__call_tool(
  name="call_tool",
  arguments={
    "name": "<server__tool>",
    "arguments": {<tool params>},
    "_caller_id": "search-agent"
  }
)
```

Per scoprire tool disponibili:
```
aria-mcp-proxy__call_tool(
  name="search_tools",
  arguments={"query": "<descrizione>", "_caller_id": "search-agent"}
)
```

## Tier Ladder (ordine obbligatorio)

| Step | Provider | Scopo |
|------|----------|-------|
| 1 | **context7** | Docs lookup ufficiale, version-aware |
| 2 | **github-discovery** | Repo discovery, screening, assessment |
| 3 | **searxng** (general web) | Fallback ricerca web |
| 4 | **tavily** | Fallback aggiuntivo |
| 5 | **exa** | Fallback premium |
| 6 | **brave** | Fallback |
| 7 | **fetch** | Fallback deep scrape |

## Workflow

### Fase 1 — Context7 Docs Lookup
Quando l'utente chiede informazioni su una libreria, framework o package:

1. **resolve-library-id**: Usa `context7__resolve-library-id` per trovare la libreria
   ```
   arguments={"query": "<descrizione uso>", "libraryName": "<nome libreria>"}
   ```

2. **query-docs**: Una volta ottenuto il library ID, usa `context7__query-docs` per
   ottenere documentazione ufficiale e code examples
   ```
   arguments={"libraryId": "<id restituito>", "query": "<domanda specifica>"}
   ```

3. Se la libreria non viene trovata, scala immediatamente a Fase 3 (fallback).

**Importante**: Non chiamare `context7__query-docs` più di 3 volte per domanda.
Se non trovi cio che serve dopo 3 chiamate, scala a fallback.

### Fase 2 — github-discovery Repo Analysis
Quando l'utente chiede analisi/confronto di repository:

1. **discover_repos**: Cerca repository pertinenti
   ```
   arguments={"query": "<descrizione>", "max_candidates": 20}
   ```

2. **screen_candidates**: Screening qualità per filtrare candidati promettenti
   ```
   arguments={"pool_id": "<id pool>", "gate_level": "both", "max_candidates": 10}
   ```

3. **quick_assess** o **deep_assess**: Valutazione approfondita dei migliori candidati
   ```
   arguments={"repo_urls": ["<url1>", "<url2>"], "max_candidates": 3}
   ```

4. **compare_repos**: Se necessario, confronto affiancato
   ```
   arguments={"repo_urls": ["<url1>", "<url2>"]}
   ```

5. **explain_repo**: Per spiegare perché un repo ha un certo punteggio
   ```
   arguments={"repo_url": "<url>", "detail_level": "summary"}
   ```

**Note**: Usa `get_candidate_pool`, `get_shortlist`, `rank_repos` per navigare
risultati intermedi. Usa `create_session` per workflow di discovery continui.

### Fase 3 — Synthesis
Combina i risultati delle fasi precedenti in un report strutturato:

1. Docs ufficiali (da Context7) -- fonte primaria, massima autorevolezza
2. Assessment repo (da github-discovery) -- qualità, manutenzione, maturità
3. Fallback web search -- solo se i primi due non hanno dato risultati sufficienti

Formato report:
```markdown
## [Nome Libreria/Repo]

### Documentazione Ufficiale
- [fonte: Context7] <key findings, API patterns, best practices>

### Qualità Repository
- [fonte: github-discovery] <qualità score, manutenzione, issue, stars>

### Note / Alternative
- [fonte: web fallback] <se applicabile>
```

### Fase 4 — Fallback
Se uno dei backend specializzati (context7, github-discovery) non risponde:

1. Scala a searxng (ricerca web generale)
2. Se necessario, scala attraverso la tier ladder standard

**Regola**: Non dichiarare mai "integrato in ARIA" un backend che non ha
smoke test E2E verde.

## Memory / Wiki Rules

- Usa `aria-memory__wiki_recall_tool` per vedere se esistono già knowledge chunks
  su librerie o repo rilevanti.
- Massimo una `wiki_update_tool` per ricerca significativa.
- Ogni fatto deve distinguere la provenienza:
  - docs ufficiale via Context7
  - assessment repo via github-discovery
  - fallback web search
- Non memorizzare output raw completi di tool.
- Non memorizzare snippet non verificati come best practice.

## Invarianti

- **Tutte le chiamate passano dal proxy** con `_caller_id: "search-agent"`
- **Mai invocare direttamente** `context7__*` o `github-discovery__*` -- passa sempre da `aria-mcp-proxy__call_tool`
- **Provenance obbligatoria**: ogni fatto deve avere fonte tracciabile
- **Fallback**: Se un backend non risponde, scala alla tier ladder senza interrompere la ricerca
- **Limite Context7**: massimo 3 chiamate query-docs per domanda
