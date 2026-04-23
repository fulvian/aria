---
title: LLM Wiki Paradigm — External Knowledge
sources:
  - docs/foundation/fonti/Analisi Approfondita LLM Wiki.md
last_updated: 2026-04-23
tier: 1
---

# LLM Wiki Paradigm — Riferimenti Esterni

> Sintesi della fonte esterna `docs/foundation/fonti/Analisi Approfondita LLM Wiki.md`.
> Questo documento informa l'approccio wiki di ARIA.

## Concetto Fondamentale (Karpathy, Aprile 2026)

Il pattern "LLM Wiki" (Andrej Karpathy) applica il paradigma della compilazione del codice alla conoscenza testuale. Invece di eseguire "codice sorgente" (documenti grezzi) tramite RAG ad ogni query, un LLM "compila" le fonti in un artefatto strutturato: una Wiki di file Markdown interconnessi, ottimizzati per consultazione rapida.

### Tripartizione Strutturale

| Livello | Funzione | Permessi LLM |
|---------|----------|-------------|
| **Raw Sources** | Ground truth immutabile | Sola lettura |
| **The Wiki** | Conoscenza sintetizzata, interconnessa | Lettura + Scrittura |
| **The Schema** | Governance (convenzioni, tassonomia) | Sola lettura |

### File Speciali

1. **`index.md`**: Catalogo orientato al contenuto, mappa di tutte le pagine con riassunti e tag
2. **`log.md`**: Registro cronologico append-only di ogni operazione (ingest, modifica, interrogazione)

### Triade Operativa

- **Ingest**: "Compilazione" — le fonti grezze vengono analizzate, entità estratte, wiki aggiornata incrementalmente con backlink
- **Query**: Interrogazione diretta dell'artefatto pre-compilato (non dei raw), latenza ridotta
- **Lint**: Manutenzione asincrona — pagine orfane, riferimenti rotti, discrepanze, lacune informative

## Implementazioni di Riferimento

### nvk/llm-wiki (headless, developer-oriented)
- Orchestrazione multi-agente con parallelizzazione asincrona (`--plan` flag)
- 5 agenti (Standard), 8 (Deep), 10 (Retardmax) con personalità algoritmiche diverse
- Scrittura sandbox per prevenire race conditions in ingestione parallela
- "Thesis-Driven Research" con agenti antagonistici per stress-test ipotesi
- 84+ asserzioni strutturali nei test

### nashsu/llm_wiki (desktop, Tauri v2)
- App desktop Tauri (Rust) + React 19 + TypeScript
- IDE a tre colonne con visualizzazione grafi (sigma.js + ForceAtlas2)
- Pipeline ingestione: PDF (pdf-extract), DOCX (docx-rs), XLSX (calamine)
- Chain-of-Thought a 2 step: analisi astratta → generazione
- SHA256 caching incrementale
- Algoritmo Louvain per community detection
- Interoperabilità Obsidian vault

### axoviq-ai/synthadoc (enterprise)
- Motore di compilazione agnostico per ecosistemi multi-agente
- Schema JSON rigoroso per output tipizzati
- Risoluzione contraddizioni: flag `status: contradicted` + coda HITL per risoluzione umana
- Community Edition v0.1.0

## Applicazione nel Contesto ARIA

La LLM Wiki di ARIA segue questo paradigma:

| Concetto Karpathy | Realizzazione ARIA |
|-------------------|-------------------|
| Raw Sources | `docs/foundation/`, `docs/foundation/decisions/`, `docs/operations/` |
| The Wiki | `docs/llm_wiki/wiki/` (questa directory) |
| The Schema | `AGENTS.md` + Blueprint §16 (Ten Commandments) |
| `index.md` | `docs/llm_wiki/wiki/index.md` |
| `log.md` | `docs/llm_wiki/wiki/log.md` |
| Ingest | Manuale/orchestrata: raw docs → wiki pages |
| Query | Consultazione wiki pages da parte di agenti LLM |
| Lint | Verifica cross-reference, provenienza, aggiornamento |

### Mapping Tier

| LLM Wiki Tier | ARIA Memory Tier |
|---------------|-----------------|
| Raw Sources | T0 (verbatim, immutabile) |
| The Wiki | T1 (sintesi derivate, ricostruibili) |

*source: `docs/foundation/fonti/Analisi Approfondita LLM Wiki.md`*
