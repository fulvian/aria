---
name: hitl-queue
version: 1.0.0
description: Interfaccia gate HITL verso Telegram
trigger-keywords: [approva, conferma, HITL, human, aspetta]
user-invocable: false
allowed-tools:
  - aria-memory_stats
max-tokens: 1000
estimated-cost-eur: 0.00
---

# HITL Queue Skill

## Obiettivo
Gestire la coda di richieste che richiedono approvazione umana.

## Utilizzo
Invocata automaticamente quando un task ha policy=ask.

## Procedura
1. Crea pending HITL entry con:
   - question: cosa chiedere all'utente
   - options: scelte possibili (JSON array)
   - channel: telegram
   - expires_at: timeout (default 15 min)
2. Invia notifica Telegram con inline keyboard
3. Attendi risposta
4. Resolvi HITL entry e procedi o abort

## Gestione timeout
- Scadenza in quiet hours → defer_to_morning
- Scadenza normale → auto-deny con log
