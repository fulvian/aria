# Memory Embedding System — Gap Analysis

**Data**: 2026-03-30
**Stato**: Aperto
**Priorità**: Media
**Componente**: `internal/aria/memory/`, `internal/llm/provider/`, `internal/llm/models/`

## Sommario

Il sistema di memoria a 4 layer è funzionante e attivo, ma la ricerca semantica basata su embedding è **completamente assente**. I campi e le colonne esistono nel modello dati e nello schema DB, ma non sono mai popolati né utilizzati. La similarità tra episodi è attualmente implementata con un approccio keyword-based (`strings.Contains`) che non offre reale comprensione semantica.

## Stato attuale dei 4 layer

| Layer | Persistenza | Ricerca | Stato |
|-------|-------------|---------|-------|
| Working Memory | `sync.Map` + SQLite con TTL e GC | N/A (key-value) | ✅ Funzionante |
| Episodic Memory | SQLite | Keyword-based (`strings.Contains`) | ⚠️ Parziale |
| Semantic Memory | SQLite con confidence tracking | Keyword matching su dominio/categoria | ⚠️ Parziale |
| Procedural Memory | SQLite con scoring | Scoring su trigger/pattern/success rate | ✅ Funzionante |

## Dettaglio del gap

### 1. Interfaccia Provider — manca `CreateEmbedding`

**File**: `internal/llm/provider/provider.go:53-58`

L'interfaccia `Provider` supporta solo `SendMessages` e `StreamResponse`. Non esiste alcun metodo per generare embedding.

```go
type Provider interface {
    SendMessages(ctx, messages, tools) (*ProviderResponse, error)
    StreamResponse(ctx, messages, tools) <-chan ProviderEvent
    Model() models.Model
}
```

**Azioni richieste**:
- Aggiungere `CreateEmbedding(ctx context.Context, text string) ([]float32, error)` all'interfaccia
- Implementare in almeno un provider (OpenAI è il candidato più semplice, endpoint `/v1/embeddings`)

### 2. Modelli embedding — assenti

**File**: `internal/llm/models/`

Non esiste nessuna definizione di modello embedding. I file contengono solo modelli chat/completion.

**Azioni richieste**:
- Aggiungere modelli embedding (es. `text-embedding-3-small`, `text-embedding-3-large` per OpenAI)
- Considerare supporto multi-provider (Gemini, Anthropic hanno anch'essi API embedding)

### 3. Vector storage — non integrato

**File**: `internal/aria/memory/service.go`, `internal/db/`

La colonna `embedding_id TEXT` esiste nella tabella `episodes` (migration `20260328120000_aria_baseline.sql:98`) ma è sempre vuota:

```go
// service.go:194 — RecordEpisode()
EmbeddingID: toNullString(""),  // sempre vuoto
```

Non esiste nessuna integrazione con librerie vector SQLite.

**Azioni richieste**:
- Integrare `sqlite-vec` (https://github.com/asg017/sqlite-vec) o alternativa compatibile
- Creare una tabella vettoriale per gli embedding degli episodi
- Potenzialmente estendere a fact/procedure per ricerca semantica trasversale

### 4. Generazione embedding — mai invocata

**File**: `internal/aria/memory/service.go`

In `RecordEpisode()` (linea 194) l'embedding non viene mai generato. Il campo `Episode.Embedding []float32` (definito in `memory.go:57`) non è mai popolato.

**Azioni richied**:
- Dopo il salvataggio dell'episodio, chiamare l'API embedding sul testo combinato (situation + task + outcome)
- Salvare il vettore nello storage vettoriale
- Aggiornare `embedding_id` con il riferimento

### 5. Similarità semantica — workaround keyword

**File**: `internal/aria/memory/service.go:283-321`, `882-909`

`GetSimilarEpisodes()` usa un approccio pseudo-semantico:
1. `extractKeywords()` filtra stop-words dal testo (linea 909)
2. `calculateSimilarityScore()` fa `strings.Contains()` sul task text (linea 882)
3. Applica bonus per recency e outcome
4. Soglia di 0.3 — se nessun match supera la soglia, ritorna i 5 episodi più recenti

**Azioni richieste**:
- Sostituire `calculateSimilarityScore()` con cosine similarity tra embedding vettoriali
- Mantenere i bonus per recency/outcome come layer aggiuntivo sullo score
- Considerare search ibrida (keyword + vector) per robustezza

## Piano di implementazione suggerito

### Fase 1 — Fondamenta
- [ ] Aggiungere `CreateEmbedding()` all'interfaccia `Provider`
- [ ] Implementare in provider OpenAI (endpoint `/v1/embeddings`)
- [ ] Definire modelli embedding in `internal/llm/models/`
- [ ] Integrare `sqlite-vec` nel layer DB

### Fase 2 — Cablaggio
- [ ] Generare embedding in `RecordEpisode()` (async per non bloccare)
- [ ] Salvare vettori in tabella sqlite-vec
- [ ] Popolare `EmbeddingID` nel record episodio
- [ ] Popolare `Episode.Embedding []float32` in `convertDBEpisode()`

### Fase 3 — Ricerca semantica
- [ ] Implementare cosine similarity search in `GetSimilarEpisodes()`
- [ ] Valutare estensione a `QueryKnowledge()` (Semantic Memory)
- [ ] Search ibrida keyword + vector con score combinato

### Fase 4 — Ottimizzazione
- [ ] Batch embedding per episodi storici (backfill)
- [ ] Cache embedding per testi identici
- [ ] Metriche di qualità della ricerca (precision/recall)
- [ ] Benchmark performance query vettoriale

## Impatto

Senza embedding, la memoria episodica non può trovare esperienze rilevanti basate su significato — solo su keyword esatte. Questo limita la capacità del sistema di imparare dal passato in modo efficace, specialmente quando l'utente riformula lo stesso concetto con parole diverse.

## Note

- Il campo `Embedding []float32` è definito nel modello dominio ma è completamente morto
- Il campo `EmbeddingID` nel DB è sempre stringa vuota
- Il workaround keyword funziona accettabilmente per casi semplici ma non scala
- Nessun TODO/FIXME trovato nel codice — il gap è intenzionalmente rimandato
