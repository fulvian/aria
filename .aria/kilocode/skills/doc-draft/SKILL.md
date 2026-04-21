---
name: doc-draft
version: 1.0.0
description: Redige bozza Google Docs a partire da input utente + contesto memoria
trigger-keywords: [bozza, doc, scrivi documento, crea documento, redige]
user-invocable: true
allowed-tools:
  - google_workspace/create_doc
  - google_workspace/get_doc_content
  - aria-memory/recall
  - aria-memory/hitl_ask
max-tokens: 20000
---

# Doc Draft Skill

## Obiettivo
Generare bozza Google Docs da input utente, usando contesto dalla memoria.

## Procedura
1. Recupera contesto da memoria via `aria-memory/recall` (sessioni recenti, decisioni)
2. Genera bozza markdown + proponi titolo
3. HITL "Crea doc '<titolo>' in Drive? [Sì] [Modifica titolo] [Annulla]"
4. `create_doc` con titolo + contenuto bozza
5. Reply con link Drive al documento creato

## HITL Obbligatorio
Prima di creare documento, chiedere conferma all'utente.

## Invarianti
- NON sovrascrivere documenti esistenti
- Titolo del doc deve essere concordato con utente

## Output
Link Drive al documento creato.
