# Piano di Implementazione — Remediation Gap Memory Embedding

**Data**: 2026-03-30  
**Stato**: Proposto  
**Priorità**: P0 (bloccante funzionale)  
**Input di riferimento**: `docs/issues/memory-embedding-gap.md`

## 1. Executive Summary

L’analisi completa della codebase conferma che il sistema memoria ARIA è operativo nei 4 layer, ma la ricerca semantica è assente end-to-end: non esiste generazione embedding nel layer provider, non esiste persistenza vettoriale reale, e il retrieval “simile” usa keyword matching (`strings.Contains`) con fallback recency.

Conseguenza: la memoria episodica non generalizza parafrasi/riformulazioni e non soddisfa quanto previsto dal blueprint per similarity search vettoriale.

## 2. Evidenze principali (codebase)

### P0 — Blocchi architetturali/funzionali

1. **Provider embedding non supportato**
   - `Provider` non espone API embedding.
   - `internal/llm/provider/provider.go:53-59`

2. **Embedding mai generato in `RecordEpisode`**
   - `EmbeddingID` sempre vuoto al salvataggio episodio.
   - `internal/aria/memory/service.go:185-195`

3. **Similarity search non semantica**
   - `GetSimilarEpisodes` basata su keywords + bonus outcome/recency.
   - `internal/aria/memory/service.go:285-322`
   - `internal/aria/memory/service.go:882-924`

4. **Storage vettoriale non implementato**
   - Colonna `episodes.embedding_id` presente ma inutilizzata.
   - `internal/db/migrations/20260328120000_aria_baseline.sql:89-100`
   - `internal/db/sql/episodes.sql:1-24`

### P1 — Gap di prodotto/configurazione

5. **Registry modelli embedding assente**
   - Nessun `ModelID` embedding in `internal/llm/models/*`.
   - `internal/llm/models/models.go:10-23`

6. **Configurazione embedding assente**
   - Nessuna chiave dedicata per provider/model embedding in config/schema.
   - `internal/config/config.go:170-187`
   - `cmd/schema/main.go:168-241`

7. **Copertura test non include path embedding/vector**
   - Test memory presenti, ma non coprono generazione embedding, persistence vector, ranking ibrido.
   - `internal/aria/memory/service_test.go`
   - `internal/aria/memory/integration_test.go`

### P2 — Qualità/robustezza

8. **Bug logico nel sorting di `GetSimilarEpisodes`**
   - Ordinamento ricalcola score usando indici di slice diverse (`bestEpisodes` vs `recentEpisodes`).
   - `internal/aria/memory/service.go:315-319`

9. **Portabilità vector backend da progettare**
   - Driver SQLite embedded in uso, ma nessuna integrazione extension-loading/vector backend.
   - `internal/db/connect.go:9-11`

## 3. Obiettivo target

Portare ARIA a un sistema memoria conforme al blueprint sul piano semantico:

- embedding generati automaticamente per nuovi episodi;
- storage vettoriale persistente e interrogabile;
- retrieval ibrido (vector + keyword + recency/outcome);
- fallback robusto in assenza embedding/provider;
- backfill storico controllato;
- metriche di qualità retrieval e test end-to-end.

## 4. Piano implementativo a fasi

## Fase 0 — Design, contratti e feature flags

### Deliverable
- Definizione contratti embedding:
  - estensione `provider.Provider` con `CreateEmbedding(ctx, text)` (o variante batch).
  - interfaccia interna memory storage per vettori (`StoreEmbedding`, `SearchSimilar`).
- Feature flag retrieval:
  - `memory.embedding.enabled`
  - `memory.embedding.mode = lexical|hybrid|vector`
- Decisione su backend vettoriale:
  - primaria: sqlite-vec;
  - fallback: tabella standard + cosine in Go (degraded mode).

### Acceptance
- API embedding definite e approvate.
- Modalità fallback chiaramente specificata (no hard-failure).

---

## Fase 1 — Provider & model registry embedding (P0)

### Deliverable
- Estendere `internal/llm/provider/provider.go` con metodo embedding.
- Implementare provider embedding in OpenAI (`/v1/embeddings`) come baseline.
- Introdurre registry modelli embedding in `internal/llm/models/`:
  - `text-embedding-3-small`
  - `text-embedding-3-large`
- Typed error per provider non supportati (es. `ErrEmbeddingNotSupported`).

### Test
- Unit test request/response mapping OpenAI embeddings.
- Contract test: provider senza embedding => fallback non distruttivo.

### Acceptance
- Generazione embedding disponibile con provider OpenAI.
- Nessuna regressione su chat/completion provider esistenti.

---

## Fase 2 — DB/migrazioni/vector store (P0)

### Deliverable
- Nuova migrazione DB:
  - tabella `episode_embeddings` con chiave episodio, vettore, dimensione, provider, modello, hash testo, timestamps.
- Estensione query SQL/sqlc:
  - insert/upsert embedding episodio;
  - get embedding per episodio;
  - top-k search (quando backend vector disponibile).
- Aggiornamento `episodes.embedding_id` con reference consistente.

### Test
- Migrazioni up/down su DB temporaneo.
- Integration test query embedding CRUD.
- Test di avvio su ambiente senza extension vector (fallback attivo).

### Acceptance
- Persistenza embedding funzionante e recuperabile.
- Avvio applicazione stabile anche senza sqlite-vec.

---

## Fase 3 — Cablaggio runtime memory service (P0)

### Deliverable
- `RecordEpisode()`:
  - genera payload testo canonico (task + actions + outcome + feedback);
  - invoca embedding async (non bloccare path principale);
  - persiste vettore e aggiorna `embedding_id`.
- `convertDBEpisode()` popola `Episode.Embedding` quando disponibile.
- Correzione bug ordinamento similarity (`service.go:315-319`).

### Test
- Unit test su pipeline async (success, timeout, errore provider).
- Test di consistenza `embedding_id` popolato post-record.
- Regression test sorting/score deterministico.

### Acceptance
- Nuovi episodi con embedding entro SLA asincrona definita.
- Nessun aumento significativo latenza su `RecordEpisode` sincrono.

---

## Fase 4 — Retrieval semantico ibrido (P0/P1)

### Deliverable
- `GetSimilarEpisodes()` con scoring composito:
  - `w_vector * cosine_similarity`
  - `w_keyword * lexical_score`
  - `w_recency * recency_bonus`
  - `w_outcome * outcome_bonus`
- Fallback chain:
  - vector unavailable -> hybrid lexical;
  - zero vectors -> top recent relevante.
- Opzionale estensione a `QueryKnowledge()` per semantic retrieval facts.

### Test
- Golden dataset con parafrasi (it/en) per confronto baseline vs hybrid.
- Test ranking top-k con expected ordering.
- Benchmark p50/p95 retrieval.

### Acceptance
- Miglioramento misurabile recall/precision rispetto baseline keyword-only.
- Comportamento deterministico e robusto in fallback.

---

## Fase 5 — Backfill, operatività e osservabilità (P1)

### Deliverable
- Job di backfill embedding per episodi storici (batch idempotente).
- Cache embedding by content-hash per deduplicare richieste API.
- Metriche:
  - `% episodi con embedding`
  - latenza embedding generation
  - fallback rate
  - retrieval quality proxy (CTR/hit relevance score interno)
- Runbook operativo (failure modes, retry policy, throttling).

### Test
- Test idempotenza backfill.
- Test resume backfill dopo interruzione.
- Load test batch con limiti API.

### Acceptance
- Corpus storico coperto oltre soglia target (es. >95%).
- Nessun degrado operativo critico durante backfill.

---

## Fase 6 — Config, QA finale e allineamento blueprint (P1)

### Deliverable
- Configurazione completa:
  - provider/model embedding
  - timeout/retry/concurrency
  - mode lexical/hybrid/vector
- QA end-to-end su flow orchestrator con retrieval semantico attivo.
- Aggiornamento documentazione blueprint/progress/changelog in coerenza con stato reale.

### Test
- E2E con flag ON/OFF.
- Test di compatibilità multipiattaforma (Linux/macOS) in modalità fallback/vector.

### Acceptance
- Feature operativa in produzione con rollout graduale.
- Blueprint e implementazione riallineati.

## 5. Piano di rollout (sicuro)

1. **Stage 1**: deploy con `memory.embedding.enabled=false` (shadow mode logging).  
2. **Stage 2**: attivazione solo ingest embedding (search ancora lexical).  
3. **Stage 3**: `mode=hybrid` su percentuale sessioni controllata.  
4. **Stage 4**: `mode=hybrid` globale, `vector-only` solo se KPI confermati.

## 6. KPI di successo

- Coverage embedding episodi recenti: **>= 99%**.
- Miglioramento Recall@5 su dataset parafrasi: **+30%** minimo vs baseline.
- p95 `GetSimilarEpisodes`: incremento max tollerato **< 20%** rispetto baseline.
- Error rate pipeline embedding: **< 1%** (esclusi outage provider esterni).

## 7. Rischi e mitigazioni

- **Rischio provider/costi API embedding**  
  Mitigazione: cache hash, batch, rate-limit, fallback lexical.

- **Rischio portability sqlite-vec**  
  Mitigazione: backend astratto + degraded mode senza extension.

- **Rischio regressione ranking**  
  Mitigazione: golden tests e feature flag rollout progressivo.

- **Rischio disallineamento blueprint/stato reale**  
  Mitigazione: aggiornamento roadmap e changelog ad ogni fase conclusa.

## 8. Sequenza operativa consigliata (ordine esecuzione)

1. Contratti provider/model embedding + flag config.  
2. Migrazione DB + sqlc embedding store.  
3. Cablaggio `RecordEpisode` async + update `embedding_id`.  
4. Retrieval ibrido in `GetSimilarEpisodes` + fix sorting bug.  
5. Test/benchmark + rollout shadow.  
6. Backfill storico + attivazione graduale in produzione.

## 9. Definizione di completamento

Il gap è considerato chiuso quando:
- embedding sono generati e persistiti per nuovi episodi;
- `GetSimilarEpisodes` usa semantic scoring reale (hybrid/vector);
- il fallback lexical è resiliente e testato;
- il backfill storico è completato a soglia target;
- test unit/integration/e2e coprono l’intero path embedding;
- documentazione blueprint rispecchia lo stato effettivo.
