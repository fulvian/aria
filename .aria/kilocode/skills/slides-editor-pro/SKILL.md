---
name: slides-editor-pro
version: 1.0.0
description: Skill per operazioni di modifica batch su presentazioni Google Slides - crea, legge, aggiorna presentazioni e gestisce commenti con approvazione HITL obbligatoria.
trigger-keywords:
  - slides
  - edit
  - modify
  - presentation
  - batch
  - update
  - google slides
  - commenti slides
user-invocable: true
allowed-tools:
  - google_workspace_get_presentation
  - google_workspace_create_presentation
  - google_workspace_batch_update_presentation
  - google_workspace_create_presentation_comment
  - google_workspace_reply_to_presentation_comment
  - google_workspace_resolve_presentation_comment
  - aria_memory_remember
  - aria_memory_recall
  - aria_memory_hitl_ask
max-tokens: 60000
estimated-cost-eur: 0.20
---

# Slides Editor Pro Skill

## Obiettivo

Skill specializzato per operazioni di modifica batch su presentazioni Google Slides. Gestisce aggiornamenti atomici di testo e stili, modifiche strutturali delle slide e gestione commenti. Tutte le operazioni di scrittura richiedono approvazione HITL esplicita prima dell'applicazione.

## HITL Mandatory

**OBBLIGATORIO**: Prima di qualsiasi operazione `batch_update_presentation`, lo skill DEVE invocare `aria_memory_hitl_ask` per ottenere conferma esplicita dall'utente. Le operazioni di scrittura non vengono mai eseguite senza approvazione umana.

Flow obbligatorio:
1. Leggere la presentazione corrente (`get_presentation`)
2. Presentare il riepilogo delle operazioni batch proposte
3. Chiamare `aria_memory_hitl_ask` con tutte le modifiche pianificate
4. Attendere conferma esplicita dell'utente
5. Solo dopo approvazione, applicare tutte le modifiche atomicamente
6. Verificare con una lettura post-modifica

## Procedura

### Fase 1: Analisi e Lettura
- Ottenere la presentazione corrente tramite `get_presentation`
- Identificare: slide count, layout, elementi modificabili
- Costruire il diff delle modifiche proposte

### Fase 2: HITL Approval
- Chiamare `aria_memory_hitl_ask` con:
  - Riepilogo stato corrente
  - Lista operazioni batch dettagliata
  - Rischi e impatti delle modifiche
  - Request di approvazione esplicita
- Non procedere senza conferma

### Fase 3: Applicazione Atomica
- Eseguire `batch_update_presentation` con tutte le operazioni
- Le modifiche sono atomiche: tutte o nessuna
- Loggare ogni operazione applicata

### Fase 4: Verifica
- Leggere nuovamente la presentazione per validazione
- Confrontare risultato con operazioni pianificate
- Segnalare eventuali discrepanze

### Fase 5: Memory Tagging
- Salvare risultato con tag `slides_editor_pro`
- Registrare operazioni eseguite per audit trail

## Output Schema

```json
{
  "status": "success|pending_approval|error",
  "presentation_id": "string",
  "analysis": {
    "slide_count": "number",
    "layouts_detected": ["string"],
    "elements_modifiable": "number"
  },
  "proposed_operations": [
    {
      "type": "text_update|style_update|structural_edit|comment",
      "slide_index": "number",
      "target_element": "string",
      "current_value": "string",
      "proposed_value": "string"
    }
  ],
  "hitl_status": {
    "requested": "boolean",
    "approved": "boolean",
    "timestamp": "ISO8601"
  },
  "applied_operations": [
    {
      "operation_id": "string",
      "status": "applied|failed",
      "verification": "passed|failed"
    }
  ],
  "memory_tag": "slides_editor_pro"
}
```

## Invarianti

1. **Lettura obbligatoria**: Mai scrivere senza aver prima letto lo stato corrente
2. **Atomicità batch**: Applicare modifiche in un'unica `batch_update_presentation`; in caso errore, riportare esito senza assumere rollback implicito
3. **Limite operazioni**: Massimo 20 operazioni per batch senza consenso esplicito
4. **Integrità slide**: L'ordine e layout delle slide DEVE essere preservato
5. **HITL obbligatorio**: Qualsiasi `batch_update` richiede `aria_memory_hitl_ask` preventiva
6. **Verifica post-write**: Sempre leggere dopo aver scritto per validazione
7. **Tag memory**: Tutte le operazioni taggate con `slides_editor_pro` per tracciabilità

## Error Handling

- Fallimento lettura: Restituire errore e non procedere
- HITL rifiutato: Annullare operazioni e loggare rifiuto
- Fallimento batch: Tentare rollback e segnalare errore
- Discrepanza verifica: Segnalare immediatamente e attendere istruzioni
