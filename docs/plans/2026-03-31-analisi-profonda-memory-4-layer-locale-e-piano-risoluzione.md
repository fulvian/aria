# ARIA — Analisi Profonda Sistema Locale e Piano di Risoluzione

**Data**: 2026-03-31  
**Ambito**: istanza locale deployata (`/home/fulvio/aria-prod`) + codebase (`/home/fulvio/coding/aria`)  
**Oggetto**: malfunzionamento percepito del sistema memoria a 4 layer  
**Stato documento**: operativo (root cause identificata, piano esecutivo pronto)

---

## 1) Executive summary

Il problema principale **non è il codice del memory service in sé**, ma il fatto che nell’istanza locale il runtime opera in pratica fuori dal path ARIA/memory:

1. **ARIA risulta disattivata a runtime** (flag `ARIA_ENABLED` non impostata; il loader ARIA legge solo env vars).
2. **La configurazione locale (`.aria.json/.opencode.json`) non abilita `memory.enabled`** e non definisce provider/model embedding.
3. **Il database locale conferma assenza totale di dati memory** (`episodes`, `facts`, `procedures`, `working_memory_contexts`, `episode_embeddings` tutti a 0).
4. Il servizio sembra essere stato avviato almeno una volta con argomento non supportato (`--host`), quindi possibile startup incompleto/non conforme.

Conseguenza: il sistema opera principalmente in **legacy mode** (session/messages presenti), e il sottosistema memoria 4-layer non riceve traffico reale.

---

## 2) Evidenze raccolte

### 2.1 Configurazione runtime/avvio

- `internal/aria/config/config.go`
  - `ariaConfig.Load()` usa esclusivamente variabili ambiente `ARIA_*`.
  - `Enabled` default: `false` (se `ARIA_ENABLED` non impostata).
- `internal/app/aria_integration.go`
  - `initARIA()` esce subito se `ariaCfg.Enabled == false`.
- `internal/app/app.go`
  - `RunNonInteractive()` usa ARIA solo se `IsARIAMode()==true`, altrimenti legacy.

**Osservazione locale ambiente**:
- Nessuna `ARIA_*` presente.
- Nessuna variabile embedding/provider impostata in env corrente.

### 2.2 Config files locali

- `/home/fulvio/.aria.json`: campo `memory` vuoto (`{}`) → embedding disattivati per default.
- `/home/fulvio/aria-prod/.aria.json` e `.opencode.json`: nessun blocco `aria` e nessun blocco `memory` utile all’abilitazione reale.

### 2.3 Stato DB locale (istanza deployata)

DB: `/home/fulvio/aria-prod/.aria/aria.db`

- Tabelle esistenti: `episodes`, `working_memory_contexts`, `episode_embeddings`, `fact_embeddings`.
- Conteggi:
  - `sessions`: 8
  - `messages`: 172
  - `episodes`: 0
  - `facts`: 0
  - `procedures`: 0
  - `working_memory_contexts`: 0
  - `episode_embeddings`: 0
  - `fact_embeddings`: 0

**Interpretazione**: il sistema sta tracciando chat/sessione legacy, ma non il ciclo memoria ARIA.

### 2.4 Log runtime locale

- `/home/fulvio/aria-prod/logs/aria.log` contiene:
  - `Error: unknown flag: --host`

**Interpretazione**: avvio con comando non compatibile con CLI corrente; alto rischio di startup path errato o non applicato.

---

## 3) Analisi del codice memoria (stato attuale)

## 3.1 Cosa funziona

- Memory service 4-layer è implementato in `internal/aria/memory/service.go`:
  - Working memory: `SetContext/GetContext` + persistenza DB + GC.
  - Episodic memory: `RecordEpisode/SearchEpisodes/GetSimilarEpisodes`.
  - Semantic memory: `StoreFact/GetFacts/QueryKnowledge`.
  - Procedural memory: `SaveProcedure/GetProcedure/FindApplicableProcedures`.
- Embedding pipeline presente:
  - queue async + worker
  - serializzazione vettori
  - persistenza in `episode_embeddings`
  - retrieval ibrido (vector+keyword+recency+outcome)
- Provider interface estesa con `CreateEmbedding(...)`.
- OpenAI-compatible embedding implementato (`internal/llm/provider/openai.go`).

## 3.2 Criticità tecniche residue (anche dopo fix configurazione)

1. **Close incompleto del memory service**
   - `Close()` chiude `stopCh` (GC) ma non `embedStopCh` (worker embedding).
   - Rischio goroutine leak e shutdown non pulito.

2. **`episodes.embedding_id` non aggiornato**
   - In `RecordEpisode`, `EmbeddingID` resta sempre vuoto.
   - Il sistema usa `episode_embeddings.episode_id` come relazione reale: funziona, ma crea incoerenza con schema legacy.

3. **Dedup embedding non applicata in write path**
   - Esiste `GetEpisodeEmbeddingByHash`, ma `processEmbedding()` fa sempre `CreateEpisodeEmbedding`.
   - Possibili duplicati per stesso episodio/testo in run ripetuti.

4. **Validazione config embedding insufficiente**
   - `memory.enabled=true` senza `memory.provider/model` può degradare silenziosamente.
   - `createEmbedding` non supportato su alcuni provider (Anthropic/Gemini/Bedrock) → fallback implicito poco osservabile.

5. **Copertura test embedding limitata lato integrazione reale**
   - Test presenti, ma pochi casi e2e su pipeline embedding attiva con provider mock affidabile + asserzioni DB complete.

---

## 4) Root cause (ordinata per impatto)

## RC-1 (P0) — ARIA non attiva in runtime
- Mancanza `ARIA_ENABLED=true` nel processo che avvia il binario.
- Effetto: orchestrator ARIA e memory pipeline non entrano mai in esercizio.

## RC-2 (P0) — Config memory embedding non attiva
- `memory.enabled=false` implicito e assenza provider/model embedding.
- Effetto: nessuna generazione vettoriale anche quando ARIA è attiva.

## RC-3 (P1) — Startup command errato (`--host`)
- Processo locale invocato con flag non supportato.
- Effetto: esecuzioni intermittenti/fallite, stato locale incoerente.

## RC-4 (P1) — Hardening incompleto memory lifecycle
- Worker embedding non fermato su `Close()`.

## RC-5 (P2) — Incoerenze funzionali minori
- `embedding_id` non valorizzato, dedup non usata, osservabilità embedding da rafforzare.

---

## 5) Piano di risoluzione completo e dettagliato

## Fase A — Ripristino runtime corretto locale (P0)

### Obiettivo
Portare il processo locale in modalità ARIA reale e verificare ingest memoria.

### Attività
1. Correggere comando di avvio (rimuovere `--host`).
2. Esportare env minime nel contesto di avvio:
   - `ARIA_ENABLED=true`
   - `ARIA_ROUTING_ENABLE_FALLBACK=true`
3. Avviare il servizio con CLI supportata (`aria -d` o `aria -p "..."`).

### Verifica
- Log deve contenere inizializzazione ARIA (`Initializing ARIA mode`).
- Nessun errore `unknown flag`.

### Exit criteria
- Startup stabile ripetibile 3 volte consecutive.

---

## Fase B — Attivazione memory embedding (P0)

### Obiettivo
Abilitare pipeline embedding per retrieval ibrido.

### Attività
1. Aggiornare config locale con blocco memory esplicito (nel config effettivamente letto a runtime):
   - `memory.enabled: true`
   - `memory.provider: openai` **oppure** `local` (OpenAI-compatible endpoint)
   - `memory.model: text-embedding-3-small` (openai) o modello locale compatibile
   - `memory.mode: hybrid`
   - `memory.batchSize: 1`
   - `memory.timeoutMs: 30000`
   - `memory.vectorCacheEnabled: true`
2. Garantire provider coerente e abilitato con API key valida.

### Verifica
- Log: `Embedding enabled` con provider/model.
- Dopo traffico test, `episode_embeddings` > 0.

### Exit criteria
- Almeno 10 episodi con embedding persistito.

---

## Fase C — Validazione end-to-end 4 layer (P0)

### Obiettivo
Provare funzionalmente working/episodic/semantic/procedural + similarità.

### Attività
1. Eseguire scenario guidato locale:
   - 5 query con esito success/partial/failure
   - 2 eventi di learning success/failure
   - 2 query conoscenza
2. Verificare DB:
   - `working_memory_contexts` cresce
   - `episodes` cresce
   - `facts` cresce
   - `procedures` cresce (se discovery/usage attivo)
   - `episode_embeddings` cresce
3. Eseguire query di similarità con parafrasi e confrontare top-k.

### Verifica
- Tutti i 4 layer con dati > 0.
- Similarità non solo keyword exact-match.

### Exit criteria
- Test operativo locale firmato (checklist completa).

---

## Fase D — Hardening codice memory (P1)

### Obiettivo
Rendere robusto il servizio in produzione locale.

### Attività tecniche
1. **Fix lifecycle**
   - In `Close()`: chiudere anche `embedStopCh` se inizializzata.
2. **Coerenza embedding reference**
   - Aggiornare `episodes.embedding_id` dopo `CreateEpisodeEmbedding` (opzionale ma raccomandato).
3. **Dedup by hash**
   - Prima di insert embedding, tentare lookup by hash/episode e riuso.
4. **Validazione config fail-fast**
   - Se `memory.enabled=true` ma provider/model invalidi: warning strutturato + fallback deterministico dichiarato.
5. **Logging diagnostico**
   - Metriche embedding periodiche: generated/cache_hit/backfill/error_rate.

### Verifica
- `go test ./internal/aria/memory/...`
- `go test -race ./internal/aria/memory/...`
- test integrazione con DB temporaneo.

### Exit criteria
- Nessun leak in shutdown ripetuti.
- Pipeline embedding stabile sotto carico leggero.

---

## Fase E — Osservabilità e runbook operativo locale (P1)

### Obiettivo
Ridurre MTTR e rendere misurabile lo stato memoria.

### Attività
1. Aggiungere comando diagnostico (o script) locale che riporta:
   - stato ARIA mode
   - stato memory config
   - count tabelle memoria
   - embedding metrics runtime
2. Definire runbook di triage in `docs/runbooks/`:
   - “nessun dato episodic”
   - “embedding a zero”
   - “provider not supported”

### Exit criteria
- Diagnostica one-shot eseguibile in < 30s.

---

## Fase F — Stabilizzazione e regressione (P2)

### Obiettivo
Prevenire ricadute.

### Attività
1. Test e2e CI per memoria attiva/disattiva.
2. Test config matrix:
   - ARIA off
   - ARIA on + memory off
   - ARIA on + memory hybrid
3. Aggiungere guardia su startup args non validi nel deploy script.

### Exit criteria
- Nessuna regressione in 3 run consecutivi post-fix.

---

## 6) Checklist operativa immediata (ordine consigliato)

1. Correggere comando di avvio locale (rimuovere `--host`).
2. Attivare `ARIA_ENABLED=true` nel processo deploy locale.
3. Configurare blocco `memory` con provider/model compatibili.
4. Riavviare servizio e verificare log ARIA + embedding.
5. Generare traffico test e confermare crescita tabelle memoria.
6. Eseguire hardening codice (fase D) e test race.

---

## 7) Rischi e mitigazioni

- **Rischio**: ARIA attiva ma provider embedding non supportato.  
  **Mitigazione**: enforce provider compatibile (`openai`/`local` OpenAI-compatible), validazione startup.

- **Rischio**: API key assente/errata.  
  **Mitigazione**: check startup fail-fast + log esplicito.

- **Rischio**: leak worker embedding su stop/restart.  
  **Mitigazione**: fix `Close()` + test shutdown multiplo.

- **Rischio**: falsa percezione “memory rotta” per assenza traffico ARIA.  
  **Mitigazione**: dashboard minima con count tabelle e stato mode.

---

## 8) Definizione di successo

Il problema è considerato risolto quando, su ambiente locale deployato:

1. ARIA mode è attiva stabilmente.
2. I 4 layer memoria contengono dati reali dopo interazioni normali.
3. `episode_embeddings` è popolata e `GetSimilarEpisodes` usa scoring ibrido effettivo.
4. Lo shutdown non lascia worker attivi.
5. Esiste runbook diagnostico che permette triage rapido.

---

## 9) Allegato: evidenze sintetiche (snapshot)

- Env locale: nessuna `ARIA_*` presente al momento dell’analisi.  
- Config user/prod: `memory` non configurata (vuota/assente).  
- DB locale: `episodes/facts/procedures/working_contexts/embeddings = 0`.  
- Log locale: errore startup `unknown flag: --host`.
