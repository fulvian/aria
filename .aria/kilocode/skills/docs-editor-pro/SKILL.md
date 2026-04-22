---
name: docs-editor-pro
version: 1.0.0
description: Skill per operazioni supportate su Google Docs via MCP - creazione documento e lifecycle commenti con HITL obbligatorio
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
Eseguire in modo sicuro le operazioni Docs effettivamente disponibili nel toolset MCP corrente:
- creazione nuovi documenti (`google_workspace_create_doc`),
- ciclo di vita commenti (`google_workspace_create_doc_comment`, `google_workspace_reply_to_comment`, `google_workspace_resolve_comment`).

Le modifiche strutturali di contenuto (insert/delete/find-replace/batchUpdate testo) **non sono esposte** dal server MCP corrente e non devono essere simulate.

HITL obbligatorio prima di ogni operazione di scrittura.

## HITL Mandatory
**PRIMA di qualsiasi operazione di scrittura**, deve essere chiamato `aria_memory_hitl_ask` per ottenere conferma esplicita dall'utente. Non procedere mai senza conferma HITL.

## Procedura

### Fase 1: Identificazione Documento
1. Parse dell'user input per determinare il documento target
2. `google_workspace_search_docs` per trovare il documento
3. Se múltiples documenti trovati, chiedere all'utente di specificare quale

### Fase 2: Read Pre-Action (OBBLIGATORIO)
1. `google_workspace_get_doc_content` per leggere stato attuale
2. Generare summary dello stato corrente
3. Identificare punti/ancore per eventuali commenti

### Fase 3: Diff Preview
1. Calcolare e presentare il piano operativo supportato
2. Mostrare:
   - Azione (`create_doc` oppure `comment_lifecycle`)
   - Documento target e anchor di commento
   - Numero di operazioni che verranno eseguite

### Fase 4: HITL Confirmation
1. Chiamare `aria_memory_hitl_ask` con:
   - Riassunto delle modifiche
   - Diff preview completo
   - Richiesta esplicita di approvazione
2. Attendere conferma prima di procedere

### Fase 5: Apply Changes
Solo dopo HITL confermato:
1. Per nuovi documenti: `google_workspace_create_doc`
2. Per commenti: `google_workspace_create_doc_comment` / `google_workspace_reply_to_comment`
3. Per resolve: `google_workspace_resolve_comment`

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
  "status": "success|pending_hitl|error|unsupported_operation",
  "document": {
    "id": "string",
    "title": "string",
    "url": "string"
  },
  "operation_summary": {
    "operation_type": "create_doc|create_comment|reply_comment|resolve_comment",
    "operations_count": number,
    "comments_added": number,
    "comments_resolved": number
  },
  "current_state": "string (summary)",
  "proposed_changes": "string (plan format)",
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

1. **ALWAYS read before write**: Mai eseguire write senza aver prima letto lo stato attuale del documento
2. **ALWAYS present plan before HITL**: Mostrare sempre preview delle azioni supportate prima della conferma
3. **ALWAYS verify post-write**: Dopo ogni write, verificare che sia stato applicato correttamente
4. **No batch > 10**: Nessuna batch operation può superare le 10 operazioni senza explicit user consent
5. **HITL before write**: Obbligatorio attendere conferma HITL prima di qualsiasi write
6. **Document existence check**: Verificare sempre che il documento esista prima di tentare modifiche
7. **Comment threading**: Reply to comment deve specificare il comment_id parent
8. **Unsupported ops blocked**: Richieste di editing testo non supportate devono tornare `unsupported_operation` con guidance esplicita

## Error Handling

- Documento non trovato: chiedere all'utente di verificare il titolo
- Permission denied: riportare errore con suggerimento di check permissions
- Concurrent edit: segnalare conflitto e proporre retry
- HITL timeout: dopo 5 minuti senza risposta, chiedere se continuare
