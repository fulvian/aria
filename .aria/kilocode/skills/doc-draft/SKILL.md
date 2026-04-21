---
name: doc-draft
version: 1.0.0
description: Redige bozza Google Docs a partire da input utente + contesto memoria
trigger-keywords: [bozza, doc, scrivi documento, crea documento, redige]
user-invocable: true
allowed-tools:
  - google_workspace/drive.create_file
  - google_workspace/docs.write
  - google_workspace/docs.read
  - aria-memory/recall
  - aria-ops/hitl_ask
---

# Doc Draft Skill

## Obiettivo
Generare bozza Google Docs da input utente, usando contesto dalla memoria.

## Procedura
1. Recupera contesto da memoria via `aria-memory/recall` (sessioni recenti, decisioni)
2. Genera bozza markdown + proponi titolo
3. HITL "Crea doc '<titolo>' in Drive? [Sì] [Modifica titolo] [Annulla]"
4. `drive.create_file(mimeType='application/vnd.google-apps.document')` → `docs.write` con contenuto
5. Reply con link Drive al documento creato

## HITL Obbligatorio
Prima di creare documento, chiedere conferma all'utente.

## Invarianti
- NON sovrascrivere documenti esistenti
- Titolo del doc deve essere concordato con utente

## Output
Link Drive al documento creato.
