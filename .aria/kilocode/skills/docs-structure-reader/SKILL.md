---
name: docs-structure-reader
version: 1.0.0
description: Leggere e analizzare la struttura di documenti Google Docs - intestazioni, tabelle, commenti e punti di ancoraggio modificabili
trigger-keywords: [doc, document, google docs, structure, index]
user-invocable: true
allowed-tools:
  - google_workspace_search_docs
  - google_workspace_get_doc_content
  - google_workspace_list_docs_in_folder
  - google_workspace_read_doc_comments
  - aria_memory_remember
  - aria_memory_recall
max-tokens: 50000
estimated-cost-eur: 0.10
---

# Docs Structure Reader Skill

## Obiettivo

Leggere e analizzare la struttura interna di documenti Google Docs esistenti. Estrae: mappa delle sezioni con gerarchia delle intestazioni, mappa delle tabelle con posizione e sommario del contenuto, lista dei commenti non risolti, e punti di ancoraggio editabili (posizioni di testo per modifiche). Operazione solo lettura - nessuna operazione di creazione, modifica o commento.

## Procedura

### 1. Ricerca documento

- Usare `google_workspace_search_docs` per trovare il documento target per nome
- Se il documento è in una cartella specifica, usare `google_workspace_list_docs_in_folder` per navigare
- Salvare il `document_id` del documento target

### 2. Estrazione contenuto strutturato

- Usare `google_workspace_get_doc_content` con il `document_id` per estrarre il testo completo
- Identificare la gerarchia delle intestazioni (H1, H2, H3, ecc.)
- Mappare le tabelle con posizione (riga/colonna indicativa) e sommario contenuto
- Identificare i punti di ancoraggio editabili (blocchi di testo modificabili)

### 3. Estrazione commenti

- Usare `google_workspace_read_doc_comments` per ottenere tutti i commenti
- Filtrare solo i commenti non risolti
- Estrarre autore, timestamp e contenuto testuale

### 4. Memorizzazione struttura

- Usare `aria_memory_remember` per salvare la struttura del documento con tag `docs_structure_reader`
- Memorizzare: section_map, table_map, unresolved_comments, editable_anchors

## Output Schema

```json
{
  "document_id": "<string>",
  "document_title": "<string>",
  "section_map": {
    "headings": [
      {
        "level": "<number>",
        "text": "<string>",
        "position": "<string>"
      }
    ]
  },
  "table_map": [
    {
      "position": "<string>",
      "rows": "<number>",
      "columns": "<number>",
      "content_summary": "<string>"
    }
  ],
  "unresolved_comments": [
    {
      "author": "<string>",
      "timestamp": "<string>",
      "content": "<string>",
      "position": "<string>"
    }
  ],
  "editable_anchors": [
    {
      "position": "<string>",
      "context": "<string>"
    }
  ],
  "memory_tags": ["docs_structure_reader"]
}
```

## Invarianti

- **SOLA LETTURA**: Non eseguire operazioni di creazione, modifica, o commento
- **NO create**: Non creare nuovi documenti, cartelle o contenuti
- **NO modify**: Non modificare contenuti esistenti
- **NO delete**: Non eliminare alcun elemento
- **CONSISTENCY**: Verificare che il documento esista prima di tentare l'accesso
- **MEMORY_TAG**: Tutti i dati memorizzati devono includere il tag `docs_structure_reader`
