# ARIA - Note Persistenti

## Utente
- **Nome**: Fulvio
- **Età**: 45 anni
- **Famiglia**: Sposato con Federica, figlia Adriana (21 mesi)
- **Città**: Caltanissetta, Sicilia
- **Lingua preferita**: Italiano

## Lavoro
- **Ruolo**: Consulente per la Pubblica Amministrazione
- **Settori principali**:
  - Progetti di innovazione tecnologica negli Uffici Giudiziari
  - Gestioni associate per enti locali (Comuni e Unioni di Comuni italiani)

## Preferenze
- Gli piace il tennis 🎾 (gioca)
- Serie crime e film 🎬
- Appassionato di tecnologia, informatica, AI, LLM, training e fine-tuning con librerie transformer (LoRA, QLoRA)
- Vibe coding / coding assistito da AI — ha creato aria stesso
- Suite Google Workspace (documenti, fogli, presentazioni — formati Office vari)
- Lavora molto in call online (Google Meet, Microsoft Teams)

## Tool
- Google Workspace (online)
- Google Meet, Microsoft Teams
- AI coding tools (aria, altri)

# Scopo di questo file
`ARIA.md` è la memoria operativa persistente del repository: deve ridurre il tempo di discovery degli agenti, aumentare coerenza implementativa e migliorare affidabilità delle esecuzioni multi-sessione.

## Regole di aggiornamento
- Aggiorna la sezione "Note Persistenti" ogni volta che ritieni vi sia una nuova informazione che possa servire a profilare l'utente con l'obiettivo di fornire un servizio tarato sui propri bisogni, gusti e inclinazioni.

#SISTEMA ARIA

## Mappa architetturale reale (codebase)
- `internal/aria/core/` -> Orchestrator, decision/planning/review pipeline.
- `internal/aria/agency/` -> Agency specializzate + supervisor/registry/workflow/synthesis.
- `internal/aria/agent/` -> contratto agente esteso (skills, learning, state).
- `internal/aria/skill/` -> skill modulari eseguibili, registry skill.
- `internal/aria/routing/` -> classificazione, policy router, capability registry.
- `internal/aria/memory/` -> memory service 4-layer + embedding + retention.
- `internal/aria/scheduler/` -> scheduling task persistenti e recurring.

## Agencies disponibili
- `development` - coding, review, architecture/design, bridge con coder legacy
- `knowledge` - ricerca multi-provider, supervisor/router, workflow engine, synthesis
- `nutrition` - nutrizione/ricette/diete (implementata)
- `weather` - meteo/forecast/alerts (POC attivo)

### Sistema gerarchico (ordine di orchestrazione)
1. **Orchestrator**: riceve query, classifica, applica policy, prepara contesto memoria.
2. **Agency**: dominio specialistico (development, knowledge, nutrition, weather).
3. **Agent**: esecuzione specializzata nel dominio.
4. **Skill**: capacità riusabile orientata al task.
5. **Tool/MCP/provider**: esecuzione concreta (file, bash, search, APIs).

### Routing operativo (runtime)
- Pipeline standard: **Classify -> PolicyRouter -> CapabilityRegistry -> Route decision**.
- Fallback: legacy path quando confidenza è sotto soglia o target non disponibile.
- Feedback loop: `RecordRoutingFeedback()` + `AdjustRoutingPolicy()` per auto-tuning.

# Memoria ARIA (4 layer) — riferimento operativo
## 1) Working Memory (contesto sessione)
- Cache in-memory (`sync.Map`) + persistenza DB (`working_memory_contexts`) con TTL e GC.
- Contiene contesto attivo: sessione, task, messaggi, file, metadata.
## 2) Episodic Memory (storia/esecuzioni)
- Tabella episodi con task/actions/outcome/feedback.
- Recupero: filtri + ranking (successo/recency) + similarità ibrida.
- Embeddings asincroni, cache vettoriale, backfill disponibile.
### 3) Semantic Memory (conoscenza/fatti)
- Facts con dominio/categoria/confidenza/fonte.
- Deduplica contenuti, tracking uso (`use_count`, `last_used`), query knowledge base.
### 4) Procedural Memory (workflow appresi)
- Procedure versionate con trigger, steps, success rate, uso.
- Discovery automatica pattern da episodi riusciti.
- Matching di procedure applicabili per nuovi task.
### Bootstrap memoria nel contesto (OBBLIGATORIO)
Prima di ogni esecuzione significativa:
1. `GetContext(sessionID)`
2. `GetSimilarEpisodes(situation)`
3. `FindApplicableProcedures(task)`
4. `SearchEpisodes(sessionID, limit=10)`
Questo contesto viene passato al task (`working_context`, `similar_episodes`, `applicable_procedures`) prima di delegare all’agency.

## Best practice per prompt/rules (AGENTS.md / rules.md)
### Principi chiave
- Regole **specifiche e verificabili**, non vaghe.
- Preferire istruzioni **repo-aware** (path reali, comandi reali, pattern reali).
- Imporre output con **checklist di verifica** (test/lint/vet/build) prima della chiusura.
- Favorire **file-scoped checks** quando disponibili; usare full-suite solo quando richiesto/necessario.
- Definire chiaramente azioni **consentite senza conferma** vs **ask-first**.
### Regole pratiche per ARIA (da seguire sempre)
- Leggi bene la richiesta dell'utente. Se non è chiara, chiedi subito chiarimenti, prima di iniziare a lavorare.
- Individua quale o quali agenzie possono svolgere il compito in maniera corretta, esperta, efficiente ed efficace.
- Attiva sempre le agenzie e segui la gerarchia dell'organizzaizone.
- Non inventare dati o informazioni. Devi basare la tua risposta solo ed esclusivamente sui dati e le informazioni recuperati tramite chiamate API o altri tool da fonte esterna.
- Se un task non riesci a portarlo a compimento in maniera corretta e completa, ammetti subito i tuoi limiti.

## Template prompt operativo (riusabile)
```md
Obiettivo: <risultato atteso e criterio di accettazione>
Scope: <file/package inclusi> | Esclusioni: <file/package esclusi>
Vincoli: <performance/sicurezza/compatibilità/stile>
Architettura: rispetta Orchestrator -> Agency -> Agent -> Skill -> Tool
Memoria: bootstrap 4-layer + riuso procedure applicabili
Verifica: esegui test/vet/build pertinenti e riporta evidenze sintetiche
Output: modifiche principali + verifiche + rischi/limiti residui
```
## Policy Git & sicurezza operativa
- Mai usare comandi distruttivi irreversibili senza esplicita autorizzazione.
- Evitare force push su main/master.
- Non includere file sensibili (`.env`, credenziali, token) nei commit.
- Preferire commit atomici e messaggi orientati al “perché”.
## Politica aggiornamento ARIA.md (obbligatoria)
Aggiornare questo file quando emergono:
- nuovi comandi affidabili di verifica o build;
- nuovi vincoli architetturali consolidati;
- nuovi pattern procedurali ad alto riuso;
- nuove preferenze stabili di stile/workflow.
### Cadenza consigliata
- Revisione leggera: settimanale.
- Revisione strutturale: mensile.
- Aggiornamento immediato dopo cambi architetturali rilevanti.
### Regola editoriale
- Mantenere contenuto pratico, sintetico, non ridondante.
- Ogni sezione deve avere impatto operativo diretto.
