---
document: ARIA Phase 1 — Sprint 1.1 Implementation Plan
version: 1.1.0
status: implemented
date_created: 2026-04-20
last_review: 2026-04-20
owner: fulvio
phase: 1
sprint: "1.1"
canonical_blueprint: docs/foundation/aria_foundation_blueprint.md
blueprint_sections: ["§5", "§13", "§14.1", "§14.6"]
phase_overview: docs/plans/phase-1/README.md
---

# Sprint 1.1 — Credential Manager & Memoria Tier 0/1

## 1) Obiettivo, scope, vincoli

### 1.1 Obiettivo

Portare ARIA alla condizione operativa di **scrivere e leggere memoria persistente verbatim** (Tier 0) con un indice full-text (Tier 1), e di **acquisire/rilasciare chiavi API** in modo sicuro, rotazionale, auditato. Questo sprint pone le **fondazioni** su cui Sprint 1.2/1.3/1.4 costruiranno scheduler, gateway, sub-agenti.

### 1.2 In scope

- Modulo `src/aria/credentials/` completo: SOPS+age wrapper, keyring store, rotator con circuit breaker, audit logger, API unificata `CredentialManager`.
- Modulo `src/aria/memory/` con `schema.py` (Pydantic v2), `episodic.py` (SQLite WAL + FTS5), `clm.py` (compaction base extractive), `actor_tagging.py`.
- MCP server custom `aria-memory` (`src/aria/memory/mcp_server.py`, FastMCP 3.x) con 7 tool: `remember`, `recall`, `recall_episodic`, `distill`, `curate`, `forget`, `stats`.
- `src/aria/utils/logging.py` (JSON line, `trace_id` via `contextvars`, secret redaction).
- Schema SQLite validato contro `docs/foundation/schemas/sqlite_full.sql` esistente (non riscrivere, solo aggiungere FTS5 triggers se mancanti).
- Test unitari e integration (coverage ≥ 85% credentials, ≥ 80% memory).
- Benchmark di recall (fixture 1k entry) con p95 < 250ms.

### 1.3 Out of scope (Sprint 1.1)

- LanceDB / Tier 2 embedding (il modulo `semantic.py` stub con `NotImplementedError` controllato da feature flag `ARIA_MEMORY_T2=0`).
- Grafo associativo / Tier 3 (fase 2).
- Scheduler, Gateway, Conductor.
- Integrazione provider reali (Tavily/Brave/...): in questo sprint il `CredentialManager` sa leggere/rotare chiavi ma nessuno le consuma ancora.

### 1.4 Vincoli inderogabili (richiami blueprint)

- **P4 Local-First**: tutti i DB, chiavi, stato runtime locali. Nessuna sincronizzazione cloud.
- **P5 Actor-Aware Memory**: `EpisodicEntry.actor` obbligatorio, validato a schema (Pydantic + CHECK SQL).
- **P6 Verbatim Preservation**: nessuna `UPDATE` su `episodic.content`. Solo INSERT. Tombstone via tabella `episodic_tombstones` (soft delete).
- **P7 HITL**: `forget(id)` genera entry `hitl_pending` (stub in Sprint 1.1, wire reale in Sprint 1.2).
- **P9 ≤ 20 tool per sub-agente**: `aria-memory` MCP server espone **7** tool, ben dentro il budget.
- SQLite runtime ≥ 3.51.3 (`PRAGMA sqlite_version` check all'avvio; fail fast altrimenti).

## 2) Pre-requisiti

Verificabili con `./scripts/bootstrap.sh --check`:

- `sops`, `age`, `sqlite3 --version` ≥ 3.51.3 disponibili nel PATH
- `~/.config/sops/age/keys.txt` presente e leggibile (chmod 600)
- `.aria/credentials/.sops.yaml` presente con regole valide
- `.venv/` attiva, `uv sync --dev` senza errori
- `docs/foundation/schemas/sqlite_full.sql` presente (Phase 0)

## 3) Work Breakdown Structure (WBS)

### W1.1.A — Utilities di logging e config (abilitante)

**File da creare**: `src/aria/utils/logging.py`, `src/aria/utils/metrics.py` (stub per Sprint 1.2).

**API obbligatoria** (`aria.utils.logging`):

```python
from contextvars import ContextVar
from typing import Any
import logging
import json

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")

def get_logger(name: str) -> logging.Logger: ...
def set_trace_id(trace_id: str) -> None: ...
def new_trace_id() -> str: ...  # uuid4 hex[:12]
def redact_secret(value: str | None, keep_last: int = 4) -> str: ...
def log_event(logger: logging.Logger, level: int, event: str, **context: Any) -> None: ...
```

Requisiti:
- Output: JSON line con campi `ts` (ISO8601 UTC), `level`, `logger`, `event`, `trace_id`, `context`.
- File handler: `.aria/runtime/logs/<logger_root>-%Y-%m-%d.log`, rotazione giornaliera gzip (`logging.handlers.TimedRotatingFileHandler` con `when='midnight'`, `backupCount=90`).
- Stdout handler (solo se `sys.stdout.isatty()`).
- `redact_secret(None)` → `"<none>"`; `redact_secret("sk-abc1234567")` → `"***4567"`.

**Acceptance**:
- `pytest tests/unit/utils/test_logging.py` verde (10+ assertion minime: formato JSON, trace propagation, redaction, rotation logica).
- Nessun byte di chiave non redatta in un log di test deliberato.

### W1.1.B — Config loader (estensione/refactor)

**File**: `src/aria/config.py` (GIA esistente da Phase 0, estendere; non riscrivere da zero).

Aggiungere/normalizzare:
- Classe `AriaConfig` (`pydantic.BaseSettings`-style via `pydantic-settings` gia in deps? Se no, `BaseModel` + `os.environ`).
- Campi richiesti (default indicati):

```python
class AriaConfig(BaseModel):
    home: Path                  # ARIA_HOME
    runtime: Path               # ARIA_RUNTIME
    credentials: Path           # ARIA_CREDENTIALS
    log_level: str = "INFO"
    timezone: str = "Europe/Rome"
    locale: str = "it_IT.UTF-8"
    quiet_hours: str = "22:00-07:00"
    memory_t2_enabled: bool = False          # ARIA_MEMORY_T2
    memory_t0_retention_days: int = 365
    memory_t1_compression_after_days: int = 90
    sops_age_key_file: Path                  # SOPS_AGE_KEY_FILE
    telegram_whitelist: list[str] = []       # CSV in env
    # Phase 1 flags (saranno consumati in sprint 1.2-1.4)
```

**Acceptance**:
- Caricamento idempotente: `AriaConfig.load()` singleton safe cross-thread.
- `ARIA_HOME` non esistente -> `ConfigurationError` esplicito.
- Test: `tests/unit/test_config.py` valida env parsing, default, errori.

### W1.1.C — CredentialManager: SOPS adapter

**File**: `src/aria/credentials/sops.py`.

**Responsabilita**: wrapper sincrono del binary `sops` per decrypt/encrypt di `.aria/credentials/secrets/*.enc.yaml` e `.aria/runtime/credentials/providers_state.enc.yaml`.

**API**:

```python
class SopsError(Exception): ...

class SopsAdapter:
    def _init_(self, age_key_file: Path): ...
    def decrypt(self, path: Path) -> dict[str, Any]: ...      # yaml.safe_load
    def encrypt_inplace(self, path: Path, data: dict[str, Any]) -> None: ...
    def edit_atomic(self, path: Path, mutate_fn: Callable[[dict], dict]) -> None: ...
    def is_encrypted(self, path: Path) -> bool: ...            # check sops metadata
```

Requisiti implementativi:
- `decrypt`: `subprocess.run(["sops", "--decrypt", str(path)], check=True, capture_output=True, env=...)`. Env deve contenere `SOPS_AGE_KEY_FILE`.
- `encrypt_inplace`: scrittura atomica tmp + `sops --encrypt -i` + rename; permessi `0600`.
- `edit_atomic`: acquire `flock` su `<path>.lock` con timeout 10s (`fcntl.flock`, `LOCK_EX`), decrypt → mutate → encrypt → release.
- Timeout subprocess: 15s.
- Errori: convertire stderr SOPS in `SopsError` con messaggio azionabile (es. "age key file not found").

**Acceptance**:
- `tests/integration/credentials/test_sops.py` con age key di test (in `tests/fixtures/age/test_key.txt`) e file yaml sintetico. Verificare: decrypt=encrypt roundtrip, locking concorrente (2 thread), permessi 0600 post-encrypt.
- Nessun file plaintext residuo dopo crash simulato (prova con `kill -9` su figlio sops? opzionale; almeno fault injection via monkeypatch).

### W1.1.D — CredentialManager: KeyringStore

**File**: `src/aria/credentials/keyring_store.py`.

**Responsabilita**: persistenza refresh token OAuth (Google Workspace, futuri provider) via `keyring` (Secret Service su Linux, fallback age-file).

**API**:

```python
class KeyringStore:
    def _init_(self, service_prefix: str = "aria"): ...
    def put_oauth(self, service: str, account: str, refresh_token: str) -> None: ...
    def get_oauth(self, service: str, account: str) -> str | None: ...
    def delete_oauth(self, service: str, account: str) -> bool: ...
    def list_accounts(self, service: str) -> list[str]: ...   # best-effort
```

Requisiti:
- Service name: `{prefix}.{service}` (es. `aria.google_workspace`).
- Fallback quando `keyring.backend.fail.Keyring` rilevato (no Secret Service): usare `.aria/credentials/keyring-fallback/<service>-<account>.age` cifrato con **chiave separata** da SOPS (path `$HOME/.config/sops/age/keyring_fallback.txt` se presente, altrimenti errore esplicito).
- Detection backend all'init: log `event=keyring_backend` con nome backend.

**Acceptance**:
- Unit test con `keyring.backends.fake` (in memory).
- Integration test con Secret Service reale marker `@pytest.mark.requires_secret_service` (skip su CI headless senza).

### W1.1.E — CredentialManager: Rotator + Circuit Breaker

**File**: `src/aria/credentials/rotator.py`.

**Responsabilita**: gestione stato runtime per-chiave (credits_used, circuit_state, cooldown), strategia di selezione.

**Schema runtime state** (persistito via SOPS in `.aria/runtime/credentials/providers_state.enc.yaml`, come da blueprint §11.3):

```yaml
providers:
  tavily:
    rotation_strategy: least_used
    keys:
      - key_id: tvly-1
        credits_total: 1000
        credits_used: 0
        circuit_state: closed     # closed|open|half_open
        failure_count: 0
        cooldown_until: null       # ISO8601 UTC or null
        last_used_at: null
        last_error: null
```

**API**:

```python
class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class KeyInfo(BaseModel):
    provider: str
    key_id: str
    key: SecretStr
    credits_remaining: int | None
    circuit_state: CircuitState

class Rotator:
    def _init_(self, sops: SopsAdapter, state_path: Path, clock: Callable[[], datetime] = ...): ...
    def acquire(self, provider: str, strategy: Literal["least_used","round_robin","failover"] | None = None) -> KeyInfo: ...
    def report_success(self, provider: str, key_id: str, credits_used: int = 1) -> None: ...
    def report_failure(self, provider: str, key_id: str, reason: str, retry_after: int | None = None) -> None: ...
    def status(self, provider: str | None = None) -> dict: ...
```

Circuit breaker parametri (hardcoded in Sprint 1.1, tunabili in config Sprint 1.2):
- `OPEN` dopo **3 failure consecutivi in 5 min**.
- `cooldown_until = now + 30 min`.
- `HALF_OPEN` al primo `acquire` dopo cooldown: concede **1 probe**; success→`CLOSED`, failure→`OPEN` con cooldown raddoppiato (max 2h).
- `credits_remaining == 0` → key implicitamente skippata (non consumata circuit breaker).
- `clock` iniettato per testabilita.

Concorrenza: rotator usa `asyncio.Lock` per modifiche stato in-memory e `sops.edit_atomic` per flush. Flush opportunistico: ogni 5s OR su ogni `report_failure` con `circuit_state` cambiato, OR su shutdown (hook).

**Acceptance**:
- `tests/unit/credentials/test_rotator.py`: 20+ test. Casi: rotazione least_used bilanciata, passaggio closed→open→half_open→closed, lock reentrante, multi-provider isolation, recupero da state corrotto (fallback reset documentato in `rotator.recover_from_corruption()`).
- Nessun test di concorrenza con `time.sleep`: usare `pytest.freezegun` o clock mock.

### W1.1.F — CredentialManager: Audit logger

**File**: `src/aria/credentials/audit.py`.

**Responsabilita**: ogni invocazione `acquire`/`report_*` genera record JSON line su `.aria/runtime/logs/credentials-YYYY-MM-DD.log`.

**Formato** (coerente con blueprint §13.6):

```json
{"ts":"2026-04-20T14:32:10Z","op":"acquire","provider":"tavily","key_id":"tvly-1","result":"ok","credits_remaining":847,"trace_id":"abc123"}
```

Requisiti:
- Redaction obbligatoria: `key` completa MAI in log, solo `key_id`.
- Retention 90 giorni (reuso del handler `aria.utils.logging`).

**Acceptance**:
- Smoke test: `audit.record({...})` scrive correttamente linea; chiave sensibile non presente.

### W1.1.G — CredentialManager: API unificata

**File**: `src/aria/credentials/manager.py`.

Aggrega gli adapter sopra in una singola facciata:

```python
class CredentialManager:
    def _init_(self, config: AriaConfig | None = None): ...

    # API keys rotation
    def acquire(self, provider: str, strategy: str | None = None) -> KeyInfo: ...
    def report_success(self, provider: str, key_id: str, credits_used: int = 1) -> None: ...
    def report_failure(self, provider: str, key_id: str, reason: str, retry_after: int | None = None) -> None: ...
    def status(self, provider: str | None = None) -> dict: ...

    # OAuth (usato da Sprint 1.4 in modo reale)
    def get_oauth(self, service: str, account: str = "primary") -> OAuthBundle | None: ...
    def put_oauth(self, service: str, account: str, refresh_token: str) -> None: ...
    def revoke_oauth(self, service: str, account: str) -> None: ...
```

Entrypoint CLI: `python -m aria.credentials` (estendere `src/aria/credentials/_main_.py` esistente) con typer:

```
aria creds list [--provider PROVIDER]
aria creds rotate <provider>                    # forza round-robin su prossima key
aria creds status [--provider PROVIDER]
aria creds audit --tail 50
aria creds reload                               # rilegge api-keys.enc.yaml
```

**Acceptance**:
- `aria creds status` funziona con chiavi fittizie e stampa tabella ricca (`rich`).
- Integration test: decrypt stub → acquire → report_success → state persisted.

### W1.1.H — Memory: schema Pydantic

**File**: `src/aria/memory/schema.py`.

Seguire letteralmente il blueprint §5.5 (riportato qui come riferimento autoritativo):

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal, Optional
from uuid import UUID, uuid4

class Actor(str, Enum):
    USER_INPUT = "user_input"
    TOOL_OUTPUT = "tool_output"
    AGENT_INFERENCE = "agent_inference"
    SYSTEM_EVENT = "system_event"

class EpisodicEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    ts: datetime
    actor: Actor
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    content_hash: str
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, object] = Field(default_factory=dict)

class SemanticChunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_episodic_ids: list[UUID]
    actor: Actor
    kind: Literal["fact", "preference", "decision", "action_item", "concept"]
    text: str
    keywords: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    first_seen: datetime
    last_seen: datetime
    occurrences: int = 1
    embedding_id: Optional[UUID] = None

class ProceduralSkill(BaseModel):
    id: str
    path: str
    name: str
    description: str
    trigger_keywords: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    version: str = "1.0.0"
```

Aggiungere (non in blueprint ma richiesto da implementazione):
- `class MemoryStats(BaseModel)`: `t0_count`, `t1_count`, `sessions`, `last_session_ts`, `avg_entry_size`, `storage_bytes`.
- Funzione `content_hash(text: str) -> str` che ritorna `"sha256:<hexdigest>"`.

**Acceptance**:
- Pydantic v2 validation test: `actor` non valido, `ts` naive-datetime rifiutato (deve essere aware), `content` vuoto → accettato ma con warning.

### W1.1.I — Memory: Tier 0 (SQLite WAL)

**File**: `src/aria/memory/episodic.py`.

**Responsabilita**: CRUD su `episodic.db`, FTS5 sync, backup incrementale-friendly.

Uso schema gia definito in `docs/foundation/schemas/sqlite_full.sql`. Verificare e se mancanti aggiungere **triggers di sincronizzazione FTS5** (T0 → T1 non automatico: T1 e popolato dal CLM, non da trigger. Ma FTS5 virtual table `semantic` puo avere triggers su `semantic_chunks` per indicizzazione automatica).

**API obbligatoria** (async):

```python
class EpisodicStore:
    def _init_(self, db_path: Path, config: AriaConfig): ...
    async def connect(self) -> None: ...                # apre conn, applica PRAGMA
    async def close(self) -> None: ...
    async def insert(self, entry: EpisodicEntry) -> None: ...
    async def insert_many(self, entries: Sequence[EpisodicEntry]) -> None: ...
    async def get(self, id: UUID) -> EpisodicEntry | None: ...
    async def list_by_session(self, session_id: UUID, limit: int = 50, offset: int = 0) -> list[EpisodicEntry]: ...
    async def list_by_time_range(self, since: datetime, until: datetime, limit: int = 500) -> list[EpisodicEntry]: ...
    async def search_text(self, query: str, top_k: int = 10) -> list[EpisodicEntry]: ...   # FTS5 on episodic (separato da semantic)
    async def tombstone(self, id: UUID, reason: str, actor_user_id: str | None = None) -> bool: ...
    async def vacuum_wal(self) -> None: ...             # PRAGMA wal_checkpoint(TRUNCATE)
    async def stats(self) -> MemoryStats: ...
```

PRAGMA obbligatori all'`connect()`:
```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA wal_autocheckpoint=1000;
PRAGMA busy_timeout=5000;
```

Check version fail-fast:
```python
cursor = await conn.execute("SELECT sqlite_version()")
(version,) = await cursor.fetchone()
if version_tuple(version) < (3, 51, 3):
    raise MemoryError(f"SQLite {version} < 3.51.3 required (blueprint §6.1.1)")
```

Regola P6 Verbatim: **NESSUNA `UPDATE` su colonne `content`, `content_hash`, `actor`, `role`, `session_id`, `ts`**. Hard delete vietato eccetto via `tombstone()` che scrive in `episodic_tombstones` (aggiungere tabella se non presente nello schema):

```sql
CREATE TABLE IF NOT EXISTS episodic_tombstones (
    episodic_id TEXT PRIMARY KEY REFERENCES episodic(id),
    tombstoned_at INTEGER NOT NULL,
    reason TEXT NOT NULL,
    actor_user_id TEXT
);
```

`list_by_*` e `search_text` filtrano implicitamente via `LEFT JOIN episodic_tombstones WHERE t.episodic_id IS NULL`.

**Acceptance**:
- Test insert/get/list/search FTS5.
- Test tombstone: entry non piu restituito ma fisicamente presente.
- Test PRAGMA: `journal_mode=wal` verificato via `PRAGMA journal_mode`.
- Benchmark: 1000 entry insert + 200 query su FTS5, p95 < 250ms su dev laptop (documentare ambiente test).

### W1.1.J — Memory: Actor tagging helper

**File**: `src/aria/memory/actor_tagging.py`.

Helpers stateless:

```python
def derive_actor_from_role(role: str, is_tool_result: bool = False) -> Actor: ...
# user -> USER_INPUT; assistant -> AGENT_INFERENCE (o USER_INPUT se echo); tool -> TOOL_OUTPUT; system -> SYSTEM_EVENT

def actor_trust_score(actor: Actor) -> float: ...
# USER_INPUT=1.0, TOOL_OUTPUT=0.9, AGENT_INFERENCE=0.6, SYSTEM_EVENT=0.5

def actor_aggregate(actors: list[Actor]) -> Actor: ...
# downgrade rule: mix con AGENT_INFERENCE -> AGENT_INFERENCE; mix user+tool -> TOOL_OUTPUT
```

**Acceptance**: test matrice tutti i combinatori.

### W1.1.K — Memory: Tier 1 FTS5 + CLM base

**File**: `src/aria/memory/clm.py`.

**Responsabilita**: Context Lifecycle Manager. In Sprint 1.1 implementiamo **solo** distillazione extractive **senza LLM call** (mock deterministico); Sprint 1.3 potra plug-in LLM distiller.

**Strategia extractive baseline**:
1. Input: `session_id` o range temporale.
2. Recupera tutte le `EpisodicEntry` (in ordine temporale).
3. Estrai candidate chunks tramite regole:
   - `user_input` con verbo-chiave (ricorda, preferisco, voglio, deciso) → kind `preference` | `decision`.
   - `user_input` con pattern `<entita> <relazione> <valore>` → kind `fact`.
   - Pattern action item: `"devo X"`, `"ricordami di Y"` → kind `action_item`.
4. Per ogni chunk, genera `SemanticChunk` con `source_episodic_ids` puntante ai T0 origine.
5. **MAI** inferire su `tool_output` se non esplicitamente chiesto (preserva P5).
6. Aggregate actor via `actor_aggregate`; confidence = `actor_trust_score(aggregate) * keyword_match_ratio`.

**API**:

```python
class CLM:
    def _init_(self, store: EpisodicStore, semantic: SemanticStore): ...
    async def distill_session(self, session_id: UUID, force: bool = False) -> list[SemanticChunk]: ...
    async def distill_range(self, since: datetime, until: datetime) -> list[SemanticChunk]: ...
    async def promote(self, chunk_id: UUID) -> None: ...            # HITL approva inference -> confidence=1.0
    async def demote(self, chunk_id: UUID) -> None: ...              # segnala errore, confidence-=0.3
```

**File correlato**: `src/aria/memory/semantic.py` — thin wrapper su tabella FTS5 `semantic` dello schema. CRUD + search.

**Acceptance**:
- Test su dataset sintetico: sessione di 20 turn, output chunk atteso (snapshot test).
- Test P5: entry `agent_inference` NON promossa automaticamente a `fact`.
- Test idempotenza: secondo run `distill_session` non duplica chunk con stesse `source_episodic_ids`.

### W1.1.L — ARIA-Memory MCP server

**File**: `src/aria/memory/mcp_server.py`.

**Implementazione con FastMCP 3.x**. Reference https://gofastmcp.com/ (usare `@mcp.tool` decorator).

```python
from fastmcp import FastMCP

mcp = FastMCP("aria-memory")

@mcp.tool
async def remember(content: str, actor: str, role: str, session_id: str, tags: list[str] | None = None) -> dict: ...

@mcp.tool
async def recall(query: str, top_k: int = 10, kinds: list[str] | None = None, since: str | None = None, until: str | None = None) -> list[dict]: ...

@mcp.tool
async def recall_episodic(session_id: str | None = None, since: str | None = None, limit: int = 50) -> list[dict]: ...

@mcp.tool
async def distill(session_id: str) -> list[dict]: ...

@mcp.tool
async def curate(id: str, action: Literal["promote","demote","forget"]) -> dict: ...     # HITL-gated

@mcp.tool
async def forget(id: str) -> dict: ...                                                    # HITL-gated

@mcp.tool
async def stats() -> dict: ...

if _name_ == "_main_":
    mcp.run()
```

Requisiti:
- Stdio transport (default FastMCP). Configurabile via env `ARIA_MEMORY_MCP_TRANSPORT` (stdio|http).
- Tool count: 7 (budget P9 OK).
- Ogni tool logga `trace_id` e parametri non-sensibili.
- `curate(forget)` e `forget`: in Sprint 1.1 creano riga `hitl_pending` (stub) e ritornano `{"status":"pending_hitl","hitl_id":...}`. Sprint 1.2 wiraggera il flusso reale.

Registrazione in `.aria/kilocode/mcp.json`: verificare che l'entry `aria-memory` (esistente da Phase 0) punti al binario `.venv/bin/python -m aria.memory.mcp_server` (gia cosi, non cambiare).

**Acceptance**:
- `bin/aria repl` avvia KiloCode; in REPL `/tools list` mostra 7 tool `aria-memory/*`.
- Test integration: `pytest tests/integration/memory/test_mcp_e2e.py` usa `fastmcp.client` in-process per roundtrip `remember` → `recall`.

### W1.1.M — Tooling: migration runner

**File**: `src/aria/memory/migrations.py` (nuovo) + `scripts/migrate_memory.py`.

**Perche**: lo schema puo evolvere. Servono migrazioni applicate idempotentemente all'avvio di `EpisodicStore`.

**Pattern**:
- Tabella `schema_migrations (version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL, checksum TEXT NOT NULL)`.
- Migrazioni come file `src/aria/memory/migrations/NNNN_<slug>.sql`.
- Check checksum per prevenire drift (se file modificato dopo applicazione → warn ma non blocca).

**Acceptance**:
- 2 migrazioni di esempio (base + episodic_tombstones) applicate a DB vuoto, idempotenti.
- Fail test: migrazione N+1 con SQL rotto non lascia DB in stato intermedio (transazione).

## 4) Piano sprint (5 giorni lavorativi)

### D1 — Foundation utils + SOPS adapter
- W1.1.A logging + W1.1.B config refactor
- W1.1.C SOPS adapter + test integration
- End-of-day: `uv run pytest tests/unit/utils tests/integration/credentials/test_sops.py -q`

### D2 — Keyring + Rotator
- W1.1.D KeyringStore + test
- W1.1.E Rotator + circuit breaker + test
- End-of-day: roundtrip `acquire/report/acquire` su stato fittizio funziona

### D3 — CredentialManager unificato + CLI
- W1.1.F audit logger
- W1.1.G `CredentialManager` + `aria creds` CLI
- Demo: `aria creds status`, `aria creds rotate tavily`, `aria creds audit --tail 20`

### D4 — Memory schema + Tier 0
- W1.1.H schema.py
- W1.1.M migration runner
- W1.1.I episodic store + FTS5 (su tabella episodic solo, non semantic)
- Benchmark p95 recall
- End-of-day: insert 1k entry + query in p95 < 250ms

### D5 — CLM base + MCP server + review
- W1.1.J actor tagging
- W1.1.K CLM extractive + semantic store
- W1.1.L MCP server aria-memory (7 tool)
- Quality gates completi; evidence pack; appendix §18.G append di Implementation Log draft

## 5) Exit criteria Sprint 1.1

- [ ] `CredentialManager.acquire("tavily")` ritorna chiave reale da `api-keys.enc.yaml` + stato aggiornato in `providers_state.enc.yaml`
- [ ] Circuit breaker transita `closed→open→half_open→closed` in test deterministico
- [ ] `EpisodicStore` accetta 10k entry, FTS5 funzionante
- [ ] MCP server `aria-memory` registrato e invocabile da `aria repl` (test manuale: `/tools aria-memory/stats`)
- [ ] Benchmark p95 recall < 250ms (evidence in `tests/benchmarks/memory_recall_p95.txt`)
- [ ] Coverage: credentials ≥ 85%, memory ≥ 80%
- [ ] Zero secret in log (verifica manuale + test automatico `test_no_secret_leak.py`)

## 6) Deliverable checklist (Definition of Done)

- [ ] `src/aria/utils/logging.py`, `src/aria/utils/metrics.py` (stub)
- [ ] `src/aria/config.py` (esteso)
- [ ] `src/aria/credentials/{sops,keyring_store,rotator,audit,manager,_main_}.py`
- [ ] `src/aria/memory/{schema,episodic,actor_tagging,semantic,clm,mcp_server,migrations}.py`
- [ ] `src/aria/memory/migrations/0001_init.sql`, `0002_tombstones.sql`
- [ ] `tests/unit/{utils,credentials,memory}/` coverage target
- [ ] `tests/integration/{credentials,memory}/` coverage target
- [ ] `tests/benchmarks/memory_recall_p95.py` eseguito + output committato
- [ ] `docs/implementation/phase-1/sprint-01-evidence.md` (output comandi gate, screenshot REPL)
- [ ] ADR-0004 redatto come `Proposed` in `docs/foundation/decisions/ADR-0004-associative-memory-persistence.md` (decisione finale rimandata a Fase 2 ma framework posto)
- [ ] Implementation Log draft entry in blueprint §18.G (merge post-chiusura)

## 7) Quality gates e verifiche

```bash
# Static
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/aria/credentials src/aria/memory src/aria/utils

# Tests
uv run pytest tests/unit tests/integration -q --cov=aria.credentials --cov=aria.memory --cov=aria.utils --cov-report=term-missing

# Benchmarks
uv run python -m tests.benchmarks.memory_recall_p95 --entries 1000 --queries 200 --fail-if-p95-above-ms 250

# MCP smoke
./bin/aria repl  # in REPL: /tools list, /tools aria-memory/stats, Ctrl-D
```

Evidenze obbligatorie nel PR:
- Output integrale `pytest --cov`
- Output `memory_recall_p95` con tempi
- Log `aria creds status` e `aria creds audit --tail 20`
- Screenshot REPL con `aria-memory/*` tools elencati

## 8) Risk register (Sprint 1.1)

| ID  | Rischio                                                           | Impatto | Mitigazione                                                                       |
|-----|-------------------------------------------------------------------|---------|-----------------------------------------------------------------------------------|
| R11 | SOPS subprocess hang / zombie                                     | Alto    | Timeout 15s hard, test con binary SOPS sostituito da fake che sleeppa             |
| R12 | Race condition su `providers_state.enc.yaml`                      | Medio   | `flock` + `asyncio.Lock`; test concorrenza 2 thread                               |
| R13 | FTS5 non disponibile nel build SQLite di sistema                  | Alto    | Check in bootstrap Phase 0; questo sprint verifica `PRAGMA compile_options` contiene `ENABLE_FTS5`; fail fast |
| R14 | Performance recall p95 > 250ms su dataset reale                  | Medio   | Indici dedicati su `(session_id, ts)`; cover index su FTS5; documentare tuning    |
| R15 | Leak di chiave in log di errore                                   | Alto    | Test automatico su pattern regex `/^[A-Za-z0-9]{20,}$/` in log files              |
| R16 | Pydantic v2 breaking change vs schema blueprint (v1)              | Basso   | Blueprint usa sintassi compatibile; `Field(default_factory=...)` OK in v2         |
| R17 | MCP server stdio non parte da KiloCode                            | Alto    | Smoke test manuale al D5; tenere log `.aria/runtime/logs/mcp-aria-memory-*.log`   |
| R18 | `keyring` fallback non cifrato in assenza di Secret Service       | Alto    | Require age fallback key esplicita; errore all'init se ne manca                   |

## 9) ADR collegati

- **ADR-0002** (Accepted, Phase 0): SQLite Reliability Policy — usato come vincolo (§6.1.1 blueprint).
- **ADR-0004** (Proposed in Sprint 1.1): Associative Memory Persistence Format — redigere almeno con `Status: Proposed`, registrando l'opzione "no pickle" e rimandando la scelta fra SQLite graph tables / Parquet / dedicated engine a Fase 2.

## 10) Tracciabilita blueprint -> task

| Sezione blueprint                            | Task Sprint 1.1             |
|----------------------------------------------|-----------------------------|
| §5.1 Tassonomia 5D                           | W1.1.H schema               |
| §5.2 Storage Tiers                           | W1.1.I (T0), W1.1.K (T1)    |
| §5.3 Actor-aware tagging                     | W1.1.J                      |
| §5.4 CLM                                     | W1.1.K                      |
| §5.5 Schema Pydantic                         | W1.1.H                      |
| §5.6 MCP server ARIA-Memory                  | W1.1.L                      |
| §5.7 Governance memoria                      | W1.1.I (tombstone, retention config) |
| §6.1.1 SQLite reliability                    | W1.1.I (PRAGMA, version check) |
| §13.1 SOPS+age                               | W1.1.C                      |
| §13.3 OS keyring                             | W1.1.D                      |
| §13.4 CredentialManager unified              | W1.1.G                      |
| §13.5 Circuit breaker                        | W1.1.E                      |
| §13.6 Audit logging                          | W1.1.F                      |
| §14.1 Logging                                | W1.1.A                      |

## 11) Note prescrittive per l'LLM implementatore (anti-allucinazione)

### 11.1 Non inventare API — riferimenti ufficiali

| Funzione                                 | Documentazione autoritativa                                    |
|------------------------------------------|----------------------------------------------------------------|
| FastMCP decorators                       | https://gofastmcp.com/getting-started/installation             |
| `aiosqlite` usage                        | https://aiosqlite.omnilib.dev                                  |
| `keyring` backends                       | https://pypi.org/project/keyring/                              |
| SOPS CLI flags                           | https://github.com/getsops/sops                                |
| SQLite FTS5 tokenizer                    | https://www.sqlite.org/fts5.html                               |
| Pydantic v2 `BaseModel` / `SecretStr`    | https://docs.pydantic.dev/latest/                              |
| `tenacity` retry patterns                | https://tenacity.readthedocs.io                                |

Non usare pattern di altre librerie non menzionate (es. `httpx` sync, `sqlalchemy` ORM, `peewee`, `loguru`).

### 11.2 Errori frequenti da evitare

1. **NON fare `UPDATE episodic SET content=...`** — viola P6. Se serve correggere testo: inserire nuova entry e tombstonare la precedente.
2. **NON** promuovere `agent_inference` a `fact` senza conferma esplicita (user o tool_output). Violazione P5.
3. **NON** registrare `KeyInfo.key` (SecretStr) in audit log. Solo `key_id`.
4. **NON** chiamare `subprocess.run` senza `timeout=` e `check=True`.
5. **NON** importare da `lancedb`, `faster-whisper`, `pytesseract` in moduli sprint 1.1 — stanno in `pyproject.toml [ml]` optional, non nel core.
6. **NON** svuotare WAL con `rm -rf .aria/runtime/memory/` per risolvere errori: usare `PRAGMA wal_checkpoint(TRUNCATE)`.
7. **NON** fare `try/except` vuoti attorno a subprocess `sops` — ogni codice di errore SOPS ha significato specifico (exit code 128 = decryption failure, 129 = no key).

### 11.3 Interazione cross-modulo

- `CredentialManager` NON deve importare `aria.memory` o viceversa (solo `aria.config` e `aria.utils`).
- `EpisodicStore` NON deve accedere a filesystem fuori `ARIA_RUNTIME/memory/`.
- MCP server NON deve mai loggare su stdout (e sul canale JSON-RPC); logger punta sempre a file.

### 11.4 Sicurezza

- Ogni nuova chiave env introdotta → aggiungere a `.env.example` con commento, MAI valore reale.
- File `.enc.yaml` DEVONO essere in regexp `creation_rules` di `.sops.yaml`; verificare con `sops --verify` in test post-encrypt.
- `CredentialManager.acquire` ritorna `SecretStr`; call-site deve invocare `.get_secret_value()` solo **nel momento** dell'HTTP call, non anticipare.

### 11.5 Non-requisiti espliciti

Queste cose **NON** vanno fatte in Sprint 1.1 (saranno altri sprint):
- Integrazione con Telegram (Sprint 1.2)
- HITL resolution reale (Sprint 1.2 e 1.4)
- LLM distiller per CLM (Sprint 1.3)
- LanceDB embedding (Sprint 2.x)
- OAuth Google flow (Sprint 1.4)
- Scheduler daemon (Sprint 1.2)

Se trovi codice in produzione che sembra richiedere uno di questi, **non implementare**: aggiungi FIXME con riferimento a sprint/fase.

---

**Fine Sprint 1.1.** Exit criteria verdi → procedere con `sprint-02.md`.
