---
name: docs-editor-pro
version: 1.0.0
description: Skill per modificare documenti Google Docs esistenti - modifiche di testo, gestione commenti, batch editing con HITL obbligatorio
trigger-keywords: [doc, edit, modifica, google docs, commento, aggiorna, replace, sostituisci]
user-invocable: true
allowed-tools:
  - google_workspace_search_docs
  - google_workspace_get_doc_content
  - google_workspace_create_doc
  - google_workspace_create_doc_comment
  - google_workspace_reply_to_comment
  - google_workspace_resolve_comment
  - aria_memory_remember
  - aria_memory_recall
  - aria_memory_hitl_ask
max-tokens: 50000
estimated-cost-eur: 0.15
---

# Docs Editor Pro Skill

## Obiettivo
Modificare documenti Google Docs esistenti in modo sicuro e tracciato. La skill gestisce:
- Modifiche di testo (insert, update, delete)
- Operazioni di find/replace
- Gestione tabelle (add/remove rows, update cells)
- Ciclo di vita dei commenti (create, reply, resolve)
- Batch operations (max 10 operazioni per batch)

HITL obbligatorio prima di ogni operazione di scrittura.

## HITL Mandatory
**PRIMA di qualsiasi operazione di scrittura**, deve essere chiamato `aria_memory_hitl_ask` per ottenere conferma esplicita dall'utente. Non procedere mai senza conferma HITL.

## Procedura

### Fase 1: Identificazione Documento
1. Parse dell'user input per determinare il documento target
2. `google_workspace_search_docs` per trovare il documento
3. Se múltiples documenti trovati, chiedere all'utente di specificare quale

### Fase 2: Read Pre-Edit (OBBLIGATORIO)
1. `google_workspace_get_doc_content` per leggere stato attuale
2. Generare summary dello stato corrente
3. Identificare sezioni da modificare

### Fase 3: Diff Preview
1. Calcolare e presentare le modifiche proposte in formato diff/patch
2. Mostrare:
   - Contenuto attuale
   - Contenuto proposto
   - Numero di operazioni che verranno eseguite
   - Impatto stimato (caratteri aggiunti/rimossi)

### Fase 4: HITL Confirmation
1. Chiamare `aria_memory_hitl_ask` con:
   - Riassunto delle modifiche
   - Diff preview completo
   - Richiesta esplicita di approvazione
2. Attendere conferma prima di procedere

### Fase 5: Apply Changes
Solo dopo HITL confermato:
1. Eseguire operazioni di write in ordine
2. Per commenti: `google_workspace_create_doc_comment` / `google_workspace_reply_to_comment`
3. Per resolve: `google_workspace_resolve_comment`
4. Per nuovi documenti: `google_workspace_create_doc`

### Fase 6: Verify Post-Write
1. `google_workspace_get_doc_content` per verificare modifiche applicate
2. Confrontare con diff preview originaria
3. Reportare eventuali discrepanze

### Fase 7: Memory Update
1. Chiamare `aria_memory_remember` con tag `docs_editor_pro`
2. Includere:
   - Documento modificato
   - Tipo di operazioni eseguite
   - Timestamp
   - Outcome (success/failure)

## Output Schema

```json
{
  "status": "success|pending_hitl|error",
  "document": {
    "id": "string",
    "title": "string",
    "url": "string"
  },
  "diff_summary": {
    "operations_count": number,
    "characters_added": number,
    "characters_removed": number,
    "comments_added": number,
    "comments_resolved": number
  },
  "current_state": "string (summary)",
  "proposed_changes": "string (diff format)",
  "hitl_confirmation": {
    "asked": boolean,
    "confirmed": boolean,
    "timestamp": "ISO8601"
  },
  "apply_confirmation": {
    "applied": boolean,
    "timestamp": "ISO8601"
  },
  "verification_result": {
    "verified": boolean,
    "discrepancies": ["string"]
  }
}
```

## Invarianti

1. **ALWAYS read before write**: Mai modificare senza aver prima letto lo stato attuale del documento
2. **ALWAYS present diff before HITL**: Mostrare sempre preview delle modifiche prima di chiedere conferma
3. **ALWAYS verify post-write**: Dopo ogni modifica, verificare che sia stata applicata correttamente
4. **No batch > 10**: Nessuna batch operation può superare le 10 operazioni senza explicit user consent
5. **HITL before write**: Obbligatorio attendere conferma HITL prima di qualsiasi write
6. **Document existence check**: Verificare sempre che il documento esista prima di tentare modifiche
7. **Comment threading**: Reply to comment deve specificare il comment_id parent
8. **No data loss**: Non eliminare contenuto senza backup esplicito nella memory

## Error Handling

- Documento non trovato: chiedere all'utente di verificare il titolo
- Permission denied: riportare errore con suggerimento di check permissions
- Concurrent edit: segnalare conflitto e proporre retry
- HITL timeout: dopo 5 minuti senza risposta, chiedere se continuare