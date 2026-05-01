---
name: meeting-prep
version: 1.0.0
description: "Briefing pre-meeting da evento calendario. Aggrega: descrizione evento, partecipanti (storia conversazioni), allegati Drive (ingested), contesto wiki."
trigger-keywords:
  - prepara meeting
  - briefing meeting
  - prep evento
  - prep call
  - prep call cliente
user-invocable: true
allowed-tools:
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

## Procedura
1. Parsing input utente: data/ora evento + parole chiave (cliente, progetto).
2. Spawn workspace-agent → `calendar.list_events(date_range=<window>, q=<keywords>)` → seleziona evento.
3. Estrai partecipanti (campo `attendees`).
4. Per ogni partecipante (esterno, non self):
   - Spawn workspace-agent → `gmail.search(from:<email> OR to:<email>, after:90d)` → ultime N=20 email
   - Sintetizza topic ricorrenti + tono interlocutore.
5. Allegati Drive dell'evento → spawn workspace-agent → `drive.read` → URL/path locali; invoca office-ingest.
6. wiki_recall su `<participant_name>` e `<keywords>` → eventuali topic/decision storici.
7. Compone brief: Profilo evento → Partecipanti (storia + tono) → Allegati key → Decisioni pending → Domande aperte.

## Output
- Markdown 1 pagina (≤ 800 parole).
- Salva in `${ARIA_HOME}/.aria/runtime/briefs/meeting-<date>-<slug>.md`.
- Wiki patch opzionale `meeting-<YYYY-MM-DD>-<slug>` (kind=topic) — solo se l'utente conferma esito post-meeting.

## Invarianti
- Q9 = no auto-tagging: NON crea entity `client-<slug>` automaticamente. Crea SOLO se l'utente chiede esplicitamente "salva questo cliente in wiki".
- Tempi target: 15-30s end-to-end.
- Se partecipanti > 10: tronca a top-5 per frequenza email.
