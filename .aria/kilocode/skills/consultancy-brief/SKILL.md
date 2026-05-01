---
name: consultancy-brief
version: 1.0.0
description: Sintesi executive multi-documento per workflow consulente. Compone outline strutturato (TL;DR, contesto, findings, decisioni, open questions) da N file ingested + contesto wiki.
trigger-keywords:
  - briefing
  - executive summary
  - sintesi cliente
  - riepilogo dossier
  - dossier
  - sintesi documenti
user-invocable: true
allowed-tools:
  - office-ingest
  - aria-memory__wiki_recall_tool
  - aria-memory__wiki_update_tool
  - planning-with-files
max-tokens: 20000
estimated-cost-eur: 0.10
---

# Consultancy Brief

## Obiettivo
Produrre brief executive (1-3 pagine markdown) integrando N documenti + storia wiki.

## Procedura
1. Identifica i file in input (path list o glob pattern).
2. Per ogni file: invoca `office-ingest` skill (nested).
3. Recupera contesto wiki: `wiki_recall_tool(query=<topic+entità>)`.
4. Pianifica outline con `planning-with-files`:
   - sezioni: TL;DR (3-5 bullet) → Contesto → Findings → Decisioni pending → Aperti / next steps → Sources.
5. Sintetizza ogni sezione (max 200 parole, citando fonte file:lineblock o pagina dove applicabile).
6. Genera output markdown finale.
7. Default no_salience_reason="recall_only" se nessun fatto nuovo emerge; altrimenti propone topic patch.

## Output
- File markdown brief (in cwd o `${ARIA_HOME}/.aria/runtime/briefs/<timestamp>-<slug>.md`).
- Lista citazioni fonti.

## Invarianti
- Mai inventare dati: se 3+ fonti contraddittorie, riportale tutte.
- Se < 2 fonti totali: avvisa "brief povero" e raccomanda search-agent.
- Cita SEMPRE i file con path relativo + sezione/pagina.
