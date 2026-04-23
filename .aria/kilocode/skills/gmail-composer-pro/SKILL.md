---
name: gmail-composer-pro
version: 1.0.0
description: Composizione e invio di email Gmail con gestione sicura di risposte thread-safe e strategie per allegati
trigger-keywords: [email, send, compose, reply, gmail, draft]
user-invocable: true
allowed-tools:
  - google_workspace_search_gmail_messages
  - google_workspace_get_gmail_message_content
  - google_workspace_draft_gmail_message
  - google_workspace_send_gmail_message
  - aria_memory_remember
  - aria_memory_recall
  - aria_memory_hitl_ask
max-tokens: 35000
estimated-cost-eur: 0.10
---

# Gmail Composer Pro Skill

## Obiettivo

Skill WRITE per la composizione, revisione e invio di email Gmail con HITL condizionale. Gestisce il contesto thread per risposte, pre-draft, verifica invio e logging in memoria.

## HITL Condizionale

Usa `aria_memory_hitl_ask` quando l'invio non e esplicitamente richiesto nel prompt corrente oppure quando il rischio e alto (destinatari multipli esterni, allegati sensibili, invii automatici/proattivi). Se l'utente rifiuta, archiviare la decisione in memoria e abortire l'invio.

## Procedura

### Step 1: Read Context
- Use `google_workspace_search_gmail_messages` per ottenere thread_id se reply a thread esistente
- Use `google_workspace_get_gmail_message_content` per estrarre:
  - References header (per thread continuity)
  - In-Reply-To header (per thread continuity)
  - Subject originale (per Reply-To prefixed "Re: ")
  - Mittente originale (per To: default)

### Step 2: Compose Draft
- Build email con:
  - To: destinatario/i
  - Subject: "Re: [original subject]" se reply, altrimenti subject nuovo
  - References: da thread precedente se esistente
  - In-Reply-To: da thread precedente se esistente
  - Body: contenuto email formattato
  - Attachments: lista file (opzionale)
- Use `google_workspace_draft_gmail_message` per creare bozza locale
- Se invio esplicitamente richiesto dall'utente e non ad alto rischio, procedere senza HITL aggiuntivo

### Step 3: HITL Confirmation (solo se richiesto)
- Call `aria_memory_hitl_ask` con:
  - action: "send_email"
  - summary: "Email a [destinatario]: [subject]"
  - details: { to, subject, body, attachments, thread_info }
- Wait per user confirmation
- Se rejected: archivia in memoria con `aria_memory_remember` tag "gmail_composer_pro" e decision "rejected"
- Se confirmed: proceed to Step 4

### Step 4: Send
- Se HITL richiesto, procedere solo dopo conferma.
- Altrimenti (richiesta esplicita e rischio normale), inviare direttamente.
- Use `google_workspace_send_gmail_message` con draft_id o costruzione diretta del messaggio
- Capture returned message_id

### Step 5: Verify
- Use `google_workspace_get_gmail_message_content` con message_id per verificare invio corretto
- Confirm: to, subject, body match intended
- Log success/failure in memoria con `aria_memory_remember`

### Step 6: Memory Archive
- Store session summary with `aria_memory_remember`
- Tags: `gmail_composer_pro`, `sent`, `thread_id` (if applicable)
- Include: message_id, timestamp, recipient, subject

## Output Schema

```json
{
  "composer_action": "draft|send|verify",
  "draft_preview": {
    "to": ["email@example.com"],
    "subject": "Re: Original Subject",
    "body": "Email body text...",
    "attachments": ["file1.pdf"],
    "thread_headers": {
      "references": "message-id-string",
      "in_reply_to": "original-message-id"
    }
  },
  "hitl_request": {
    "action": "send_email",
    "summary": "Email a email@example.com: Re: Original Subject",
    "status": "pending|confirmed|rejected"
  },
  "send_confirmation": {
    "message_id": "msg-123abc",
    "timestamp": "2026-04-22T18:59:00+02:00",
    "status": "sent|failed"
  },
  "verification": {
    "read_message_id": "msg-123abc",
    "match_expected": true,
    "to": "email@example.com",
    "subject": "Re: Original Subject",
    "status": "verified|failed"
  },
  "memory_tags": ["gmail_composer_pro", "sent"]
}
```

## Invarianti

1. **HITL by risk/intent**: `aria_memory_hitl_ask` e richiesto solo per invii impliciti, proattivi o ad alto rischio.

2. **Thread Headers Preservation**: Per reply a thread esistente:
   - References header MUST essere preservato/copiato dal messaggio originale
   - In-Reply-To header MUST essere copiato dal messaggio originale
   - Subject MUST essere prefixed "Re: " se non gia presente

3. **Attachment Validation**:
   - Verificare che file esistano prima di includere in draft
   - Indicare dimensione e tipo nella preview

4. **Send Verification**: Dopo ogni send, MUST usare `google_workspace_get_gmail_message_content` per verificare che il messaggio sia stato inviato correttamente.

5. **Memory Logging**: Ogni operazione MUST essere loggata in memoria con tag `gmail_composer_pro` per tracciabilita.

6. **No Silent Sends**: Nessun invio implicito senza consenso; richieste esplicite dell'utente valgono come consenso operativo.
