---
name: slides-content-auditor
version: 1.0.0
description: Strumento di audit per contenuti di presentazioni Google Slides - analizza inventario slide, densita testuale, copertura placeholder e integrita visiva
trigger-keywords:
  - slides
  - presentation
  - audit
  - content
  - slide
user-invocable: true
allowed-tools:
  - google_workspace_get_presentation
  - google_workspace_get_page
  - google_workspace_get_page_thumbnail
  - google_workspace_read_presentation_comments
  - aria_memory_remember
  - aria_memory_recall
max-tokens: 60000
estimated-cost-eur: 0.15
---

# Slides Content Auditor Skill

## Obiettivo

Questo skill esegue un audit completo del contenuto di una presentazione Google Slides. Fornisce un inventario strutturato delle slide, analisi della densita testuale, report sulla copertura dei placeholder e audit di immagini/grafici. Operazione **solo lettura** - non vengono eseguite operazioni di scrittura, creazione o modifica.

## Procedura

### Fase 1: Raccolta dati presentazione

1. Chiamare `google_workspace_get_presentation` con `presentation_id` per ottenere:
   - Titolo e metadata della presentazione
   - Lista di tutte le slide (slide_id, layout, position)
   - Conteggio totale slide

2. Chiamare `google_workspace_read_presentation_comments` con `presentation_id` per ottenere:
   - Tutti i commenti e relative risposte
   - Stato di risoluzione dei commenti
   - Autori e timestamp

### Fase 2: Inventario slide e analisi layout

Per ogni slide identificata:

1. Chiamare `google_workspace_get_page` con `page_id` per ottenere:
   - Titolo della slide (se presente)
   - Layout utilizzato
   - Elementi presenti (forme, immagini, tabelle, grafici)
   - Conteggio text elements e relative lunghezze

2. Opzionalmente chiamare `google_workspace_get_page_thumbnail` con `page_id` per:
   - Generare thumbnail visivo per revisione manuale
   - Verificare presenza visual di immagini/grafici

### Fase 3: Analisi densita testuale

Calcolare per ogni slide:

- **Text density score** = numero totale caratteri / area slide disponibile
- Classificare come:
  - **Sovraffollata** (text density > 0.7): troppo contenuto testuale
  - **Normale** (0.3 <= text density <= 0.7): contenuto bilanciato
  - **Sparsa** (text density < 0.3): contenuto insufficiente

Identificare slide con text density anomala.

### Fase 4: Analisi copertura placeholder

Verificare per ogni slide:

- Presenza di placeholder non compilati
- Tipo di placeholder (titolo, body, immagine, grafico, tabella)
- Layout di appartenenza

Report dei placeholder mancanti o non compilati.

### Fase 5: Audit immagini/grafici

Per ogni slide verificare:

- Presenza di immagini inline
- Presenza di grafici embeddati
- Elementi multimediali
- Segnalare slide prive di elementi visivi nonostante layout preveda immagini

### Fase 6: Consolidamento e salvataggio memoria

1. Consolidare tutti i dati raccolti nel formato di output schema
2. Chiamare `aria_memory_remember` con tag `slides_content_auditor` per salvare il report di audit
3. Restituire il report completo all'utente

## Output Schema

```json
{
  "audit_metadata": {
    "presentation_id": "string",
    "presentation_title": "string",
    "audit_timestamp": "ISO8601",
    "total_slides": "number",
    "slides_audited": "number"
  },
  "slide_inventory": [
    {
      "slide_index": "number",
      "slide_id": "string",
      "title": "string | null",
      "layout": "string",
      "text_element_count": "number",
      "character_count": "number",
      "has_thumbnail": "boolean"
    }
  ],
  "text_density_analysis": {
    "average_density": "number",
    "overcrowded_slides": [
      {
        "slide_id": "string",
        "density_score": "number",
        "recommendation": "string"
      }
    ],
    "sparse_slides": [
      {
        "slide_id": "string",
        "density_score": "number",
        "recommendation": "string"
      }
    ]
  },
  "placeholder_coverage": {
    "total_placeholders": "number",
    "filled_placeholders": "number",
    "unfilled_placeholders": [
      {
        "slide_id": "string",
        "placeholder_type": "string",
        "layout_name": "string"
      }
    ]
  },
  "media_audit": {
    "total_images": "number",
    "total_charts": "number",
    "slides_without_visuals": [
      {
        "slide_id": "string",
        "expected_from_layout": "string"
      }
    ]
  },
  "comment_resolution": {
    "total_comments": "number",
    "resolved_comments": "number",
    "unresolved_comments": [
      {
        "comment_id": "string",
        "author": "string",
        "content": "string",
        "resolved": "boolean"
      }
    ]
  }
}
```

## Invarianti

1. **Read-only**: Questo skill esegue SOLO operazioni di lettura. Non vengono chiamate funzioni di:
   - `google_workspace_create_*`
   - `google_workspace_batch_update_*`
   - `google_workspace_delete_*`
   - `google_workspace_comment_*` (solo lettura consentita)

2. **Nessuna modifica**: Nessun commento viene risolto, modificato o eliminato durante l'audit

3. **Audit mode**: Le operazioni di thumbnail sono opzionali e utilizzate solo per verifica visiva aggiuntiva

4. **Memory tagging**: Tutti i report di audit vengono salvati in memoria con il tag `slides_content_auditor`
