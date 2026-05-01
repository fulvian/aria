---
name: office-ingest
version: 2.0.0
description: Estrae testo, tabelle e metadata da PDF/DOCX/XLSX/PPTX/TXT/HTML/CSV in markdown LLM-ready. Sostituisce pdf-extract@1.0.0 con copertura formati estesa via markitdown-mcp.
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
  - markitdown-mcp__convert_to_markdown
  - filesystem__read
  - filesystem__list_directory
  - aria-memory__wiki_update_tool
max-tokens: 8000
estimated-cost-eur: 0.02
deprecates: pdf-extract@1.0.0
---

# Office Ingest

## Obiettivo
Convertire un file office locale (o URL pubblico) in markdown strutturato pronto per LLM.

## Procedura
1. Risolvi path: se l'utente fornisce path relativo, espandi rispetto a `${ARIA_HOME}` o cwd.
2. Verifica esistenza con `filesystem__read` (head 1KB) — se manca, errore esplicito.
3. Costruisci URI `file://<absolute_path>` o `https://...`.
4. Invoca `markitdown-mcp__convert_to_markdown(uri=<URI>)`.
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
- markitdown-mcp DOWN → fallback `filesystem__read` raw + warning "estrazione povera, no struttura".
- File corrotto → errore con suggerimento (es. "PDF criptato — fornisci password via HITL").
- Formato non supportato (es. .pages) → suggerisci conversione manuale.
