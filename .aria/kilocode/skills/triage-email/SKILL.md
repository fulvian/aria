---
name: triage-email
version: 1.0.0
description: Triage giornaliero Inbox Gmail — classifica, sintetizza, evidenzia urgenti
trigger-keywords: [email, triage, inbox, riassumi mail, leggi email]
user-invocable: true
allowed-tools:
  - google_workspace/gmail.search
  - google_workspace/gmail.read
  - google_workspace/gmail.modify_labels
  - aria-memory/remember
max-tokens: 30000
estimated-cost-eur: 0.05
---

# Triage Email Skill

## Obiettivo
Leggere l'inbox Gmail delle ultime 24h, classificare per urgenza, generare digest actionable.

## Classificazione
- **Urgent**: richiede azione o risposta entro 24h (flag con label ARIA/urgent)
- **Actionable**: richiede azione ma non urgente
- **Informational**: da leggere quando possibile
- **Newsletter/Promo**: ignorabile o archiviabile

## Procedura
1. Query `gmail.search` con `q="is:unread newer_than:24h"`
2. Per ogni messaggio: `gmail.read` → estrai `from`, `subject`, `snippet`, `timestamp`
3. Classifica heuristically: newsletter / personal / work / urgent (keyword)
4. Sintesi: digest markdown con sezioni per classe
5. Per urgenti: proponi label `ARIA/urgent` → `gmail.modify_labels` (HITL `ask`)
6. Salva digest in memoria: `aria-memory/remember` actor=AGENT_INFERENCE, tag=`email_digest`
7. Reply Telegram con digest

## Invarianti
- NON eliminare email (skill hardcoded: no `gmail.delete`)
- NON inviare risposte automatiche
- Max 3 item per sezione nel digest

## Output
Digest telegram-friendly con sezioni per categoria.
