---
name: memory-distillation
version: 1.0.0
description: Invoca CLM su range temporale o sessione specifica
trigger-keywords: [distilla, compatt, consolidate, memory, memoria]
user-invocable: false
allowed-tools:
  - aria-memory_recall_episodic
  - aria-memory_distill
max-tokens: 15000
estimated-cost-eur: 0.03
---

# Memory Distillation Skill

## Obiettivo
Attivare il Context Lifecycle Manager su un range temporale o sessione.

## Utilizzo
Skill di sistema invocata automaticamente post-sessione o via scheduler.

## Procedura
1. Identifica sessioni da processare (ultime N chiuse)
2. Per ogni sessione:
   a. Recall episodic entries
   b. Distill in semantic chunks
   c. Apply actor tagging
3. Aggiorna statistics

## Invarianti
- Mai sovrascrivere T0 raw
- Actor=agent_inference confidence < 0.7 → review queue
- Distillation is async, non blocking
