---
name: source-dedup
version: 1.0.0
description: Deduplica fonti web e canonicalizza URL per report di ricerca
trigger-keywords: [dedup, deduplica, canonicalize, fonti duplicate]
user-invocable: false
allowed-tools:
  - fetch/fetch
---

# Source Dedup Skill

## Obiettivo
Ridurre duplicazioni nei risultati ricerca prima della sintesi.

## Procedura
1. Normalizza URL rimuovendo query tracking (`utm_*`, `fbclid`, `gclid`).
2. Unifica host (`www.` -> root) e schema (`http`/`https`) quando equivalente.
3. Confronta titolo e dominio; scarta duplicati semantici mantenendo la fonte migliore.
4. Mantieni almeno 3 domini distinti quando disponibili.

## Invarianti
- Non rimuovere fonti con tesi in conflitto: conservarle entrambe.
- In output finale includere URL canonico e URL originale se differiscono.
