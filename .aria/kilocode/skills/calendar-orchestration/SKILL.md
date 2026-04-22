---
name: calendar-orchestration
version: 1.0.0
description: Proposta slot + creazione eventi Calendar con HITL obbligatorio
trigger-keywords: [calendario, meeting, evento, pianifica, organizza incontro]
user-invocable: true
allowed-tools:
  - google_workspace_list_calendars
  - google_workspace_get_events
  - google_workspace_get_event
  - google_workspace_create_event
  - google_workspace_modify_event
  - aria_memory_remember
  - aria_memory_recall
  - aria_memory_hitl_ask
max-tokens: 20000
---

# Calendar Orchestration Skill

## Obiettivo
Proporre slot per meeting, chiedere conferma HITL, creare evento Calendar.

## Procedura
1. Parse request utente (data range, durata, attendees, titolo)
2. `google_workspace_list_calendars` + `google_workspace_get_events` per free/busy nei prossimi 7-14gg
3. Proponi 3 slot candidati (orari lavorativi, fuori quiet hours)
4. `aria_memory_hitl_ask` con inline keyboard "Scegli slot: [A] [B] [C] [annulla]"
5. Risposta A/B/C → `google_workspace_create_event` (policy `ask` ma gia approvato implicitamente da HITL scelta)
6. Salva evento id in memoria tag `calendar_event`

## HITL Obbligatorio
Prima di creare evento, chiedere sempre conferma all'utente con HITL inline keyboard.

## Output
Evento creato in Calendar con link/invite.
