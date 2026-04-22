---
name: sheets-editor-pro
version: 1.0.0
description: Modifica fogli di lavoro Google Sheets con supporto HITL: aggiornamento valori, formattazione, regole condizionali, aggiunta righe, ridimensionamento dimensioni
trigger-keywords: [sheets, edit, modify, spreadsheet, cell, format]
user-invocable: true
allowed-tools:
  - google_workspace_list_spreadsheets
  - google_workspace_get_spreadsheet_info
  - google_workspace_read_sheet_values
  - google_workspace_modify_sheet_values
  - google_workspace_create_spreadsheet
  - google_workspace_create_sheet
  - google_workspace_create_sheet_comment
  - google_workspace_reply_to_sheet_comment
  - google_workspace_resolve_sheet_comment
  - aria_memory_remember
  - aria_memory_recall
  - aria_memory_hitl_ask
max-tokens: 50000
estimated-cost-eur: 0.18
---

# Sheets Editor Pro Skill

## Obiettivo

Modifica fogli di lavoro Google Sheets in modo sicuro e tracciato. Questo skill supporta le seguenti operazioni:

- **Valori**: aggiornamento celle, append righe, cancellazione intervalli
- **Formattazione**: stile celle, colori, bordi, alignment (in combinazione con modify_sheet_values)
- **Regole condizionali**: applicazione di regole IF/THEN (via modify_sheet_values)
- **Dimensioni**: aggiunta/rimozione righe e colonne
- **Commenti**: aggiunta, reply, risoluzione commenti

Tutte le operazioni di scrittura richiedono HITL obbligatorio prima dell'applicazione.

## HITL Obbligatorio

**PRIMA di qualsiasi operazione di scrittura**, questo skill DEVE chiamare `aria_memory_hitl_ask` per ottenere conferma esplicita dall'utente. Non procedere mai con modifiche senza approvazione HITL.

## Procedura

### Step 1: Identificazione del foglio di lavoro

- Se l'utente fornisce un URL o ID specifico: usare direttamente quello.
- Se l'utente non specifica: chiamare `google_workspace_list_spreadsheets` per elencare i fogli disponibili e chiedere conferma all'utente.

### Step 2: Raccolta metadati e stato attuale

- Chiamare `google_workspace_get_spreadsheet_info` per ottenere: sheet names, named ranges, grid properties.
- Identificare il foglio e l'intervallo di interesse.

### Step 3: Lettura stato corrente (pre-edit)

- Chiamare `google_workspace_read_sheet_values` per ottenere i valori attuali delle celle nell'intervallo target.
- Registrare lo stato pre-modifica per il diff e la verifica post-applicazione.

### Step 4: Costruzione preview delle modifiche

- Presentare un riepilogo delle modifiche proposte:
  - **Intervalli coinvolti**: specificare per ogni modifica Sheet!Range (es. Foglio1!A1:B10)
  - **Valori correnti vs nuovi**: tabella diff con valore attuale → nuovo valore
  - **Tipo operazione**: UPDATE, APPEND, DELETE, FORMAT
- Se le modifiche superano i 10 range update, richiedere consenso esplicito per batch estesi.

### Step 5: HITL - Richiesta approvazione

- Chiamare `aria_memory_hitl_ask` con il riepilogo completo delle modifiche.
- Includere nell'ask:
  - Spreadsheet e foglio target
  - Lista completa degli intervalli e valori
  - Avviso che l'operazione è irreversibile senza backup
- **Non procedere** fino a ricezione approvazione esplicita.

### Step 6: Applicazione modifiche

- Dopo approvazione HITL, chiamare `google_workspace_modify_sheet_values` con i parametri approvati.
- Per operazioni batch: maximum 10 range updates per chiamata senza consenso esplicito.
- Supporta `valueInputOption` (RAW, USER_ENTERED) e `includeValuesInResponse` per verifica.

### Step 7: Verifica post-applicazione

- Chiamare `google_workspace_read_sheet_values` per confermare che i valori applicati corrispondano alle aspettative.
- Se la verifica fallisce, loggare la discrepanza e segnalare all'utente.
- Eventuali errori parziali devono essere riportati con dettaglio celle/intervalli falliti.

### Step 8: Memory storage

- Chiamare `aria_memory_remember` con tag `sheets_editor_pro` per salvare:
  - Spreadsheet ID, sheet name, timestamp operazione
  - Tipo di modifica applicata
  - Valori pre/post (per rollback manuale se necessario)
  - Esito verifica
- Usare `aria_memory_recall` per verificare precedenti modifiche allo stesso foglio (cache contestuale).

### Step 9: Gestione commenti (opzionale)

- Se richiesto dall'utente, usare `google_workspace_create_sheet_comment`, `google_workspace_reply_to_sheet_comment`, o `google_workspace_resolve_sheet_comment`.
- I commenti richiedono HITL separato prima dell'applicazione.

## Output Schema

```json
{
  "operation_type": "update|append|delete|format|comment",
  "spreadsheet_id": "<id>",
  "spreadsheet_title": "<title>",
  "sheet_name": "<sheet_name>",
  "applied_at": "<ISO8601>",
  "changes_summary": [
    {
      "range": "A1:B10",
      "operation": "UPDATE|APPEND|DELETE",
      "previous_values": "<array or null>",
      "new_values": "<array or null>",
      "verification": "PASSED|FAILED|PENDING"
    }
  ],
  "hitl_approved": true,
  "apply_confirmation": {
    "cells_affected": "<count>",
    "ranges_affected": ["<range1>", "<range2>"],
    " irreversible": true
  },
  "verification_result": {
    "status": "SUCCESS|PARTIAL|FAILED",
    "verified_ranges": ["<range1>"],
    "failed_ranges": ["<range2>"],
    "discrepancies": []
  },
  "memory_tag": "sheets_editor_pro"
}
```

## Invarianti

1. **ALWAYS read before write**: Mai chiamare `google_workspace_modify_sheet_values` senza aver prima chiamato `google_workspace_read_sheet_values` per ottenere lo stato corrente.
2. **ALWAYS present ranges before HITL**: Il riepilogo HITL deve sempre includere tutti gli intervalli coinvolti (Sheet!Range) e i valori correnti vs nuovi.
3. **HITL before any write**: Qualsiasi operazione di scrittura (modify, create, comment) richiede approvazione esplicita via `aria_memory_hitl_ask`. Non saltare mai questo step.
4. **Max 10 ranges per batch**: Più di 10 range updates richiedono consenso esplicito per batch esteso.
5. **Quota limits**: Rispettare i limiti Google Sheets API (100 richieste/minuto). Inserire delay appropriati per operazioni batch.
6. **Verify after write**: Dopo ogni modifica, chiamare `google_workspace_read_sheet_values` per confermare l'applicazione corretta.
7. **Memory tagging**: Tutti i dati salvati in memoria devono essere taggati con `sheets_editor_pro`.
8. **No overwrite without backup**: Non sovrascrivere celle con dati non letti senza aver prima letto lo stato.
9. **Comment operations need separate HITL**: Operazioni sui commenti richiedono HITL separato dall'operazione principale.
10. **User confirmation required**: L'utente deve sempre confermare i valori prima dell'applicazione, anche per modifiche apparentemente semplici.