# Piano di Implementazione ARIA — Fasi Iniziali (Foundation + Core Bootstrap)

**Data:** 2026-03-28  
**Baseline:** `docs/foundation/BLUEPRINT.md` v`1.0.0-DRAFT` (Status: `FOUNDATIONAL`)  
**Scope di questo piano:** pianificare in modo eseguibile e robusto l’avvio implementativo senza modificare feature utente esistenti.

---

## 1) Obiettivo operativo

Trasformare ARIA in modo incrementale e backward-compatible, partendo dalle fasi iniziali con priorità su:

1. **Fondazioni architetturali verificabili** (interfacce, contratti, package layout, registry)
2. **Persistenza minima estesa** (DB e sqlc pronti per task/agency/memory)
3. **Orchestrazione core “thin”** (routing base + agency development MVP)
4. **Riduzione rischio regressioni** (compatibilità con `internal/llm/*`, TUI/CLI invarianti)

---

## 2) Analisi sintetica codebase attuale (impatti principali)

### 2.1 Punti solidi già presenti (riuso diretto)

- **Agent runtime stabile** in `internal/llm/agent/agent.go`
  - stream provider/tool-use, cancellazione, session lock (`sync.Map`), usage tracking
- **Tool abstraction unificata** in `internal/llm/tools/tools.go` (`BaseTool`, `ToolInfo`, `ToolCall`)
- **MCP integration** già operativa in `internal/llm/agent/mcp-tools.go`
- **Permission service** funzionante in `internal/permission/permission.go`
- **Pub/Sub generico** in `internal/pubsub/*`
- **Persistence con sqlite+goose+sqlc** (`internal/db/*`, `internal/db/migrations/*`, `internal/db/sql/*`)

### 2.2 Gap rispetto BLUEPRINT (fasi iniziali)

- Nessuna namespace `internal/aria/*`
- Architettura agent **flat** (no Agency/Orchestrator/Skill layer)
- Schema DB limitato a `sessions/messages/files`
- Config non estesa per agencies/skills/scheduler/guardrails
- Nessun classifier/router dedicato a intent+complexity

### 2.3 Vincoli architetturali da rispettare

- Backward compatibility con flussi correnti (`cmd/root.go`, `internal/app/app.go`)
- Migrazioni additive e reversibili (goose)
- Evitare riscrittura big-bang del coder agent
- Mantenere “opt-in complexity”: default path deve restare semplice

---

## 3) Strategia proposta: fasi iniziali ottimizzate

Le macrofasi Blueprint 0 e 1 vengono raffinate in **7 fasi esecutive** per ridurre rischio e accelerare feedback.

---

## Fase A — Foundation Contracts & Guardrails (pre-codifica strutturale)

**Scopo:** definire contratti minimi ARIA senza impattare runtime esistente.

### Deliverable

- `internal/aria/` creato con package vuoti + interfacce core (solo contratti)
  - `core`, `agency`, `agent`, `skill`, `routing`, `memory`, `scheduler`, `permission`, `guardrail`, `analysis`
- Documento di mapping “Blueprint → Package/Interface”
- Matrice decisionale “compatibility mode” (legacy agent path vs orchestrator path)

### Criteri di accettazione

- Build verde senza feature nuova attiva
- Interfacce compile-time complete per Fase 0 (Blueprint 2.x, 3.x, 4.x, 5.x, 6.x)
- Nessuna regressione sui package correnti

### Rischi / mitigazioni

- **Rischio:** over-design precoce  
  **Mitigazione:** interfacce minime + TODO espliciti, no implementazioni premature.

---

## Fase B — Data Foundation (DB + sqlc scaffolding)

**Scopo:** preparare persistenza per agencies/tasks/memory senza attivare scheduling reale.

### Deliverable

- Nuove migrazioni additive (es. `tasks`, `task_dependencies`, `task_events`, `agencies`, `agency_states`, `memory_*`)
- Query SQL nuove in `internal/db/sql/*.sql`
- Generazione sqlc aggiornata (`sqlc generate`)
- Modelli repository/service stub ARIA che usano `db.Querier`

### Criteri di accettazione

- `go test ./...` verde
- Migrazione da DB vuoto e DB già esistente valida
- Nessun breaking change alle tabelle `sessions/messages/files`

### Rischi / mitigazioni

- **Rischio:** schema troppo ambizioso in anticipo  
  **Mitigazione:** introdurre campi minimi necessari per Fasi C-D; estensioni successive in migrazioni incremental.

---

## Fase C — Config & Registry Layer

**Scopo:** estendere configurazione per ARIA mantenendo default legacy.

### Deliverable

- Estensione `internal/config/config.go` con blocchi opzionali:
  - `aria.enabled`
  - `aria.routing`
  - `aria.agencies`
  - `aria.skills`
  - `aria.scheduler`
  - `aria.guardrails`
- Registry base:
  - `AgencyRegistry`
  - `SkillRegistry`
  - `AgentRegistry` (wrapper su agent legacy dove serve)
- Validazione config con fallback safe

### Criteri di accettazione

- Config legacy continua a funzionare senza campi ARIA
- Config ARIA minima parse/validate correttamente
- Nessun impatto su startup corrente (`cmd/root.go`)

---

## Fase D — Orchestrator MVP (routing base non distruttivo)

**Scopo:** introdurre orchestratore con fallback trasparente al coder legacy.

### Deliverable

- `internal/aria/core/orchestrator.go` (impl MVP)
- `internal/aria/routing/classifier.go` + `router.go` (regole baseline deterministiche)
- Pipeline:
  1. classify intent/domain/complexity
  2. routing decision
  3. execute via agency/agent
  4. fallback su `app.CoderAgent` se no match

### Criteri di accettazione

- Per prompt development standard, output equivalente (o fallback) rispetto allo stato attuale
- Tracciamento decisioni di routing disponibile (log/eventi)
- Timeout/cancel invarianti rispettati

### Rischi / mitigazioni

- **Rischio:** classificazione fragile all’inizio  
  **Mitigazione:** rules-first + confidence threshold + fallback obbligatorio.

---

## Fase E — Development Agency MVP

**Scopo:** prima agency operativa (Blueprint 8.3.2: almeno 1 agency)

### Deliverable

- `DevelopmentAgency` con agenti iniziali:
  - `coder` (bridge al servizio legacy `internal/llm/agent`)
  - `reviewer` (placeholder operativo con skill selection)
  - `architect` (routing stub iniziale)
- Stato agency persistibile (read/write minimo)
- Eventi agency via `pubsub`

### Criteri di accettazione

- Query di coding instradabili verso Development Agency
- Esecuzione task immediate funzionante
- Isolamento sufficiente per aggiungere altre agency senza refactor centrale

---

## Fase F — Skill System MVP (+ migrazione skill da tool semantics)

**Scopo:** introdurre layer skill senza rompere tool execution.

### Deliverable

- `Skill` interface + runtime wrapper
- Prime skill operative (target minimo 3):
  - `code-review`
  - `test-driven-dev` (inizialmente procedurale)
  - `systematic-debugging`
- Skill-to-tool mapping esplicito (required tools / required MCP)
- `CanExecute()` con check capability/permission base

### Criteri di accettazione

- Le 3 skill invocabili via Development Agency
- Nessuna duplicazione logica critica nel tool layer
- Error handling standardizzato (ToolResponse compatibile)

---

## Fase G — Integration, Verification, Rollout controllato

**Scopo:** collegamento CLI/TUI, test e rollout graduale.

### Deliverable

- Hook in `internal/app/app.go` per modalità:
  - `legacy` (default)
  - `aria` (opt-in)
- Test stack:
  - unit (classifier/router/registry)
  - integration (orchestrator→agency→agent)
  - migration tests (DB)
- Checklist blueprint update (versione, changelog, stato)

### Criteri di accettazione

- `go test ./...` verde
- Modalità legacy invariata
- Modalità aria esegue almeno workflow development end-to-end base

---

## 4) Piano temporale (stima realistica)

- **Sprint 1:** Fasi A-B
- **Sprint 2:** Fasi C-D
- **Sprint 3:** Fasi E-F
- **Sprint 4:** Fase G + hardening

Dipendenze critiche:

- B dipende da A
- D dipende da C
- E/F dipendono da D
- G dipende da E/F

---

## 5) Sequenza tecnica dettagliata (ordine commit consigliato)

1. `chore(aria): add foundational interfaces and package scaffolding`
2. `feat(db): add aria baseline tables and sqlc queries`
3. `feat(config): add aria configuration blocks and validation`
4. `feat(aria-core): add orchestrator MVP with deterministic router`
5. `feat(agency): add development agency with legacy coder bridge`
6. `feat(skill): add skill registry and first 3 development skills`
7. `feat(app): wire opt-in aria runtime mode`
8. `test(aria): add unit/integration/migration coverage`
9. `docs(blueprint): update roadmap progress, status, changelog`

---

## 6) Test strategy iniziale (obbligatoria per gate di fase)

### Unit

- classifier: intent/domain/complexity matrix
- router: target decision + fallback rules
- registries: lookup, duplicate handling, capability filters

### Integration

- orchestrator → development agency → coder bridge
- cancellation propagation
- permission check propagation

### DB/Migrations

- bootstrap DB vuoto
- upgrade DB con dati legacy
- query compatibility su `sessions/messages/files`

### Non-regression

- Esecuzione prompt non-interattivo (`cmd/root.go` flow)
- Flussi tool principali (`bash/edit/glob/grep/view`)

---

## 7) Aggiornamenti obbligatori BLUEPRINT durante esecuzione

Per conformità alle regole progetto:

1. Aggiornare progress FASE 0/1 in sezione 8.1 ad ogni milestone chiusa
2. Aggiornare `Status` documento:
   - `FOUNDATIONAL` → `IN_PROGRESS` all’avvio effettivo implementazione Fase A
   - `IN_PROGRESS` → `EVOLVING` al completamento della prima fase completa
3. Aggiornare Change Log ad ogni version bump
4. Mantenere tracciabilità file/package ↔ sezione blueprint

---

## 8) Definition of Done per “fasi iniziali”

La fase iniziale è considerata completata quando:

- [ ] Namespace `internal/aria/*` presente con contratti + MVP runtime
- [ ] Development Agency funzionante end-to-end (opt-in)
- [ ] 3 skill development operative
- [ ] Routing base con fallback stabile
- [ ] Schema DB ARIA base migrato + sqlc aggiornato
- [ ] Test unit/integration/migration verdi
- [ ] BLUEPRINT aggiornato (progress + changelog + status)

---

## 9) Backlog immediato (pronti per execution)

1. Definire interfacce minime concrete per A (ridurre ambiguità campi non necessari)
2. Disegnare ERD minimo per B (task + agency state + memory seed)
3. Stabilire routing rules v0 (keywords + complexity heuristic)
4. Definire contratto “legacy coder bridge” (input/output/eventi)
5. Definire test matrix iniziale per gate G

---

## 10) Nota operativa

Questo piano è intenzionalmente **incrementale e anti-big-bang**: preserva OpenCode corrente, abilita ARIA in modalità opt-in e introduce componenti nuove con gate di verifica a ogni passaggio.
