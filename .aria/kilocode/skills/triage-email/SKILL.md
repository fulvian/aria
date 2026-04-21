---
name: triage-email
version: 1.0.0
description: Triage giornaliero Inbox Gmail — classifica, sintetizza, evidenzia urgenti
trigger-keywords: [email, triage, inbox, riassumi mail, leggi email]
user-invocable: true
allowed-tools:
  - google_workspace/search_gmail_messages
  - google_workspace/get_gmail_message_content
  - google_workspace/draft_gmail_message
  - aria-memory/remember
  - aria-memory/hitl_ask
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
1. Query `search_gmail_messages` con `q="is:unread newer_than:24h"`
2. Per ogni messaggio: `get_gmail_message_content` → estrai `from`, `subject`, `snippet`, `timestamp`
3. Classifica heuristically: newsletter / personal / work / urgent (keyword)
4. Sintesi: digest markdown con sezioni per classe
5. Per urgenti: crea proposta di follow-up in bozza (`draft_gmail_message`) solo dopo `aria-memory/hitl_ask`
6. Salva digest in memoria: `aria-memory/remember` actor=AGENT_INFERENCE, tag=`email_digest`
7. Reply Telegram con digest

## Invarianti
- NON eliminare email (skill hardcoded: no `gmail.delete`)
- NON inviare risposte automatiche
- Max 3 item per sezione nel digest

## Output
Digest telegram-friendly con sezioni per categoria.
