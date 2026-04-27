# Handoff: Architettura Auto-Persistence Memoria ARIA

**Data:** 2026-04-27  
**Da:** GLM-5.1 (sessione ARIA corrente)  
**A:** Claude Code / Opus 4.7  
**Scopo:** Analisi architetturale e decisione finale sul sistema di auto-persistenza della memoria  
**Branch:** `fix/memory-recovery`  
**Stato:** Richiede decisione architetturale prima dell'implementazione

---

## 1. Contesto del Progetto

### 1.1 Cos'è ARIA

ARIA (Autonomous Reasoning & Intelligent Assistant) è un assistente personale AI local-first che gira su Kilo Code (CLI). Il repository è `/home/fulvio/coding/aria`. L'architettura è documentata in `docs/foundation/aria_foundation_blueprint.md` (~2000 righe).

### 1.2 Stack Tecnico

- **Runtime**: Kilo Code CLI (`kilo run --agent aria-conductor --auto`)
- **Linguaggio**: Python 3.11+ (`src/aria/`)
- **Memory DB**: SQLite WAL (`episodic.db`) + FTS5
- **MCP Server**: FastMCP 3.x (esposto come `aria-memory`)
- **Scheduler**: systemd user service (`aria-scheduler.service`)
- **Launcher**: `bin/aria` (Bash, gestisce isolamento runtime)

### 1.3 Principi Inderogabili (Le Dieci Regole — §16 Blueprint)

Questi vincoli sono **non-negotiabili**:

| # | Principio | Impatto su Auto-Persistenza |
|---|-----------|----------------------------|
| P1 | **Isolation First** | ARIA gira in HOME isolato (`$ARIA_HOME/.aria/kilo-home/`) |
| P2 | **Upstream Invariance** | NON modificare il codice sorgente di Kilo Code |
| P3 | **Local-first Privacy** | Tutto resta su disco locale, zero chiamate di rete |
| P5 | **Actor-Aware Memory** | Ogni entry ha un actor (USER_INPUT > TOOL_OUTPUT > AGENT_INFERENCE) |
| P6 | **Verbatim Preservation** | T0 è immutabile, solo INSERT, tombstones per delete |
| P7 | **HITL on Destructive** | Azioni distruttive richiedono approvazione umana |

---

## 2. Il Problema

### 2.1 Sintomo

Il sistema di memoria attuale **perde sistematicamente le risposte dell'assistant**. Solo l'input utente viene persistito.

### 2.2 Causa Radice

Il persistence system dipende dall'agente LLM che chiama esplicitamente tool MCP:

| Tool | Scopo | Compliance LLM |
|------|-------|----------------|
| `remember(actor=user_input)` | Persistire input utente | ✓ Funziona (verificato con smoke test REPL) |
| `complete_turn(response_text=...)` | Persistire risposta assistant | ✗ **LLM salta la chiamata** (verificato con smoke test REPL) |

**Perché `complete_turn` viene saltato:**
- L'LLM priorità completare la risposta vs chiamare un tool aggiuntivo
- Non può essere forzato con prompt engineering (già tentato)
- Il comportamento è intrinsecamente probabilistico, non deterministico

### 2.3 Verifica Empirica

Smoke test REPL (`bin/aria repl`):
```
Input utente: "ricordati che mi chiamo Fulvio Luca Daniele Ventura"
  → remember() chiamato ✓ → entry in episodic.db (actor=user_input)

Risposta assistant: "Ho memorizzato le tue preferenze sul nome, Fulvio."
  → complete_turn() NON chiamato ✗ → NESSUNA entry in episodic.db (actor=agent_inference)
```

Query di verifica su `kilo.db` (database sessioni Kilo):
```sql
-- Il tool remember è stato chiamato con successo:
SELECT data FROM part WHERE json_extract(data, '$.type') = 'tool'
  AND json_extract(data, '$.tool') = 'aria-memory_remember'
  AND json_extract(data, '$.state.status') = 'completed'
→ Risultato: input utente salvato con successo

-- Ma la risposta "Ho memorizzato..." non è mai arrivata a episodic.db
SELECT COUNT(*) FROM episodic WHERE actor = 'agent_inference';
→ Risultato: 0 (o solo entry dalla gateway path)
```

### 2.4 Impatto

Senza risposte assistant in memoria:
- **Recall incompleto**: `recall_episodic` restituisce solo metà della conversazione
- **CLM cieco**: la distillazione T0→T1 non può estrarre fatti dalle risposte
- **Contesto perso**: riprendere una conversazione è impossibile senza le risposte

---

## 3. Il Sistema di Memoria Esistente (Già Implementato)

### 3.1 Architettura a 5 Tier (Blueprint §5)

| Tier | Nome | Storage | Stato Implementazione |
|------|------|---------|----------------------|
| T0 | Episodic | SQLite WAL (`episodic.db`) | ✅ Implementato |
| T1 | Semantic | SQLite FTS5 | ✅ Implementato |
| T2 | Conceptual | LanceDB (lazy) | ⬜ Piano |
| T3 | Associative | SQLite graph | ⬜ Piano |
| T4 | Procedural | Filesystem SKILL.md | ⬜ Piano |

### 3.2 Schema T0 (Episodic) — `episodic.db`

```sql
CREATE TABLE episodic (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    ts INTEGER NOT NULL,         -- Unix timestamp
    actor TEXT NOT NULL,          -- user_input|tool_output|agent_inference|system_event
    role TEXT NOT NULL,           -- user|assistant|system|tool
    content TEXT NOT NULL,        -- VERBATIM, mai sintetizzato (P6)
    content_hash TEXT NOT NULL,   -- SHA-256 per dedup
    tags TEXT,                    -- JSON array
    meta TEXT                     -- JSON dict
);

CREATE TABLE episodic_tombstones (
    episodic_id TEXT PRIMARY KEY,
    tombstoned_at INTEGER NOT NULL,
    reason TEXT NOT NULL
);
```

### 3.3 MCP Server — 12 Tool (`src/aria/memory/mcp_server.py`)

1. `remember` — Scrive entry T0
2. `complete_turn` — (AGGIUNTO) Persiste risposta assistant + tool output
3. `recall` — Ricerca semantica + episodica
4. `recall_episodic` — Recall cronologico con query FTS5
5. `distill` — Trigger CLM distillation
6. `curate` — Promote/demote/forget con HITL
7. `forget` — Soft delete + tombstone
8. `stats` — Telemetria
9. `hitl_list` — Lista HITL pending
10. `hitl_cancel` — Cancella richiesta HITL
11. `hitl_approve` — Approva ed esegue azione HITL
12. `health` — Health check + stats

### 3.4 File Principali del Memory Subsystem

```
src/aria/memory/
├── __init__.py
├── episodic.py       # EpisodicStore (651 righe)
├── semantic.py       # SemanticStore con FTS5
├── clm.py            # Context Lifecycle Manager (T0→T1 distillation)
├── mcp_server.py     # FastMCP server (769 righe, 12 tool)
├── schema.py         # Pydantic v2 models (Actor, EpisodicEntry, SemanticChunk)
├── migrations.py     # Schema migrations
├── actor_tagging.py  # Actor trust scores
└── config.py         # (dovrebbe esistere) MemoryConfig
```

### 3.5 Flusso Dati Attuale

```
[REPL Path — Kilo TUI/CLI]
User input → Kilo Code → aria-conductor agent
  → agent chiama aria-memory/remember() ← LLM chiama questo ✓
  → agent risponde con testo
  → agent dovrebbe chiamare complete_turn() ← LLM NON chiama questo ✗

[Gateway Path — Telegram]
User input → Gateway → ConductorBridge
  → bridge.insert(EpisodicEntry) ← hardcoded, funziona ✓
  → bridge._distill_session_bg() ← post-session distillation ✓

[Scheduler Path]
Ogni 6h → memory-distill task → CLM.distill_range()
Ogni 6h → memory-wal-checkpoint → vacuum_wal()
```

---

## 4. Scoperta Critica: Il Database di Kilo Code

### 4.1 Kilo Code salva TUTTO in SQLite

Il database di Kilo Code si trova in:
```
.aria/kilo-home/.local/share/kilo/kilo.db  (2.4 GB, WAL mode)
```

### 4.2 Schema Rilevante (verificato direttamente)

```sql
CREATE TABLE session (
    id TEXT PRIMARY KEY,        -- es. "ses_234269f6affe5uld1Z6s6TbhEh"
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    time_created INTEGER NOT NULL,
    time_updated INTEGER NOT NULL,
    -- ... altri campi
);

CREATE TABLE message (
    id TEXT PRIMARY KEY,        -- es. "msg_dcbd97146001C8TLLGibnB23r8"
    session_id TEXT NOT NULL,
    time_created INTEGER NOT NULL,  -- Unix epoch ms
    data TEXT NOT NULL              -- JSON: {role, agent, tokens, modelID, finish, ...}
);

CREATE TABLE part (
    id TEXT PRIMARY KEY,        -- es. "prt_dcbd97c45001M41wWGiwrehHud"
    message_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    time_created INTEGER NOT NULL,
    data TEXT NOT NULL              -- JSON: varia per tipo
);
```

### 4.3 Tipi di Part (dati reali)

| `data.type` | Conteggio | Contenuto |
|---|---|---|
| `tool` | 841 | Nome tool, input, output, stato chiamata |
| `step-start` | 515 | Metadata snapshot |
| `step-finish` | 506 | Ragione completamento, token counts |
| `reasoning` | 504 | Traccia ragionamento LLM |
| **`text`** | **328** | **Testo utente/assistant — IL CONTENUTO REALE** |
| `patch` | 163 | Diff file |

### 4.4 Esempio: Turno Completo in kilo.db

```sql
-- Messaggio utente (role=user):
--   part type="text" → "ricordati che mi chiamo Fulvio Luca Daniele Ventura"

-- Messaggio assistant (role=assistant, finish=tool-calls):
--   part type="step-start"     → snapshot metadata
--   part type="reasoning"      → "The user is telling me their name..."
--   part type="tool"           → aria-memory_remember(input={actor:user_input, ...})
--   part type="step-finish"    → token counts

-- Messaggio assistant (role=assistant, finish=stop):
--   part type="step-start"     → snapshot metadata
--   part type="reasoning"      → "I've stored this information..."
--   part type="text"           → "Ho memorizzato le tue preferenze sul nome, Fulvio."
--   part type="step-finish"    → token counts
```

### 4.5 Query per Estrarre Turni da kilo.db

```sql
SELECT 
    m.id, m.session_id, m.time_created,
    json_extract(m.data, '$.role') as role,
    json_extract(m.data, '$.agent') as agent,
    p.id as part_id,
    json_extract(p.data, '$.type') as part_type,
    p.data as part_data
FROM message m
JOIN part p ON p.message_id = m.id
WHERE m.time_created > :watermark
  AND json_extract(m.data, '$.agent') = 'aria-conductor'
ORDER BY m.time_created ASC, p.time_created ASC
```

### 4.6 Dati Realmente Presenti

```
101 sessioni, 641 messaggi, 2857 parts
Ultima sessione attiva: ses_234269f6affe5uld1Z6s6TbhEh (2026-04-27 00:12)
```

---

## 5. Piano Proposto: "Echo" Auto-Persistence Sidecar

### 5.1 Documento Completo

Il piano proposto è in: **`docs/plans/auto_persistence_echo.md`**

### 5.2 Architettura di Echo

```
┌──────────────────┐     ┌──────────────────────────────────┐
│   Kilo Code      │     │   Echo Sidecar Daemon            │
│   (CLI/TUI)      │     │                                  │
│                  │     │   ┌────────────────────────┐     │
│  User ↔ LLM     │     │   │ WAL Watcher            │     │
│                  │     │   │ (watchdog/inotify)     │     │
│  Scrive in:      │     │   └──────────┬─────────────┘     │
│  kilo.db         │────>│              │ on change          │
│                  │     │   ┌──────────▼─────────────┐     │
│                  │     │   │ Turn Extractor          │     │
│                  │     │   │ (SQL query kilo.db)     │     │
│                  │     │   └──────────┬─────────────┘     │
│                  │     │              │                    │
│                  │     │   ┌──────────▼─────────────┐     │
│                  │     │   │ Dedup + Persist         │     │
│                  │     │   │ (EpisodicStore.insert)  │     │
│                  │     │   └────────────────────────┘     │
└──────────────────┘     └──────────────────────────────────┘
```

### 5.3 Come Funziona

1. **WAL Watcher**: Monitora `kilo.db-wal` per cambiamenti via `watchdog`/inotify
2. **Turn Extractor**: Query `kilo.db` per nuovi messaggi dopo l'ultimo watermark
3. **Dedup**: Content-hash deduplication (gestisce sovrapposizione con `remember()`)
4. **Persist**: Inserisce in `episodic.db` tramite `EpisodicStore.insert()`
5. **Watermark**: Salva progresso in `.aria/runtime/echo_watermark.json`

### 5.4 Cosa viene Persistito

| Fonte | Actor | Role | Contenuto |
|-------|-------|------|-----------|
| User `text` part | `USER_INPUT` | `user` | Messaggio utente completo |
| Assistant `text` part | `AGENT_INFERENCE` | `assistant` | Risposta assistant completa |
| Tool call `tool` part | `TOOL_OUTPUT` | `tool` | Nome tool + input + output |

### 5.5 Cosa viene Filtrato

- `step-start`, `step-finish`, `patch` (metadata, non contenuto)
- Messaggi da agenti non-ARIA
- Messaggi vuoti (nessun `text` o `tool` part)
- Messaggi più vecchi del watermark (già processati)

### 5.6 Mapping Session ID

Kilo usa `ses_XXXXXXXXXXX`, ARIA usa UUID. Il mapping proposto:
```python
uuid.uuid5(uuid.NAMESPACE_URL, f"kilo://{kilo_session_id}")
```

### 5.7 Deployment

Systemd user service `aria-echo.service`, integrato in `bin/aria echo`.

### 5.8 Vantaggi Chiave

- **Zero dipendenza dall'LLM** — legge il DB di Kilo direttamente
- **Completo** — cattura input utente, risposte assistant, e tool call
- **Upstream invariant (P2)** — accesso read-only a `kilo.db`
- **Dedup** — gestisce sovrapposizione con chiamate `remember()` esistenti

---

## 6. Ricerca: Approcci Alternativi Valutati

### 6.1 Kilo Code SSE Event Bus

Kilo ha un bus eventi interno (`TurnOpen`, `TurnClose`, `MessageV2.Event.PartUpdated`) esposto via `GET /global/event` SSE.

**Verdetto: ❌ Non viable** — L'endpoint SSE è disponibile solo quando il server HTTP/TUI è attivo. In modalità CLI (`kilo run --auto`), non ci sono porte in ascolto. Verificato: `ss -tlnp` non mostra porte Kilo.

### 6.2 Kilo Code Plugin System (TypeScript)

Kilo ha un sistema plugin sperimentale con hook `session.chat.before`, ecc.

**Verdetto: ❌ Non viable** — TypeScript-only, API sperimentale, Issue #5827 non risolto.

### 6.3 APSW `setupdatehook`

**Verdetto: ❌ Non viable** — Funziona solo same-process. Kilo gira come processo separato.

### 6.4 Prompt Engineering Hardening

**Verdetto: ❌ Già tentato** — L'LLM salta `complete_turn` nonostante prompt rafforzato.

### 6.5 WAL File Watching (Approccio Scelto)

**Verdetto: ✅ Viable** — Cross-process, zero-polling, local-first, compatibile con P2.

### 6.6 Approcci Non Valutati in Dettaglio (per Opus)

Questi approcci potrebbero essere rilevanti e richiedono analisi:

- **Mem0** (ex-EmbedChain): Pipeline estrazione fatti con LLM, dedup automatica
- **Zep**: Knowledge graph temporale per agent memory
- **LightRAG**: Costruzione incrementale knowledge graph
- **LlamaIndex**: Memory module con auto-persistence
- Estensione del **FastMCP middleware** per intercettare il traffico MCP
- Modifica del **Kilo session storage** con trigger SQLite

---

## 7. Punti Decisionali Richiesti

Questi sono i punti su cui serve analisi e decisione:

### 7.1 Decisione Architetturale Principale

**Echo sidecar (WAL watcher → kilo.db reader → episodic.db writer) è l'approccio giusto?**

Considerare:
- È coerente con l'architettura 5D del blueprint?
- Rispetta i principi P1-P7?
- È mantenibile a lungo termine?
- Quali sono i rischi di coupling con lo schema `kilo.db`?
- Esiste un approccio più semplice che abbiamo trascurato?

### 7.2 Domande Specifiche

1. **Tool call persistence**: I tool call vanno persistiti come `TOOL_OUTPUT`?
2. **Reasoning traces**: Le tracce di ragionamento LLM vanno persistite?
3. **Backfill**: Offrire una modalità `--backfill` per processare sessioni storiche?
4. **Integrazione**: Servizio standalone vs integrato in `aria-scheduler`?
5. **Alternative**: Esiste un approccio più elegante che non richiede un sidecar separato?

### 7.3 Rischi da Valutare

| Rischio | Impatto |
|---------|---------|
| Schema `kilo.db` cambia con aggiornamenti Kilo | Alto — Echo si rompe |
| Performance: `kilo.db` è 2.4 GB | Medio — query indicizzate dovrebbero essere veloci |
| Race condition: Echo legge mentre Kilo scrive | Basso — WAL mode gestisce concorrenza |
| Complessità operativa: un servizio in più da gestire | Medio |

---

## 8. Stato Attuale del Repository

### 8.1 Branch e Commit

```
Branch: fix/memory-recovery
Ultimi commit (13 totali):
1c0af41 feat(memory): add complete_turn tool for mandatory response persistence
fa2afbe docs(wiki): update with post-deploy fixes and operational status
5d8cb32 fix(memory): remember tool handles literal ${ARIA_SESSION_ID} and string tags
2c098bc docs(memory): document recovery plan and wiki refresh
7a3fa5e test(memory): roundtrip episodic→distill→recall covers conversational topics
65b279b fix(scheduler): vacuum_wal skips gracefully when episodic DB is busy
b4a7002 feat(memory): cleanup script tombstones benchmark entries (P6 compliant)
4d20941 feat(memory): inclusive CLM distillation for assistant turns and topic fallback
dd410fb feat(memory): recall_episodic accepts topic query and excludes benchmark tags
0041da4 fix(gateway): persist user/tool/assistant via EpisodicStore.insert
a388e88 fix(agent): enforce aria-conductor memory persistence per turn
9897dfc fix(memory): deterministic ARIA_SESSION_ID and strict-mode resolver
b4f58f2 chore(memory): ignore episodic DB recovery backups
```

### 8.2 Quality Gates Superati

- `ruff check .` ✓
- `ruff format --check .` ✓
- `mypy src` ✓
- `pytest -q` — 112 passed, 0 failures

### 8.3 Servizi Operativi

- `aria-scheduler.service` — active (running), Type=simple
- MCP server `aria-memory` — funziona via stdio con Kilo

### 8.4 File Piano Proposto

- `docs/plans/auto_persistence_echo.md` — Piano completo "Echo sidecar"

### 8.5 Riferimenti Wiki

- `docs/llm_wiki/wiki/index.md` — Indice wiki
- `docs/llm_wiki/wiki/log.md` — Log implementazione (815 righe)
- `docs/llm_wiki/wiki/memory-subsystem.md` — Architettura memoria (220 righe)

### 8.6 Piano Originale (Memory Recovery)

- `docs/plans/memory_recovery.md` — Piano completo (1735 righe)
  - §Phase 1 menziona "auto-persist new turns"
  - §File table menziona `scripts/memory/repl_persistence_sidecar.py` come sidecar opzionale
  - Contest7 check previsto per verificare se Kilo ha hook per-turn

---

## 9. Istruzioni per l'Analisi

### 9.1 Cosa Analizzare

1. **Coerenza architetturale**: Il piano Echo è coerente con il blueprint §5 (5D memory) e le Ten Commandments §16?
2. **Alternative**: Esistono approcci migliori o più semplici?
3. **Rischi**: I rischi identificati sono accettabili? Ce ne sono altri?
4. **Complessità**: Echo aggiunge complessità operativa giustificata?
5. **Futuro**: Questo approccio scales bene con T2-T4?

### 9.2 File da Leggere

**Obbligatori:**
- `docs/foundation/aria_foundation_blueprint.md` — §5, §6, §16 (memoria, scheduler, principi)
- `docs/plans/auto_persistence_echo.md` — Piano Echo completo
- `src/aria/memory/mcp_server.py` — MCP server attuale (12 tool)
- `src/aria/memory/episodic.py` — EpisodicStore (T0)
- `src/aria/memory/schema.py` — Schema Pydantic
- `src/aria/memory/clm.py` — CLM (distillazione T0→T1)

**Raccomandati:**
- `docs/plans/memory_recovery.md` — Piano recovery originale (contesto decisioni passate)
- `docs/llm_wiki/wiki/memory-subsystem.md` — Stato attuale memory subsystem
- `bin/aria` — Launcher (isolamento runtime, ARIA_SESSION_ID)
- `.aria/kilocode/agents/aria-conductor.md` — Prompt conductor (policy persistenza)

### 9.3 Output Atteso

Un'analisi strutturata con:

1. **Valutazione del piano Echo** (approvazione, modifiche, o rifiuto)
2. **Eventuali alternative** identificate
3. **Raccomandazioni specifiche** per l'implementazione
4. **Rischi aggiuntivi** non identificati
5. **Verdetto finale**: procedere, modificare, o ripensare

---

## 10. Contesto Aggiuntivo

### 10.1 Kilo Code Processi Attivi (verifica `ps aux`)

```
fulvio 690357  kilo /home/fulvio/coding/aria --agent aria-conductor
  → MCP server aria-memory attivo (stdio)
  → Altri MCP server: git, filesystem, github, fetch, sequential-thinking,
    tavily, firecrawl, brave, searxng, google_workspace, exa
```

### 10.2 Conteggi Database kilo.db

```
101 sessioni
641 messaggi  
2857 parts
```

### 10.3 Part Types Distribution

```
tool:        841  (29.4%)
step-start:  515  (18.0%)
step-finish: 506  (17.7%)
reasoning:   504  (17.6%)
text:        328  (11.5%)  ← Il contenuto conversazionale
patch:       163  (5.7%)
```

### 10.4 Database Size

```
kilo.db:        2.4 GB  (SQLite WAL, checkpoint periodico)
kilo.db-wal:    ~10 MB  (log delle modifiche recenti)
kilo.db-shm:    32 KB   (shared memory index)
episodic.db:    ~ordini di KB/MB (8 real entries dopo cleanup)
```

---

*Fine handoff. Questo documento contiene tutto il contesto necessario per un'analisi architetturale informata del sistema di auto-persistenza.*
