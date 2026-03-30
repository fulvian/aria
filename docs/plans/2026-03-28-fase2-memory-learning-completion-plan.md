# Piano Completo di Completamento FASE 2 (Memory & Learning)

**Data**: 2026-03-28  
**Scope**: Validazione stato reale implementazione + piano robusto e dettagliato per completare FASE 2  
**Baseline documento**: `docs/foundation/BLUEPRINT.md` v1.7.0-DRAFT

---

## 1) Sintesi esecutiva

Dall’analisi della codebase, **FASE 2 è implementata a livello MVP**, ma **non ancora completata a livello production-grade** per le parti più critiche/innovative (retrieval avanzato, apprendimento procedurale reale, integrazione end-to-end nell’orchestrazione, hardening operativo).

Le fasi 0,1,3,4 risultano in gran parte implementate, ma con alcuni gap residuali da consolidare (soprattutto su persistenza/integrazione profonda).

Questo piano definisce un percorso **completo, verificabile, a basso rischio regressione**, con milestone, deliverable, criteri di accettazione e test.

---

## 2) Stato reale verificato (codebase)

### 2.1 FASE 0 — Foundation

**Evidenze**
- Namespace ARIA presente: `internal/aria/{core,agency,agent,skill,routing,memory,scheduler,permission,guardrail,analysis}`.
- Migrazione baseline presente: `internal/db/migrations/20260328120000_aria_baseline.sql`.
- Query SQLc presenti per agencies/tasks/episodes/facts/procedures.

**Valutazione**: **quasi completa / completa lato struttura**.  
**Gap residuo**: test suite “base” non uniforme su tutti i package ARIA (es. core/routing/skill senza test unitari dedicati).

---

### 2.2 FASE 1 — Core System

**Evidenze**
- Orchestrator implementato: `internal/aria/core/orchestrator_impl.go`.
- Development Agency + Registry/Lifecycle: `internal/aria/agency/*.go`.
- Enhanced agent wrapper: `internal/aria/agent/legacy_wrapper.go`.
- Skill system + skill reali: `internal/aria/skill/{registry,code_review,tdd,debugging}.go`.
- Routing baseline: `internal/aria/routing/*`.
- Integrazione app: `internal/app/aria_integration.go`.

**Valutazione**: **completa a livello MVP operativo**.  
**Gap residuo noto**: complexity analyzer routing dichiarato deferred nel blueprint.

---

### 2.3 FASE 3 — Scheduling

**Evidenze**
- Service, dispatcher, worker, recurring planner, recovery, mapper: `internal/aria/scheduler/*`.
- TUI tasks page: `internal/tui/page/tasks_page.go`.
- Test scheduler presenti e verdi.

**Valutazione**: **forte implementazione**, ma con hardening ancora necessario.

**Gap tecnici rilevati**
- `internal/aria/scheduler/executor.go`: executor è stub (non delega realmente ad Agency/Agent).
- `UpdateSchedule` in `service.go` valida ma non persiste realmente schedule aggiornata.
- Idempotenza recurring basata su euristiche (manca colonna forte tipo `recurring_parent_id`/`idempotency_key` persistita in schema).

---

### 2.4 FASE 4 — Proactivity / Guardrails

**Evidenze**
- Guardrail service completo API: `internal/aria/guardrail/service.go`.
- Extended permission service: `internal/aria/permission/service.go`.
- Wiring in app presente.

**Valutazione**: **implementata a livello funzionale in-memory**.  
**Gap residuo**: persistenza/audit robusto e integrazione cross-session non ancora strutturata.

---

## 3) Gap reali FASE 2 (Memory & Learning) da chiudere

### 3.1 Integrazione architetturale incompleta
- Memory/analysis service implementati, ma **non orchestrati end-to-end nel runtime app/orchestrator** (in `aria_integration.go` non risultano inizializzati memory + self-analysis service).
- `BasicOrchestrator.ProcessQuery` non utilizza sistematicamente working/episodic/semantic/procedural memory.

### 3.2 Working memory troppo volatile
- Solo `sync.Map` in-memory (`memory/service.go`), senza snapshot/persistenza/restore per ripartenza.

### 3.3 Episodic retrieval limitato
- `SearchEpisodes` applica solo filtro sessione o list all; **ignora in pratica** `AgentID`, `TaskType`, `TimeRange`.
- `GetSimilarEpisodes` usa fallback keyword (LIKE), no similarity embedding reale.

### 3.4 Semantic memory non fully lifecycle
- `QueryKnowledge` non aggiorna uso (`use_count`, `last_used`) sugli item consumati.
- Mancano strategie dedup/upsert/conflict resolution facts.

### 3.5 Procedural learning ancora euristico
- `FindApplicableProcedures` matching minimale e fragile.
- Learning loop non genera/aggiorna procedure in modo sistematico da pattern di successo/fallimento.

### 3.6 Self-analysis non productionized
- `AnalyzePerformance` non filtra realmente per time range (legge task globali).
- `RunPeriodicAnalysis` esiste ma non risulta orchestrato in avvio app.
- Insight non persistiti/versionati.

### 3.7 Test gap
- Test presenti ma prevalentemente unit/mock; mancano integration/E2E significativi per memory-learning cross-component.

---

## 4) Obiettivo FASE 2 (target di completamento)

Portare Memory & Learning da **MVP funzionale** a **sistema robusto, misurabile e integrato** con:
1. Memoria multi-livello realmente utilizzata in runtime.
2. Retrieval affidabile (filtro, ranking, similarity strategy con fallback).
3. Loop di apprendimento verificabile e non regressivo.
4. Self-analysis periodica utile e persistita.
5. Copertura test + osservabilità + policy retention/privacy.

---

## 5) Piano implementazione dettagliato (workstreams)

## WS1 — Integration Backbone (priorità: P0)

**Obiettivo**: integrare Memory + SelfAnalysis nel flusso reale.

**Attività**
1. Inizializzare `memory.NewService(app.DB)` e `analysis.NewService(app.DB)` in `internal/app/aria_integration.go`.
2. Estendere `ARIAComponents` con riferimenti memory/analysis.
3. Agganciare nel ciclo query orchestrator:
   - pre-execution: carico contesto + episodi simili + procedure candidate;
   - post-execution: record episodio + update facts/procedure metrics + eventuale feedback.
4. Definire eventi pub/sub dedicati (es. `memory.updated`, `analysis.insight.generated`) per telemetria interna.

**Deliverable**
- Wiring completo runtime.
- Tracciamento memoria per ogni query task.

**Acceptance criteria**
- Ogni query ARIA produce almeno 1 record episodico con outcome.
- Orchestrator consuma almeno un segnale memory prima dell’exec (quando disponibile).

---

## WS2 — Working Memory Durability (P0)

**Obiettivo**: ridurre perdita contesto su restart.

**Attività**
1. Definire snapshot context serializzato (DB table dedicata o riuso struttura session metadata).
2. Implementare save/restore automatico per session context.
3. Aggiungere TTL e garbage collection controllata.
4. Introdurre versioning schema context per backward compatibility.

**Deliverable**
- Contesto recuperabile post restart.

**Acceptance criteria**
- Restart app non perde context per sessioni attive entro TTL.
- Test integrazione passano su scenario crash/restart.

---

## WS3 — Episodic Retrieval 2.0 (P0)

**Obiettivo**: ricerca episodi precisa e scalabile.

**Attività**
1. Implementare filtri completi in `SearchEpisodes`:
   - sessionID, agentID, taskType, timeRange, limit.
2. Aggiungere ranking multi-criterio (recency + outcome quality + lexical similarity).
3. Implementare similarity stratificata:
   - fase A: lexical + metadata weighted;
   - fase B (opzionale feature flag): embedding search (`sqlite-vec`) con fallback automatico.
4. Aggiungere indici utili e query SQL dedicate.

**Deliverable**
- API retrieval deterministica e con ranking ripetibile.

**Acceptance criteria**
- Precision@k migliorata su test set sintetico.
- Query multi-filtro < soglia p95 target locale.

---

## WS4 — Semantic Memory Governance (P0)

**Obiettivo**: knowledge base consistente e “viva”.

**Attività**
1. Aggiornare `QueryKnowledge` per incrementare `use_count`/`last_used` sugli item ritornati.
2. Implementare dedup/upsert facts (key semantica domain+category+normalized content hash).
3. Gestire confidence evolution (boost su conferma, decay su obsolescenza/fallimenti).
4. Aggiungere policy source-trust e provenance minima.

**Deliverable**
- Knowledge lifecycle affidabile.

**Acceptance criteria**
- Nessuna proliferazione incontrollata di duplicati oltre soglia definita.
- Confidence e usage coerenti con accessi reali.

---

## WS5 — Procedural Learning Engine (P0/P1)

**Obiettivo**: apprendere workflow riusabili da esperienza.

**Attività**
1. Definire pipeline:
   - collect episodes → mine patterns → candidate procedures → validate → publish.
2. Migliorare `FindApplicableProcedures` con scoring trigger (type/pattern/context).
3. Introdurre anti-regression guard: auto-promotion solo oltre soglia min sample + success rate.
4. Integrare feedback esplicito utente nelle metriche procedura.

**Deliverable**
- Procedure discovery/upgrade semi-automatico.

**Acceptance criteria**
- Almeno N procedure candidate generate su dataset di test.
- Nessuna procedura promossa sotto soglie configurate.

---

## WS6 — Self-Analysis Production Hardening (P1)

**Obiettivo**: report utili, consistenti, persistiti e schedulati.

**Attività**
1. Rendere `AnalyzePerformance` time-range aware reale.
2. Persistenza report/insight (tabella dedicata o store esistente).
3. Avvio periodico analysis job integrato con scheduler (non solo ticker locale).
4. Dashboard dati minimi per TUI/log (trend success rate, top failure causes, top procedures).

**Deliverable**
- Insight periodici persistiti e consultabili.

**Acceptance criteria**
- Job periodico produce report con timestamp e dataset coerente.
- Consultazione insight disponibile da servizio/API.

---

## WS7 — Privacy, Retention, Safety (P1)

**Obiettivo**: controllo crescita dati e conformità privacy-first.

**Attività**
1. Retention policy configurabile per episodes/facts/procedures logs.
2. Pseudonimizzazione/minimizzazione dove necessario (session/user references).
3. Strumenti di purge selettivo e compattazione DB.
4. Audit eventi critici memory-learning.

**Deliverable**
- Data lifecycle controllato.

**Acceptance criteria**
- Pulizia dati verificabile con comandi test e metriche before/after.

---

## WS8 — Quality Gates (P0)

**Obiettivo**: evitare regressioni e chiudere fase con evidenza.

**Attività**
1. Unit test aggiuntivi su edge cases retrieval/learning.
2. Integration test ARIA: Orchestrator ↔ Memory ↔ Scheduler ↔ Analysis.
3. E2E scenario:
   - query ripetute,
   - apprendimento pattern,
   - suggerimento/procedura applicata,
   - insight periodico generato.
4. Benchmark locale (latenza retrieval, overhead learning).

**Deliverable**
- Test pyramid completa per FASE 2.

**Acceptance criteria**
- `go test ./internal/aria/...` verde.
- Suite integrazione memory-learning verde.
- Nessuna regressione sulle feature fasi 1/3/4.

---

## 6) Sequenza di esecuzione consigliata

1. **M1 (Settimana 1-2)**: WS1 + WS2 (integrazione + durabilità contesto)  
2. **M2 (Settimana 2-4)**: WS3 + WS4 (retrieval e governance semantica)  
3. **M3 (Settimana 4-6)**: WS5 (procedural learning engine)  
4. **M4 (Settimana 6-7)**: WS6 + WS7 (analysis hardening + retention/privacy)  
5. **M5 (Settimana 7-8)**: WS8 (QA finale, benchmark, docs, fase gate)

---

## 7) Definition of Done (FASE 2)

FASE 2 è considerata **completa** solo se:
- [ ] Memory service pienamente integrato nel runtime orchestrator.
- [ ] Working memory persistibile/restorabile cross-restart.
- [ ] Episodic retrieval con filtri completi + ranking verificato.
- [ ] Semantic memory con usage tracking + dedup/upsert.
- [ ] Procedural learning con pipeline e soglie di qualità.
- [ ] Self-analysis periodica persistita + consumabile.
- [ ] Test unit/integration/e2e e benchmark minimi verdi.
- [ ] Aggiornamento blueprint/changelog coerente con stato reale.

---

## 8) Rischi principali e mitigazioni

1. **Rischio regressioni orchestration**  
   Mitigazione: feature flags + rollout incrementale + integration tests.

2. **Rischio crescita incontrollata DB**  
   Mitigazione: retention policy + indici + compaction jobs.

3. **Rischio false procedure (learning rumoroso)**  
   Mitigazione: soglie min sample/success + human gate su promozione.

4. **Rischio complessità retrieval/embedding**  
   Mitigazione: approccio a livelli (lexical first, vector optional).

---

## 9) Verifiche immediate consigliate (prima di esecuzione piano)

1. Allineare `BLUEPRINT.md` dove oggi ci sono incongruenze tra:
   - header/changelog (fasi complete)
   - roadmap grafica/deliverable checkboxes (ancora 0% o non spuntati).
2. Formalizzare baseline metriche (success rate, retrieval p95, volume episodes/facts/procedures).
3. Definire feature flags per attivazione graduale memory-learning avanzato.

---

## 10) Conclusione operativa

La codebase ha già le fondamenta corrette. Il completamento reale della FASE 2 richiede ora **integrazione profonda, retrieval robusto, apprendimento procedurale affidabile e hardening operativo**. Il piano sopra è sequenziale, testabile e orientato a chiudere la fase in modo production-grade senza introdurre regressioni sulle fasi già avanzate.
