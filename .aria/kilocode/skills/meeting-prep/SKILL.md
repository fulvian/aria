---
name: meeting-prep
version: 2.0.0
description: "Briefing pre-meeting da evento calendario. Aggrega: descrizione evento, partecipanti (storia conversazioni), allegati Drive (ingested), contesto wiki. Usa il proxy MCP per Google Workspace."
trigger-keywords:
  - prepara meeting
  - briefing meeting
  - prep evento
  - prep call
  - prep call cliente
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - aria-memory__wiki_recall_tool
  - aria-memory__wiki_update_tool
  - office-ingest
  - spawn-subagent
max-tokens: 10000
estimated-cost-eur: 0.05
---

# Meeting Prep

## Obiettivo
Produrre brief 1 pagina markdown per prep meeting/call.

## Proxy invocation rule

Tutte le chiamate ai backend MCP passano dal proxy. Ogni chiamata deve includere
`_caller_id: "productivity-agent"`. Le chiamate Google Workspace passano dallo
stesso proxy — non serve più delegare a workspace-agent per operazioni singole.

## Procedura
1. Parsing input utente: data/ora evento + parole chiave (cliente, progetto).
2. Cerca evento calendario via proxy:
   `call_tool(name="google_workspace__get_events", arguments={...}, _caller_id="productivity-agent")`
   → seleziona evento.
3. Estrai partecipanti (campo `attendees`).
4. Per ogni partecipante (esterno, non self):
    - Cerca email via proxy:
      `call_tool(name="google_workspace__search_gmail_messages", arguments={"query": "from:<email> OR to:<email>", "after": "90d"}, _caller_id="productivity-agent")`
    - Sintetizza topic ricorrenti + tono interlocutore.
5. Allegati Drive dell'evento → leggi via proxy:
   `call_tool(name="google_workspace__get_drive_file_content", arguments={...}, _caller_id="productivity-agent")`
   → invoca office-ingest per l'estrazione.
6. wiki_recall su `<participant_name>` e `<keywords>` → eventuali topic/decision storici.
7. Compone brief: Profilo evento → Partecipanti (storia + tono) → Allegati key → Decisioni pending → Domande aperte.
8. Se proponi output write verso Google Workspace, apri un vero gate `hitl-queue__ask`
   prima dell'esecuzione; non sostituirlo con una semplice domanda testuale finale.

## Output
- Markdown 1 pagina (≤ 800 parole).
- Salva in `${ARIA_HOME}/.aria/runtime/briefs/meeting-<date>-<slug>.md`.
- Wiki patch opzionale `meeting-<YYYY-MM-DD>-<slug>` (kind=topic) — solo se l'utente conferma esito post-meeting.

## Invarianti
- Q9 = no auto-tagging: NON crea entity `client-<slug>` automaticamente. Crea SOLO se l'utente chiede esplicitamente "salva questo cliente in wiki".
- Tempi target: 15-30s end-to-end.
- Se partecipanti > 10: tronca a top-5 per frequenza email.
