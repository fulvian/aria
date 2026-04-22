---
name: gmail-thread-intelligence
version: 1.0.0
description: Analisi completa thread Gmail — timeline, partecipanti, allegati, azioni candidate, risk flags
trigger-keywords: [thread, gmail, conversazione, email, allegati, catena]
user-invocable: true
allowed-tools:
  - google_workspace_search_gmail_messages
  - google_workspace_get_gmail_message_content
  - aria_memory_remember
  - aria_memory_recall
max-tokens: 40000
estimated-cost-eur: 0.08
---

# Gmail Thread Intelligence Skill

## Obiettivo
Dato un thread ID o query di ricerca, estrarre timeline completa, identificare partecipanti con ruoli, analizzare allegati, proporre azioni candidate e segnalare risk flags. Output strutturato per decision-making rapido.

## Procedura
1. Query `google_workspace_search_gmail_messages` con `q="is:thread FROM:<sender> subject:<subject>"` o `q="<thread_id>"`
2. Per ogni messaggio nel thread: `google_workspace_get_gmail_message_content` → estrai `from`, `to`, `cc`, `subject`, `timestamp`, `body`, `attachments`
3. Ricostruisci timeline cronologica ordinando per timestamp
4. Identifica ruoli partecipanti: sender, reply-all, sole-replier, cross-participant
5. Estrai allegati: filename, size, type, has-context (presente nel body)
6. Genera action candidates: reply, reply-all, forward, archive, label, move
7. Calcola risk flags: external senders, attachment senza contesto, BCC recipients, links sospetti
8. Salva in memoria: `aria_memory_remember` actor=AGENT_INFERENCE, tag=`gmail_thread_intelligence`
9. Output structurato markdown

## Output Schema

```json
{
  "thread_id": "<gmail-thread-id>",
  "subject": "<subject>",
  "message_count": <n>,
  "timeline": [
    {
      "index": 0,
      "from": "<email>",
      "to": "<emails>",
      "cc": "<emails>",
      "timestamp": "<ISO8601>",
      "snippet": "<first-100-chars>",
      "has_attachments": true,
      "attachment_count": 0
    }
  ],
  "participants": [
    {
      "email": "<email>",
      "name": "<name>",
      "message_count": <n>,
      "role": "sender|reply-all|sole-replier|cross-participant"
    }
  ],
  "attachments": [
    {
      "filename": "<name.ext>",
      "size_bytes": <n>,
      "mime_type": "<type>",
      "has_context_in_body": true
    }
  ],
  "action_candidates": [
    {
      "action": "reply|reply-all|forward|archive|label",
      "priority": "high|medium|low",
      "reason": "<why>"
    }
  ],
  "risk_flags": [
    {
      "flag": "external_sender|attachment_no_context|bcc_recipient|suspicious_link|no_subject",
      "severity": "high|medium|low",
      "detail": "<specific>"
    }
  ]
}
```

## Invarianti
- NON eliminare email (skill hardcoded: no delete operations)
- NON inviare risposte automatiche
- NON modificare allegati o creare bozze
- SOLO lettura e analisi del thread
- Max 50 messaggi per thread (alert se superiore)
