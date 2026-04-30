# Agent Capability Matrix — Canonical Reference

**Version**: 1.0.0  
**Last Updated**: 2026-04-29  
**Status**: Active  
**Source**: `.aria/kilocode/agents/*.md`, `src/aria/agents/search/router.py`, `docs/llm_wiki/wiki/*`

## Purpose

Matrixe canonica delle capability cross-agent, protocollo di handoff e routing
policy unificata, sincronizzata tra agent YAML definitions, MCP config, router
code e LLM Wiki (§2.5 del piano di ottimizzazione).

## 1) Capability Matrix

| Agent | Type | Allowed Tools | MCP Dependencies | Delegation Targets | HITL Required | Intent Categories |
|-------|------|--------------|------------------|-------------------|---------------|------------------|
| **aria-conductor** | primary (orchestrator) | 12 (4 wiki + 4 HITL + 2 legacy + seq-thinking + spawn-subagent) | `aria-memory` | search-agent, workspace-agent, productivity-agent | Su decisioni distruttive/costose | N/A (dispatch-only) |
| **search-agent** | subagent (research) | 23 (6 provider MCP + 2 wiki + fetch) | `tavily-mcp, brave-mcp, exa-script, searxng-script, reddit-search, scientific-papers-mcp` | Nessuna (leaf agent) | No | general/news, academic, social, deep_scrape |
| **workspace-agent** | subagent (productivity) | 8 (5 Google Workspace patterns + 2 wiki + HITL) | `google_workspace` | Nessuna (leaf agent) | Su write Gmail/Drive | Operazioni Gmail/Calendar/Drive/Docs/Sheets |
| **productivity-agent** | subagent (productivity) | 11 (markitdown + filesystem + 4 wiki + HITL + fetch + seq-thinking + spawn-subagent) | `markitdown-mcp, aria-memory, filesystem` | workspace-agent (2-hop delega per Gmail/Calendar/Drive) | Su write wiki immutable (decision/lesson), send mail via workspace-agent | Office ingestion, briefing, meeting prep, email draft |

### Dettaglio Allowed Tools per Agente

**aria-conductor** (12):
- `aria-memory/*` (4: wiki_update, wiki_recall, wiki_show, wiki_list)
- `aria-memory/*` (2 legacy: forget, stats)
- `aria-memory/hitl_*` (4: ask, list_pending, cancel, approve)
- `sequential-thinking/*`
- `spawn-subagent`

**search-agent** (28):
- `searxng-script/search` (1)
- `tavily-mcp/search` (1)
- `exa-script/search` (1)
- `brave-mcp/*` (2: web_search, news_search)
- `reddit-search/*` (6: search, search_subreddit, get_post, get_subreddit_posts, get_user, get_user_posts)
- `pubmed-mcp/*` (RIMOSSO 2026-04-30: coperto da scientific-papers-mcp/source="europepmc")
- `scientific-papers-mcp/*` (5: search_papers, fetch_content, fetch_latest, list_categories, fetch_top_cited)
- `aria-memory/*` (2: wiki_update, wiki_recall)
- `fetch/fetch` (1)

**workspace-agent** (8):
- `google_workspace/gmail.*` (pattern)
- `google_workspace/calendar.*` (pattern)
- `google_workspace/drive.*` (pattern)
- `google_workspace/docs.*` (pattern)
- `google_workspace/sheets.*` (pattern)
- `aria-memory/*` (2: wiki_update, wiki_recall)
- `hitl-queue/ask` (1)

**productivity-agent** (11):
- `markitdown-mcp/convert_to_markdown` (1)
- `filesystem/*` (2: read, list_directory)
- `aria-memory/*` (4: wiki_update, wiki_recall, wiki_show, wiki_list)
- `hitl-queue/ask` (1)
- `fetch/fetch` (1)
- `sequential-thinking/*` (1)
- `spawn-subagent` (1)

## 2) Protocollo Handoff Standardizzato

Quando conductor (o productivity-agent) delega un task a un sub-agente via
`spawn-subagent`, il payload JSON DEVE seguire questo formato minimo:

```json
{
  "goal": "string — descrizione del task da eseguire (obbligatorio, max 500 char)",
  "constraints": "string — vincoli specifici (opzionale, es. 'usa solo fonti accademiche')",
  "required_output": "string — formato atteso del risultato (opzionale, es. 'lista di 5 paper con titolo, autore, DOI')",
  "timeout_seconds": "number — timeout in secondi (opzionale, default: 120)",
  "trace_id": "string — trace ID per correlazione log (obbligatorio)",
  "parent_agent": "string — agente chiamante (obbligatorio)",
  "spawn_depth": "number — profondita corrente della catena (default: 1, max: 2)",
  "envelope_ref": "string — riferimento al ContextEnvelope condiviso (opzionale)"
}
```

### Esempi di handoff

**Conductor → search-agent**:
```json
{
  "goal": "Cerca ultimi paper su Mamba state space models per update survey",
  "constraints": "usa intent=academic, dai priorità a pubmed e scientific_papers",
  "required_output": "lista di 5 paper con titolo, autori, anno, DOI, fonte",
  "timeout_seconds": 180,
  "trace_id": "trace_search_academic_001",
  "parent_agent": "aria-conductor",
  "spawn_depth": 1
}
```

**Conductor → productivity-agent**:
```json
{
  "goal": "Leggi il file PDF in docs/reports/Q1-2026-report.pdf e produci un executive summary",
  "constraints": "usa office-ingest skill, output in italiano",
  "required_output": "brief markdown con TL;DR, contesto, findings, open questions",
  "timeout_seconds": 300,
  "trace_id": "trace_productivity_001",
  "parent_agent": "aria-conductor",
  "spawn_depth": 1
}
```

**Productivity-agent → workspace-agent** (2-hop delega):
```json
{
  "goal": "Invia email al cliente con allegato il brief appena generato",
  "constraints": "usa gmail, destinatario: cliente@example.com, oggetto: 'Report Q1 2026'",
  "required_output": "conferma invio con message_id",
  "timeout_seconds": 60,
  "trace_id": "trace_workspace_001",
  "parent_agent": "productivity-agent",
  "spawn_depth": 2,
  "envelope_ref": "env_123"
}
```

### Regole handoff

1. Il mittente DEVE attendere il risultato del sub-agente prima di proseguire
2. Se il sub-agente fallisce (timeout/errore), il mittente DEVE gestire il fallimento
   (es. fallback ad altro agente, degraded mode, o notifica HITL)
3. `trace_id` DEVE essere propagato dal conductor attraverso tutta la catena
4. Il sub-agente NON DEVE modificare lo stato globale (es. wiki pages) senza HITL
   se non autorizzato esplicitamente dal mittente

## 3) Routing Policy Unificata

Criteri che conductor usa per selezionare il sub-agente appropriato:

| Condizione | Agente primario | Note |
|------------|-----------------|------|
| **Ricerca informazioni online** | `search-agent` | Per news, accademiche, social, deep scrape. Usa intent classification automatica. |
| **File office locale** (PDF/DOCX/XLSX/PPTX/TXT/HTML) | `productivity-agent` | Ingestion via markitdown-mcp, nessuna API key richiesta. |
| **Briefing multi-documento** | `productivity-agent` | Sintesi executive con outline strutturato. |
| **Preparazione meeting** | `productivity-agent` | Briefing pre-meeting con contesto wiki. |
| **Bozze email** | `productivity-agent` | Stile dinamico per-recipient, nessuna lesson statica. |
| **Gmail/Calendar/Drive/Docs/Sheets** | `workspace-agent` | Richiede OAuth Google già configurato. |
| **Task misti** (es. "leggi PDF e invia email") | `productivity-agent` → delega `workspace-agent` | 2-hop: productivity-agent spawna workspace-agent per write. |
| **Analisi + report** (es. "cerca notizie e scrivi report") | `search-agent` + `productivity-agent` | Chain: conductor raccoglie dati da search-agent, poi passa a productivity-agent per sintesi. |
| **Ricerca accademica + briefing** (es. "cerca paper su X e riassumi") | `search-agent` (academic intent) + `productivity-agent` | Chain: conductor spawna search-agent, poi passa risultati a productivity-agent per sintesi. |
| **Operazioni su memoria/wiki** | `aria-conductor` diretto | Usa i 4 wiki MCP tools (wiki_update, wiki_recall, wiki_show, wiki_list). |

### Catene di dispatch

Per task compositi, conductor PUO usare catene sequenziali:

```
1. Ricerca → Sintesi:
   search-agent → productivity-agent

2. File office → Email:
   productivity-agent → workspace-agent

3. Ricerca accademica → Briefing → Condivisione:
   search-agent → productivity-agent → workspace-agent

4. Meeting prep → Drive upload:
   productivity-agent → workspace-agent
```

### Limiti operativi

- **Timeout default spawn-subagent**: 120 secondi
- **Timeout massimo**: 300 secondi (task di ricerca complessi)
- **Profondità catena massima**: 2 hop (conductor → agente A → agente B)
- **Nesting massimo**: conductor NON deve spawnare agenti che a loro volta spawnano altri agenti (profondità 2 massima)

## 4) Provenance

- Source: `.aria/kilocode/agents/aria-conductor.md` (read 2026-04-29)
- Source: `.aria/kilocode/agents/search-agent.md` (read 2026-04-29)
- Source: `.aria/kilocode/agents/productivity-agent.md` (read 2026-04-29)
- Source: `.aria/kilocode/agents/workspace-agent.md` (read 2026-04-29)
- Source: `docs/llm_wiki/wiki/research-routing.md` (read 2026-04-29)
- Source: `src/aria/agents/search/router.py` (read 2026-04-29)
- Source: ~~Context7 `/cyanheads/pubmed-mcp-server` (queried 2026-04-29, removed 2026-04-30)~~
- Source: Context7 `/benedict2310/scientific-papers-mcp` (queried 2026-04-29)
