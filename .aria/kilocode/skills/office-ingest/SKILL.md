---
name: office-ingest
version: 3.0.0
description: Estrae testo, tabelle e metadata da PDF/DOCX/XLSX/PPTX/TXT/HTML/CSV in markdown LLM-ready. Usa il proxy MCP per markitdown.
trigger-keywords:
  - pdf
  - word
  - docx
  - excel
  - xlsx
  - powerpoint
  - pptx
  - leggi documento
  - estrai
  - ingest
  - parse
  - apri file
  - converti
user-invocable: true
allowed-tools:
  - aria-mcp-proxy_search_tools
  - aria-mcp-proxy_call_tool
  - aria-memory_wiki_update_tool
max-tokens: 8000
estimated-cost-eur: 0.02
deprecates: pdf-extract@1.0.0
---

# Office Ingest

## Obiettivo
Convertire un file office locale (o URL pubblico) in markdown strutturato pronto per LLM.

## Proxy invocation rule

Tutte le chiamate ai backend MCP passano dal proxy. Ogni chiamata deve includere
`_caller_id: "productivity-agent"`:

```
aria-mcp-proxy_call_tool(
  name="call_tool",
  arguments={
    "name": "markitdown-mcp_convert_to_markdown",
    "arguments": {"uri": "<URI>"},
    "_caller_id": "productivity-agent"
  }
)
```

Per operazioni filesystem:
```
call_tool(name="filesystem_read", arguments={"path": "<path>"}, _caller_id="productivity-agent")
call_tool(name="filesystem_list_directory", arguments={"path": "<path>"}, _caller_id="productivity-agent")
```

## Procedura
1. Risolvi path: se l'utente fornisce path relativo, espandi rispetto a `${ARIA_HOME}` o cwd.
   Non usare `Glob` o `Read` nativi host per discovery/lettura ordinaria: usa il
   backend filesystem via proxy.
2. Verifica esistenza con `filesystem_read` via proxy (head 1KB) — se manca, errore esplicito.
3. Costruisci URI `file://<absolute_path>` o `https://...`.
4. Invoca `markitdown-mcp_convert_to_markdown` via proxy con `_caller_id: "productivity-agent"`.
5. Estrai metadata da output (markitdown emette un blocco YAML con title/author/date dove disponibili).
6. Se output > max-tokens: trunca con marker `[...truncated, N pagine residue...]` e suggerisci scope (range pagine).
7. Salva in wiki ARIA solo se l'utente esplicitamente lo richiede (es. "salva il riassunto"); default no_salience_reason="tool_only".

## Output
- Markdown body con sezioni preservate (headings, tabelle, liste).
- Metadata dict: {file_path, format, title?, author?, page_count?, byte_size, sha256}.
- Tag opzionali: [office_ingest, source_document].

## Invarianti
- Mai modificare il file originale.
- Mai uploadare a servizi esterni se non esplicito (Q5: OCR off).
- Per documenti > 50 MB: warning + prompt HITL prima di proseguire.
- File con dati sensibili (parole chiave: "contratto", "riservato", "confidential") → nota di sicurezza nel summary.

## Failure modes
- markitdown-mcp DOWN → fallback `filesystem_read` raw via proxy + warning "estrazione povera, no struttura".
- File corrotto → errore con suggerimento (es. "PDF criptato — fornisci password via HITL").
- Formato non supportato (es. .pages) → suggerisci conversione manuale.
