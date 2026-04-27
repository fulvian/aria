---
name: pdf-extract
version: 1.0.0
description: Estrazione testo e metadata da PDF documents
trigger-keywords: [pdf, documento, leggi, estrai, extract]
user-invocable: true
allowed-tools:
  - filesystem/read
  - aria-memory/wiki_update_tool
max-tokens: 5000
estimated-cost-eur: 0.01
---

# PDF Extract Skill

## Obiettivo
Estrarre il contenuto testuale da file PDF con metadata e struttura.

## Procedura
1. Verifica che il file sia un PDF valido
2. Estrai metadata (titolo, autore, date, pagine)
3. Estrai testo con struttura (paragrafi, tabelle, liste)
4. Processa immagini con OCR se necessario (fallback)
5. Salva in memoria episodica con tag `pdf_ingest`

## Output
- Full text in markdown
- Metadata dict (title, author, dates, page_count)
- Summary (2-3 frasi)
- Tags: [pdf_ingest, source_document]
