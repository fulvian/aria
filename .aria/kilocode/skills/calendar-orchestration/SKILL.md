---
name: calendar-orchestration
version: 1.0.0
description: Proposta slot + creazione eventi Calendar con HITL condizionale
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
Proporre slot per meeting e creare evento Calendar con gate HITL solo quando necessario.

## Procedura
1. Parse request utente (data range, durata, attendees, titolo)
2. `google_workspace_list_calendars` + `google_workspace_get_events` per free/busy nei prossimi 7-14gg
3. Proponi 3 slot candidati (orari lavorativi, fuori quiet hours)
4. Se la creazione non e esplicitamente richiesta o e ad alto rischio, usa `aria_memory_hitl_ask` con inline keyboard
5. Applica `google_workspace_create_event` dopo conferma esplicita o quando autorizzazione e gia implicita nel prompt utente
6. Salva evento id in memoria tag `calendar_event`

## HITL Condizionale
Per richieste esplicite dell'utente (es. "crea evento domani alle 10"), l'autorizzazione e gia presente.
Usare HITL per creazioni implicite/proattive o potenzialmente distruttive.

## Output
Evento creato in Calendar con link/invite.
