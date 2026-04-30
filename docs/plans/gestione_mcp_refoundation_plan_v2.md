# Piano di Refoundation MCP per ARIA — v2 (rollback-first)

> **Data**: 2026-04-29  
> **Owner proposto**: ARIA platform / Fulvio  
> **Input primari**: `docs/plans/gestione_mcp_refoundation_plan.md`, `docs/analysis/analisi_sostenibilita_mcp_report.md`  
> **Vincoli autoritativi**: `AGENTS.md`, `docs/foundation/aria_foundation_blueprint.md` (§10, §14, P1/P2/P7/P8/P9/P10)  
> **Fonti verificate**: `.aria/kilocode/mcp.json`, `.aria/kilocode/agents/search-agent.md`, wiki MCP, Context7 (`/modelcontextprotocol/modelcontextprotocol`, `/lastmile-ai/mcp-agent`, `/metatool-ai/metamcp`)

---

## 1. Obiettivo

Rivedere la refoundation MCP di ARIA introducendo **meccanismi di rollback sicuri, modulari e robusti** senza compromettere l'architettura attuale, che oggi **funziona** e deve essere trattata come **baseline protetta**.

Il piano v2 mantiene gli obiettivi del v1:

1. ridurre costo di startup e di contesto;
2. eliminare drift fra config, agenti e runtime isolato;
3. introdurre governance esplicita su dominio, tier, ownership e lifecycle;
4. abilitare crescita progressiva senza complessità prematura;

ma aggiunge un vincolo esplicito:

5. **ogni fase deve essere reversibile in modo rapido e con blast radius limitato**.

---

## 2. Executive Summary

Il piano v1 individua bene il problema di governance e crescita, ma tratta il refactor soprattutto come percorso di ottimizzazione. Manca invece una disciplina esplicita di **cutover reversibile**.

Il principio guida di questa v2 è:

> **l'architettura corrente è il last known good (LKG); la refoundation è un overlay progressivo, non una sostituzione irreversibile.**

Da questo derivano quattro decisioni forti:

1. **config-plane first**: la refoundation deve toccare prima catalogo, profili, exposure e validazione; non storage, credenziali o stato persistente;
2. **cutover per dominio, mai globale**: `search` è il solo dominio candidato a sperimentazione più aggressiva;
3. **direct path preservato**: ogni nuovo layer (`tool search`, lazy loading, gateway) deve poter essere bypassato verso il path diretto esistente;
4. **rollback testato, non solo documentato**: ogni fase deve includere un drill di rollback in ambiente isolato.

La direzione raccomandata resta progressiva:

1. congelare e classificare la baseline attuale;
2. introdurre catalogo e drift checks in **observe-only / shadow mode**;
3. attivare bootstrap ottimizzato solo dietro flag e con schema snapshots;
4. valutare un gateway **solo per search** e solo con bypass hard verso il direct path.

---

## 3. Stato Attuale da Preservare

### 3.1 Baseline operativa osservata

Fonte: `.aria/kilocode/mcp.json` interrogato il 2026-04-29.

- **Server dichiarati**: 16
- **Server abilitati**: 15
- **Server disabilitati**: 1 (`playwright`)
- **Domini presenti**: `core`, `search`, `workspace`, `productivity`, `experimental`

### 3.2 Path diretto corrente

```text
Kilo/ARIA session
  -> carica config MCP piatta
  -> avvia server stdio o wrapper locali
  -> espone tool via allowed-tools / mcp-dependencies
  -> conductor delega ai sub-agent
```

### 3.3 Perché questa baseline va protetta

Perché è già conforme ai vincoli fondamentali del blueprint in forma sufficiente:

- **P1**: isolamento in `.aria/*` e launcher dedicato;
- **P2**: nessuna modifica al codice upstream di Kilo;
- **P8/P9**: scoping per agente già presente, anche se incompleto;
- **P10**: governance documentale già attiva via wiki + ADR.

Il problema attuale non è “architettura rotta”, ma **drift, costo operativo e assenza di meccanismi formali di rollback**.

---

## 4. Invarianti di Rollback (nuove, inderogabili per la refoundation)

1. **La baseline corrente deve restare sempre rilanciabile**.
   - Nessuna fase può rimuovere il path diretto esistente prima del superamento dei gate e di una finestra di stabilità.

2. **Nessuna migrazione distruttiva di stato**.
   - La refoundation MCP non deve richiedere migrazioni irreversibili di `.aria/runtime` o `.aria/credentials`.

3. **Cutover solo perimetralmente limitati**.
   - Ogni attivazione deve dichiarare blast radius: `server`, `domain`, `session`, `global`.
   - `global` è vietato finché non sono stabilizzati i cutover `domain`.

4. **Ogni nuovo layer deve avere bypass esplicito**.
   - Se si introduce gateway o lazy path, il path diretto precedente deve restare disponibile.

5. **Le superfici auth/write restano conservative**.
   - Cambiamenti che toccano `google_workspace`, credenziali o superfici write-capable richiedono gate HITL coerente con **P7**.

6. **Rollback drill obbligatorio**.
   - Nessuna fase si considera completata senza una prova di ritorno alla baseline in ambiente isolato.

7. **Retention window legacy obbligatoria**.
   - Config, prompt, wrapper e mapping legacy restano congelati per 14-30 giorni dopo ogni cutover significativo.

---

## 5. Meccanismi di Rollback Raccomandati

| Priorità | Meccanismo | Razionale | Trigger | Blast radius massimo |
|---|---|---|---|---|
| P0 | **Baseline protetta / last-known-good** | la baseline corrente diventa il riferimento operativo e documentale | startup failure, smoke test falliti, mismatch exposure | domain/session |
| P0 | **Rollback config-plane only** | evita danni a runtime, memoria, OAuth e credenziali | qualsiasi modifica che richieda migrazione di stato | session/domain |
| P0 | **Schema snapshots + capability gate** | `initialize` + `tools/list` diventano guardrail prima dell'attivazione | diff schema non approvato, capability non supportata | server |
| P0 | **Cutover per dominio** | rispetta P9 e riduce impatto | regressione in `search`, `workspace` o `productivity` | domain |
| P1 | **Direct-path bypass** | gateway o lazy loading devono essere overlay reversibili | latenza, alias mismatch, routing errato | domain |
| P1 | **Quarantena per singolo server** | un server guasto non deve forzare rollback totale | crash wrapper, auth mancante, schema drift locale | server |
| P1 | **Shadow mode / observe-only** | consente validazione senza diventare active path | drift non compreso, metriche insufficienti | session/domain |
| P2 | **Retention window legacy** | facilita recovery tardivi e debugging | regressione post-cutover | domain |
| P2 | **Rollback drill per fase** | evita piani di rollback solo teorici | ogni gate di uscita | session/domain |

### 5.1 Profilo baseline / candidate / shadow

La v2 raccomanda un modello minimo a profili:

- **baseline**: fotografia operativa dell'assetto corrente funzionante;
- **candidate**: configurazione derivata dal catalogo o dal nuovo layer in valutazione;
- **shadow**: stessa logica del candidate, ma solo in observe-only / logging / validation mode.

Questo non implica un sistema complesso: basta una selezione profilo nel launcher o nella catena di sync della config isolata.

### 5.2 Rollback nel config plane, non nel data plane

Il rollback deve avvenire su:

- inventory/catalogo MCP;
- file generati (`mcp.json`, exposure matrix, metadata);
- attivazione/disattivazione per dominio o server;
- routing verso gateway vs direct path.

Non deve avvenire su:

- DB della memoria;
- token OAuth persistiti;
- secret store SOPS;
- session state persistente.

### 5.3 Compatibilità verificata con snapshot

Per ogni server serve un bundle minimo versionato:

- `serverInfo`
- capabilities negoziate
- `tools/list` atteso
- eventuali metadata/notes di compatibilità

Se il bundle reale diverge in modo non approvato:

- il server va in **quarantena**;
- il resto dell'architettura rimane vivo;
- il cutover non procede.

---

## 6. Architettura Target Raccomandata (rollback-aware)

## 6.1 Livello A — Catalogo canonico MCP

Confermata la raccomandazione del v1:

`docs/foundation/mcp_catalog.yaml` oppure `.aria/config/mcp_catalog.yaml`

Campi minimi per server:

- `name`
- `domain`
- `owner_agent`
- `tier`
- `transport`
- `lifecycle`
- `auth_mode`
- `statefulness`
- `expected_tools`
- `risk_level`
- `cost_class`
- `source_of_truth`
- **`rollback_class`** (`server`, `domain`, `session`)
- **`baseline_status`** (`lkg`, `candidate`, `shadow`, `disabled`)

## 6.2 Livello B — Baseline / Candidate / Shadow profiles

La v2 introduce un piano logico a tre profili:

```text
baseline  -> architettura attuale funzionante (LKG)
candidate -> nuova configurazione/refoundation attiva dietro gate
shadow    -> osservazione/validazione senza prendere il path attivo
```

Implementazione minima raccomandata:

- profilo attivo selezionabile nel launcher o nella sync chain;
- baseline mantenuta in repo come snapshot esplicito;
- candidate generato o validato a partire dal catalogo;
- shadow usato per drift checks, schema checks e benchmark comparativi.

## 6.3 Livello C — Core vs non-core con rollback esplicito

Always-on confermati come **core**:

- `filesystem`
- `git`
- `github`
- `sequential-thinking`
- `aria-memory`
- `fetch`

Non-core e quindi primi candidati a disable/quarantena selettiva:

- `search`: `searxng-script`, `reddit-search`, `tavily-mcp`, `exa-script`, `brave-mcp`, `pubmed-mcp`, `scientific-papers-mcp`
- `workspace`: `google_workspace`
- `productivity`: `markitdown-mcp`
- `experimental`: `playwright`

## 6.4 Livello D — Direct path preservato

Ogni percorso nuovo deve restare un overlay:

```text
search-agent
  -> [candidate path: gateway / lazy / tool-search]
  -> [bypass] direct provider MCP path esistente
```

La regola è semplice:

- il candidate path può essere attivato;
- il direct path non può essere eliminato nello stesso sprint;
- la rimozione del path legacy richiede una finestra di stabilità e ADR dedicato.

## 6.5 Livello E — Gateway solo su search e solo dietro flag

Confermata la direzione del v1, con vincolo aggiuntivo:

- **gateway solo per `search`**;
- **sempre dietro flag**;
- **sempre con bypass hard** verso il direct path.

Funzioni consentite nel gateway v1:

- aliasing coerente;
- health-state registry;
- logging unificato;
- fallback metadata;
- caching di discovery metadata.

Funzioni escluse dal gateway v1:

- sostituzione totale dell'inventory MCP;
- multi-tenant auth;
- write-path su sistemi esterni;
- universal gateway per tutto ARIA.

---

## 7. Piano di Implementazione v2

## Fase 0 — Freeze della baseline e mappa di rollback (1 giorno)

### Obiettivi
- congelare il last known good;
- definire il perimetro del rollback prima di qualsiasi refactor.

### Attività
1. Fotografare l'assetto corrente come baseline esplicita.
2. Mappare per ogni server/domain:
   - owner
   - tier
   - direct path attuale
   - blast radius
   - trigger di rollback
3. Verificare mismatch config/exposure già noti.
4. Produrre una **rollback matrix** iniziale.

### Deliverable
- baseline MCP documentata
- matrice server/domain -> rollback scope
- tabella `direct path` per dominio

### Gate di uscita
- esiste una baseline LKG esplicita;
- esiste almeno un percorso documentato di ritorno per ogni dominio.

### Rollback della fase
- nessun rischio runtime: fase puramente documentale/configurativa.

## Fase 1 — Hardening in shadow mode (2-3 giorni)

### Obiettivi
- introdurre governance senza cambiare il path attivo.

### Attività
1. Introdurre `mcp_catalog.yaml`.
2. Validare o generare `mcp.json` dal catalogo.
3. Aggiungere snapshot `tools/list` e capability bundle per server.
4. Introdurre drift checks:
   - catalogo vs `mcp.json`
   - catalogo vs prompt/dependencies
   - snapshot atteso vs schema reale
5. Eseguire tutto in **shadow/observe-only mode**.

### Deliverable
- catalogo v1
- validatore drift
- schema snapshots
- report shadow mode

### Gate di uscita
- 100% server classificati;
- 0 server orfani;
- nessun mismatch critico prompt/config;
- shadow mode verde.

### Rollback della fase
- disattivare catalog-driven generation;
- tornare alla baseline documentata;
- nessun impatto su runtime state.

## Fase 2 — Bootstrap ottimizzato dietro flag (2-4 giorni)

### Obiettivi
- ridurre startup/context senza perdere reversibilità.

### Attività
1. Eseguire capability probe del client Kilo per:
   - tool search
   - lazy loading
   - per-server instructions
2. Attivare il candidate path **solo** se il probe è positivo.
3. Limitare il cutover al bootstrap/scoping, non ai dati.
4. Generare exposure matrix dal catalogo.
5. Misurare benchmark pre/post:
   - tempo startup
   - processi MCP
   - memoria indicativa
   - contesto iniziale

### Deliverable
- benchmark pre/post
- policy core/non-core operativa
- candidate bootstrap flaggato

### Gate di uscita
- drift checks verdi;
- smoke tests dominio verdi;
- regressioni entro soglie concordate;
- rollback drill eseguito una volta.

### Rollback della fase
- disabilitare tool search/lazy;
- ripristinare bootstrap baseline;
- conservare snapshot per analisi delta.

## Fase 3 — Search Gateway PoC con bypass hard (4-6 giorni)

### Obiettivi
- introdurre governance aggiuntiva dove serve davvero, senza lock-in.

### Attività
1. Valutare MetaMCP vs gateway minimo locale.
2. Attivare il gateway **solo** su `search`.
3. Mantenere il direct path precedente sempre richiamabile.
4. Registrare health, alias, fallback reason, latency delta.
5. Eseguire canary / shadow comparativo prima dell'attivazione piena di dominio.

### Deliverable
- PoC search-gateway
- runbook di bypass
- benchmark latenza/affidabilità

### Gate di uscita
- nessuna regressione utente percepibile;
- osservabilità migliore della baseline;
- bypass funzionante e provato.

### Rollback della fase
- bypass del gateway;
- ritorno al direct path `search-agent -> provider MCP`;
- nessun impatto su `workspace` / `productivity`.

## Fase 4 — Governance permanente e decommission controllato (1-2 giorni + continuo)

### Obiettivi
- prevenire nuovo drift;
- evitare che il legacy venga rimosso troppo presto.

### Attività
1. Formalizzare checklist MCP con sezione rollback obbligatoria.
2. Aggiornare wiki e runbook con baseline/candidate/fallback path.
3. Definire retention window legacy 14-30 giorni.
4. Richiedere ADR per ogni rimozione definitiva di un path legacy importante.

### Deliverable
- checklist MCP aggiornata
- wiki aggiornata
- ADR backlog aggiornato

### Gate di uscita
- ogni nuovo MCP/cutover dichiara rollback scope, trigger e runbook.

### Rollback della fase
- governance only; nessun runtime cutover consentito in questa fase.

---

## 8. Rollback Matrix Minima

| Fase | Scope attivazione | Artefatto attivato | Rollback minimo richiesto | Blast radius target |
|---|---|---|---|---|
| 0 | documentation | baseline map | n/a | none |
| 1 | config/shadow | catalogo + drift checks | ignorare candidate e tornare alla baseline | session |
| 2 | bootstrap/domain | lazy/tool-search candidate | disabilitare flag e ripristinare bootstrap baseline | domain |
| 3 | search domain | gateway candidate | bypass hard al direct path | domain |
| 4 | governance | checklist/ADR/wiki | nessun rollback runtime necessario | none |

---

## 9. Gate di Attivazione Obbligatori

Prima di qualsiasi cutover reale devono essere verdi tutti questi gate:

1. **baseline metrics captured**
2. **drift checks green**
3. **schema snapshot compatibility green**
4. **smoke tests di dominio green**
5. **rollback action documentata**
6. **rollback drill eseguito almeno una volta**
7. **HITL approval** se il cambiamento tocca superfici auth/write

---

## 10. Rischi e Mitigazioni

| Rischio | Impatto | Mitigazione v2 |
|---|---|---|
| Attivare ottimizzazioni senza fallback | regressioni prolungate | direct-path preservation + flagging |
| Catalogo corretto ma non enforced | drift ricorrente | shadow mode + drift validator |
| Schema drift di un solo server blocca tutto | rollback eccessivo | quarantena per-server |
| Gateway introdotto troppo presto | complessità inutile | solo `search`, solo PoC, solo con bypass |
| Refoundation tocca credenziali/runtime state | rischio operativo alto | config-plane only |
| Legacy rimosso troppo presto | recovery lenta | retention window + ADR per decommission |
| Over-engineering | rallentamento del progetto | YAGNI: baseline, flag, domain cutover prima del resto |

---

## 11. KPI di Successo

### KPI tecnici
- startup sessione ARIA
- contesto iniziale speso per tool definitions
- numero di processi MCP al cold start
- mismatch catalogo/config/prompt = 0
- percentuale server con owner/domain/tier/lifecycle/rollback_class definiti = 100%

### KPI di rollback
- tempo di ritorno a baseline per cutover di dominio
- numero di rollback riusciti su drill / numero di drill eseguiti
- percentuale cutover con bypass funzionante provato = 100%
- numero di rollback che richiedono interventi su runtime state = 0

### KPI operativi
- numero di incidenti dovuti a drift MCP
- numero di server configurati ma non esposti correttamente
- tempo per aggiungere un nuovo MCP con piano di rollback completo

---

## 12. File da Creare / Aggiornare

### Nuovi artefatti raccomandati
- `docs/plans/gestione_mcp_refoundation_plan_v2.md` — questo piano
- `docs/llm_wiki/wiki/mcp-architecture.md` — aggiornare con baseline/candidate/fallback
- `.aria/config/mcp_catalog.yaml` oppure `docs/foundation/mcp_catalog.yaml`
- `scripts/check_mcp_drift.py` — validazione catalogo/config/prompt/schema
- `.aria/runtime/mcp-schema-snapshots/` — snapshot di discovery/capabilities per server
- `docs/operations/mcp_cutover_rollback.md` — runbook dedicato (raccomandato, non bloccante per Fase 0)

### Aggiornamenti previsti
- `docs/analysis/analisi_sostenibilita_mcp_report.md` — nota sul fatto che v2 introduce rollback-first
- `.aria/kilocode/agents/*.md` — riallineamento exposure solo dopo Fase 1
- `.aria/kilocode/mcp.json` — eventuale generazione/validazione dal catalogo
- `bin/aria` — eventuale selezione profilo minima solo quando necessaria

---

## 13. Impatti su Blueprint, ADR e Wiki

### Blueprint

La v2 **non richiede subito** un nuovo principio globale. La modifica più prudente è:

- rafforzare §10.5 con l'obbligo di direct fallback path per ottimizzazioni MCP;
- rafforzare §14 con eventi di osservabilità relativi a cutover/rollback:
  - `profile`
  - `domain`
  - `fallback_reason`
  - `schema_version`
  - `rollback_event`

### ADR raccomandati

Confermati quelli del v1, più uno aggiuntivo:

1. **ADR — MCP catalog as single source of truth**
2. **ADR — Core vs non-core lifecycle policy**
3. **ADR — Tool search / lazy loading enablement decision**
4. **ADR — Search gateway introduction** (solo se PoC approvato)
5. **ADR — MCP Cutover and Rollback Policy**

L'ADR di rollback deve definire almeno:

- baseline/candidate/shadow semantics
- direct-path preservation
- retention window legacy
- config-plane only rule
- rollback drill requirement

### Wiki

Aggiornare:

- `mcp-architecture.md` con tripla vista `baseline / candidate / fallback path`
- `aria-launcher-cli-compatibility.md` quando esisterà selezione profilo reale
- `log.md` con ogni attivazione e ogni rollback come eventi di prima classe

---

## 14. Sequenza Operativa Consigliata

```text
Step 1  Freeze baseline attuale come LKG
Step 2  Mappa direct path e blast radius per dominio/server
Step 3  Introduci catalogo e drift checks in shadow mode
Step 4  Aggiungi schema snapshots e capability gates
Step 5  Attiva bootstrap ottimizzato solo dietro flag
Step 6  Esegui rollback drill
Step 7  Valuta search gateway PoC solo con bypass hard
Step 8  Decommission legacy solo dopo retention window + ADR
```

---

## 15. Conclusione

La refoundation MCP di ARIA non deve partire da un presupposto di rottura, ma da un presupposto di **continuità controllata**.

La priorità corretta non è “cambiare architettura”, ma:

- trattare l'assetto attuale come baseline protetta;
- eliminare il drift senza toccare lo stato persistente;
- introdurre ottimizzazioni solo dietro gate, flag e snapshot;
- limitare ogni esperimento a dominio, server o sessione;
- rendere il rollback una proprietà operativa testata.

La sequenza prioritaria diventa quindi:

> **baseline authority -> rollback invariants -> drift elimination -> measured optimization -> selective gatewaying**

---

## Provenance

- Source: `docs/plans/gestione_mcp_refoundation_plan.md` (read 2026-04-29)
- Source: `docs/analysis/analisi_sostenibilita_mcp_report.md` (read 2026-04-29)
- Source: `AGENTS.md` (read 2026-04-29)
- Source: `docs/foundation/aria_foundation_blueprint.md` §10, §14, §16 (read 2026-04-29)
- Source: `.aria/kilocode/mcp.json` (read 2026-04-29)
- Source: `.aria/kilocode/agents/search-agent.md` (read 2026-04-29)
- Source: `docs/llm_wiki/wiki/index.md` (read 2026-04-29)
- Source: `docs/llm_wiki/wiki/log.md` (read 2026-04-29)
- Source: `docs/llm_wiki/wiki/mcp-architecture.md` (read 2026-04-29)
- Source: Context7 `/modelcontextprotocol/modelcontextprotocol` (queried 2026-04-29; initialize/capability negotiation, `tools.listChanged`)
- Source: Context7 `/lastmile-ai/mcp-agent` (queried 2026-04-29; scoped server sets, connection persistence)
- Source: Context7 `/metatool-ai/metamcp` (queried 2026-04-29; namespaces, middleware, selective proxying)
- Source: Sub-agent synthesis `general` task `ses_225a80967ffeplcgnfnPjA2zhQ` (2026-04-29)
