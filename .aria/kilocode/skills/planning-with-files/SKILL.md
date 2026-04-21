---
name: planning-with-files
version: 1.0.0
description: Pianificazione strutturata su file (task_plan.md, findings.md, progress.md)
trigger-keywords: [pianifica, piano, task, todo,工作计划]
user-invocable: true
allowed-tools:
  - filesystem/*
  - aria-memory/remember
  - aria-memory/recall
max-tokens: 10000
estimated-cost-eur: 0.02
---

# Planning with Files Skill

## Obiettivo
Creare e gestire piani strutturati su filesystem usando il pattern Manus-style.

## File generati
- `.aria/runtime/tmp/plans/<session_id>-task_plan.md`: piano principale con milestones e sub-task
- `.aria/runtime/tmp/plans/<session_id>-findings.md`: note e scoperte durante l'analisi
- `.aria/runtime/tmp/plans/<session_id>-progress.md`: stato di avanzamento aggiornato in tempo reale

## Procedura
1. Identifica l'obiettivo principale
2. Crea `task_plan.md` con struttura:
   - ## Objective
   - ## Context  
   - ## Milestones
   - ## Sub-tasks per ogni milestone
   - ## Dependencies
3. Lavora sui sub-task in parallelo dove possibile
4. Aggiorna `progress.md` dopo ogni milestone completata
5. Popola `findings.md` con insights intermedi

## Invarianti
- Un task_plan è sempre associato a una sessione o progetto specifico
- Il progresso è misurato in milestones completate, non singoli passi
- Dependencies sono rese esplicite per evitare blocchi
