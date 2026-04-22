---
name: sheets-analytics-reader
version: 1.0.0
description: Legge e analizza fogli di lavoro Google Sheets per generare un report diagnostico su schema, qualità dei dati e anomalie
trigger-keywords: [sheets, spreadsheet, analytics, table, data]
user-invocable: true
allowed-tools:
  - google_workspace_list_spreadsheets
  - google_workspace_get_spreadsheet_info
  - google_workspace_read_sheet_values
  - google_workspace_read_sheet_comments
  - aria_memory_remember
  - aria_memory_recall
max-tokens: 50000
estimated-cost-eur: 0.12
---

# Sheets Analytics Reader Skill

## Obiettivo

Legge fogli di lavoro Google Sheets e produce un report diagnostico che include: mappa dello schema (nomi fogli, intestazioni colonne, tipi di dati inferiti), controlli di qualità tabella/colonna (celle vuote, duplicati, incoerenze di tipo), flag di anomalie dati e raccomandazioni di pulizia/miglioramento. Operazione **read-only** — nessuna operazione di creazione, modifica o formattazione.

## Procedura

### Step 1: Identificazione del foglio di lavoro

- Se l'utente fornisce un URL o ID specifico: usare direttamente quello.
- Se l'utente non specifica: chiamare `google_workspace_list_spreadsheets` per elencare i fogli disponibili e chiedere conferma all'utente.

### Step 2: Raccolta metadati

- Chiamare `google_workspace_get_spreadsheet_info` per ottenere: sheet names, named ranges, protections, grid properties.
- Identificare i fogli di interesse dall'utente.

### Step 3: Analisi schema

- Per ogni foglio, chiamare `google_workspace_read_sheet_values` leggendo l'intervallo intestazioni (prima riga) e un campione di righe dati (fino a 100).
- Inferire il tipo di dati dominante per colonna (string, number, date, boolean, empty).
- Costruire la mappa dello schema: `{ sheet_name: { columns: [{ name, inferred_type, sample_values }] } }`.

### Step 4: Analisi qualità dati

- **Celle vuote**: contare celle NULL per colonna e per riga.
- **Duplicati**: identificare righe con valori duplicati su colonne chiave (se identificabili).
- **Incoerenze di tipo**: segnalare celle che non matching il tipo dominante della colonna.
- **Formato data**: validare stringhe data contro formati comuni (ISO, MM/DD/YYYY, DD/MM/YYYY).

### Step 5: Controllo commenti

- Chiamare `google_workspace_read_sheet_comments` per ogni foglio.
- Riportare commenti rilevanti che indicano annotazioni utente, TODO, o flag di qualità.

### Step 6: Raccomandazioni

- Generare raccomandazioni azionabili basate sui problemi trovati:
  - Colonne con >20% celle vuote → valutare eliminazione o default value.
  - Righe duplicate → deduplicazione suggerita.
  - Incoerenze di tipo → standardizzazione formato.
  - Formato date non uniforme → normalizzazione ISO 8601.
- Flaggare righe/colonne con anomalie per attenzione HITL prima di qualsiasi modifica.

### Step 7: Memory storage

- Chiamare `aria_memory_remember` con tag `sheets_analytics_reader` per salvare il report completo nel grafo di memoria.
- Usare `aria_memory_recall` per verificare precedenti analisi dello stesso foglio (cache contestuale).

## Output Schema

```json
{
  "spreadsheet_id": "<id>",
  "spreadsheet_title": "<title>",
  "analyzed_at": "<ISO8601>",
  "sheets": [
    {
      "name": "<sheet_name>",
      "schema": {
        "columns": [
          {
            "name": "<column_name>",
            "inferred_type": "string|number|date|boolean|empty",
            "null_count": "<count>",
            "null_percentage": "<percentage>",
            "type_inconsistencies": "<count>",
            "sample_values": ["<v1>", "<v2>"]
          }
        ]
      },
      "quality_checks": {
        "empty_rows": "<count>",
        "duplicate_rows": "<count or null>",
        "overall_quality_score": "<0-100>"
      },
      "anomaly_flags": [
        {
          "type": "empty_column|type_inconsistency|date_format|duplicate",
          "location": "A1:B10",
          "description": "<human_readable>",
          "severity": "low|medium|high"
        }
      ],
      "comments_summary": [
        {
          "cell": "A1",
          "content": "<comment_text>",
          "resolved": "<boolean>"
        }
      ]
    }
  ],
  "recommendations": [
    {
      "action": "normalize_date|deduplicate|fill_empty|standardize_type",
      "target": "<sheet_name>:<column_or_range>",
      "description": "<description>",
      "requires_hitl": "<boolean>"
    }
  ]
}
```

## Invarianti

1. **Read-only**: Questo skill NON chiama alcuna tool di scrittura. Non chiama `google_workspace_write_sheet_values`, `google_workspace_update_sheet_values`, `google_workspace_batch_update`, `google_workspace_append_values`, né alcuna tool di formattazione.
2. **Solo strumenti allowlisted**: Eseguire esclusivamente le tool elencate in `allowed-tools`.
3. **Nessun segreto esposto**: Non loggare né includere nei report eventuali credential o token presenti nei dati.
4. **HITL prima di modifiche**: Qualsiasi operazione di scrittura derivata da questo analysis richiede conferma esplicita dell'utente (HITL).
5. **Memory tagging**: Tutti i dati salvati in memoria devono essere taggati con `sheets_analytics_reader`.
