---
document: ARIA Phase 1 — Sprint 1.2 Implementation Plan
version: 1.0.0
status: draft
date_created: 2026-04-20
last_review: 2026-04-20
owner: fulvio
phase: 1
sprint: "1.2"
canonical_blueprint: docs/foundation/aria_foundation_blueprint.md
blueprint_sections: ["§6", "§7", "§14.2", "§14.3"]
phase_overview: docs/plans/phase-1/README.md
depends_on: docs/plans/phase-1/sprint-01.md
---

# Sprint 1.2 — Scheduler & Gateway Telegram

## 1) Obiettivo, scope, vincoli

### 1.1 Obiettivo

Dare ad ARIA **autonomia temporale** (scheduler con trigger cron/oneshot/event) e **presenza su Telegram** (gateway multimodale con whitelist + sessioni persistite). Rendere funzionante il flusso HITL end-to-end: uno scheduler crea un `hitl_pending`, il gateway Telegram pubblica la domanda all'utente, la risposta torna nel DB e sblocca il task.

### 1.2 In scope

- Modulo `src/aria/scheduler/` completo: `store.py` (tasks/runs/dlq), `triggers.py` (cron/oneshot/event/webhook/manual), `budget_gate.py`, `policy_gate.py`, `hitl.py`, `notify.py` (sd_notify watchdog), `reaper.py`, `daemon.py` (entrypoint systemd).
- Modulo `src/aria/gateway/` completo: `daemon.py` (entrypoint), `telegram_adapter.py` (PTB 22.x async), `session_manager.py`, `auth.py` (whitelist + HMAC webhook), `multimodal.py` (OCR + Whisper stub, attivazione STT via flag), `hitl_responder.py`.
- Systemd units `aria-scheduler.service`, `aria-gateway.service` installate e operative su `systemd --user`.
- Endpoint Prometheus-ready `127.0.0.1:9090/metrics` esposto dal gateway (o dallo scheduler; vedi §3).
- Integrazione HITL reale: scheduler policy=`ask` → `hitl_pending` → Telegram inline keyboard → risposta → scheduler resume.
- CLI `aria schedule {list,add,remove,run,replay,status}`.

### 1.3 Out of scope

- Sub-agenti operativi (`search-agent`, `workspace-agent`): Sprint 1.3/1.4.
- Classificazione intent in conductor: Sprint 1.3.
- Canali diversi da Telegram + CLI: Fase 2.
- Dashboard Grafana: Fase 2.
- Transcription voice reale su modello esterno (OpenAI Whisper API): solo `faster-whisper` locale come default in questo sprint.

### 1.4 Vincoli inderogabili

- **P1** systemd user service, nessun root; `ReadWritePaths` limitato a `%h/coding/aria/.aria`.
- **P7** `hitl_pending` e gate unico per azioni destructive/costose; `policy=ask` default su tutte categorie `write/send/delete`.
- **P9** gateway expose tool count = 0 (non esegue tool direttamente; spawna child session Conductor).
- Scheduler MUST essere idempotente rispetto a crash: `task_runs` iniziati e non finiti entro `timeout` → marcati `outcome='timeout'` dal reaper al boot.
- **ADR-0005 (da creare in questo sprint)**: strategia concurrency; default decision: lease-based (tasks row ha `lease_owner`, `lease_expires_at`; reaper rilascia lease scaduti).

## 2) Pre-requisiti

- Sprint 1.1 chiuso: `CredentialManager`, `EpisodicStore`, logger, config.
- Token Telegram bot disponibile in `.aria/credentials/secrets/api-keys.enc.yaml` sotto chiave `telegram.bot_token`. Se non presente: `aria creds put telegram.bot_token --prompt` (stub CLI da aggiungere in questo sprint).
- `ARIA_TELEGRAM_WHITELIST` valorizzato in `.env` (CSV di user ID Telegram).
- `systemd --user` funzionante: `systemctl --user daemon-reload` senza errori (verifica con `loginctl show-user $USER | grep Linger` e abilitare se non gia).

## 3) Work Breakdown Structure (WBS)

### W1.2.A — Scheduler store (SQLite)

**File**: `src/aria/scheduler/store.py`.

Schema gia in `docs/foundation/schemas/sqlite_full.sql` (blueprint §6.1): `tasks`, `task_runs`, `dlq`, `hitl_pending`. Verificare e **aggiungere colonne lease** (decisione ADR-0005):

```sql
ALTER TABLE tasks ADD COLUMN lease_owner TEXT;          -- NULL = unleased
ALTER TABLE tasks ADD COLUMN lease_expires_at INTEGER;  -- epoch ms
CREATE INDEX idx_tasks_lease ON tasks(lease_owner, lease_expires_at);
```

**API**:

```python
class TaskStore:
    async def connect(self) -> None: ...
    async def create_task(self, task: Task) -> str: ...
    async def update_task(self, task_id: str, **fields) -> None: ...
    async def get_task(self, task_id: str) -> Task | None: ...
    async def list_tasks(self, status: list[str] | None = None, category: str | None = None) -> list[Task]: ...
    async def acquire_due(self, worker_id: str, lease_ttl_seconds: int = 300, limit: int = 10) -> list[Task]: ...
    async def release_lease(self, task_id: str, worker_id: str) -> None: ...
    async def record_run(self, run: TaskRun) -> str: ...
    async def update_run(self, run_id: str, **fields) -> None: ...
    async def move_to_dlq(self, task_id: str, reason: str, last_run_id: str | None) -> None: ...
    async def list_dlq(self) -> list[DlqEntry]: ...
    async def reap_stale_leases(self, now_ms: int) -> int: ...                # returns count reclaimed
    async def create_hitl(self, pending: HitlPending) -> str: ...
    async def resolve_hitl(self, hitl_id: str, response: str) -> HitlPending: ...
    async def expire_hitl(self, now_ms: int) -> list[HitlPending]: ...        # for timed-out
```

Modelli Pydantic in `src/aria/scheduler/schema.py`:

```python
class Task(BaseModel):
    id: str                              # UUID
    name: str
    category: Literal["search","workspace","memory","custom","system"]
    trigger_type: Literal["cron","event","webhook","oneshot","manual"]
    trigger_config: dict                 # JSON (stored as TEXT)
    schedule_cron: str | None = None
    timezone: str = "Europe/Rome"
    next_run_at: int | None = None
    status: Literal["active","paused","dlq","completed","failed"] = "active"
    policy: Literal["allow","ask","deny"] = "allow"
    budget_tokens: int | None = None
    budget_cost_eur: float | None = None
    max_retries: int = 3
    retry_count: int = 0
    last_error: str | None = None
    owner_user_id: str | None = None
    payload: dict                        # JSON — spec del task (prompt, sub_agent, etc.)
    lease_owner: str | None = None
    lease_expires_at: int | None = None
    created_at: int
    updated_at: int
```

**Regola lease** (ADR-0005 decisione):
- `acquire_due` usa transazione SQLite con `UPDATE tasks SET lease_owner=?, lease_expires_at=? WHERE id IN (SELECT id FROM tasks WHERE ... AND (lease_owner IS NULL OR lease_expires_at < ?) ORDER BY next_run_at LIMIT ?)`.
- `worker_id` = `f"scheduler-{os.getpid()}-{uuid4().hex[:8]}"`.
- Lease TTL default 5 min, refresh-to-heartbeat ogni 60s durante esecuzione.
- Reaper scatta ogni 30s: `lease_expires_at < now()` + `status=active` → reset `lease_owner=NULL`.

**Acceptance**:
- Test: 2 worker concorrenti invocano `acquire_due` contemporaneamente → solo uno vince il lease.
- Test reaper: lease scaduto → task riacquisibile.

### W1.2.B — Trigger evaluator (cron, oneshot, event, webhook, manual)

**File**: `src/aria/scheduler/triggers.py`.

**API**:

```python
class Trigger(Protocol):
    def next_fire(self, now: datetime, task: Task) -> datetime | None: ...

class CronTrigger:
    def __init__(self, expr: str, tz: str): ...   # validate via croniter
    def next_fire(self, now: datetime, task: Task) -> datetime: ...

class OneshotTrigger: ...
class EventTrigger: ...        # next_fire ritorna None (fires on-event bus)
class WebhookTrigger: ...      # idem
class ManualTrigger: ...        # next_fire ritorna None; fires only via CLI
```

Event bus (in-process, in Sprint 1.2 minimal):

```python
class EventBus:
    def __init__(self): ...
    async def publish(self, event: str, payload: dict) -> None: ...
    def subscribe(self, event: str, callback: Callable[[dict], Awaitable[None]]) -> None: ...
```

Eventi blueprint §6.2: `memory.semantic_threshold`, `task.dlq.new`, `credential.rotation_needed`, `gateway.user_message`.

**Acceptance**:
- Cron `0 8 * * *` da `now=2026-05-01T07:00Z` → `next_fire` = `2026-05-01T06:00Z` (TZ Europe/Rome = UTC+2 DST; attenzione). Test con TZ fissato.
- Webhook trigger: gestione HMAC validata in `auth.py` (vedi W1.2.I).

### W1.2.C — Budget gate

**File**: `src/aria/scheduler/budget_gate.py`.

**Responsabilita**: stimare/contabilizzare token e costo per task run; abortire se oltre soglia.

**API**:

```python
class BudgetGate:
    def __init__(self, store: TaskStore, config: AriaConfig): ...
    async def pre_check(self, task: Task) -> BudgetDecision: ...       # prima di iniziare run
    async def tick(self, run_id: str, tokens_consumed: int, cost_eur: float) -> BudgetDecision: ...   # durante
    async def post_run(self, run_id: str, final_tokens: int, final_cost: float) -> None: ...

class BudgetDecision(BaseModel):
    allowed: bool
    reason: str | None = None
    remaining_tokens: int | None = None
    remaining_cost_eur: float | None = None
```

Aggregato per-categoria giornaliero (blueprint §6.3): config dichiarativa in `.aria/runtime/scheduler/budgets.yaml`:

```yaml
daily_budgets:
  search:   { tokens: 500000, cost_eur: 2.00 }
  workspace:{ tokens: 100000, cost_eur: 0.50 }
  memory:   { tokens: 50000,  cost_eur: 0.10 }
```

Violazione:
- Per-run: abort graceful (cancella chiamate in-flight, marca `outcome=blocked_budget`).
- Per-categoria giornaliera: `status=paused` su TUTTI i task di categoria per 24h, notifica `system_event`.

**Acceptance**:
- Test `pre_check` su task con budget=100 token, stima=150 → deny.
- Test `tick` su corsa oltre soglia metà-run → abort.

### W1.2.D — Policy gate + Quiet Hours

**File**: `src/aria/scheduler/policy_gate.py`.

**API**:

```python
class PolicyDecision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"            # -> HITL flow
    DENY = "deny"
    DEFERRED = "deferred"  # Quiet hours shift

class PolicyGate:
    def __init__(self, config: AriaConfig, clock: Callable[[], datetime]): ...
    def evaluate(self, task: Task, now: datetime | None = None) -> PolicyDecision: ...
```

Regole (blueprint §6.4):
1. Task `policy=allow` in quiet hours (22:00-07:00 Europe/Rome) → `ALLOW` (proattivita silenziosa consentita solo per task `read-only`; controllo su `category in {"search","memory.read"}`).
2. Task `policy=ask` in quiet hours → `DEFERRED` (scheduler reinserisce `next_run_at` a `quiet_hours_end`).
3. Task `policy=deny` → `DENY` sempre (log ma non esegue).
4. Override per task esplicito in `payload.policy_override`.

**Acceptance**:
- Matrice test (policy x quiet-hours x category).

### W1.2.E — HITL flow

**File**: `src/aria/scheduler/hitl.py`.

**Responsabilita**: creazione/resolution di `hitl_pending`, timeout expiry.

**API**:

```python
class HitlManager:
    def __init__(self, store: TaskStore, bus: EventBus, config: AriaConfig): ...
    async def ask(self, task: Task, run_id: str, question: str, options: list[str] | None = None,
                  channel: Literal["telegram","cli"] = "telegram",
                  ttl_seconds: int = 900) -> HitlPending: ...
    async def wait_for_response(self, hitl_id: str, timeout_s: int = 900) -> str | None: ...
    async def resolve(self, hitl_id: str, response: str) -> None: ...
    async def expire_stale(self) -> list[str]: ...
```

- `ask` pubblica evento `hitl.created` sul bus; gateway Telegram lo consumera per inviare inline keyboard.
- `wait_for_response` usa `asyncio.Event` mappato per `hitl_id` + timer; risoluzione via `resolve` dal gateway.
- Timeout scaduto senza risposta → `user_response=None`, return a caller che decide (abort task o defer).

### W1.2.F — Notifier sd_notify + watchdog

**File**: `src/aria/scheduler/notify.py`.

```python
class SdNotifier:
    def __init__(self, watchdog_interval_s: int = 30): ...
    async def start(self) -> None: ...         # sends READY=1
    async def ping(self) -> None: ...          # sends WATCHDOG=1
    async def stop(self, reason: str = "") -> None: ...   # sends STOPPING=1
    async def run_forever(self) -> None: ...   # background loop con ping periodico
```

Usa `sd_notify` lib. Se env `NOTIFY_SOCKET` assente → no-op (sviluppo locale).

### W1.2.G — Reaper

**File**: `src/aria/scheduler/reaper.py`.

Task di manutenzione periodico (ogni 30s):
1. Rilascia lease scaduti.
2. Sposta in DLQ task con `retry_count >= max_retries`.
3. Forza `outcome=timeout` su `task_runs` iniziati e mai chiusi (detectable via `started_at < now-timeout AND finished_at IS NULL`).
4. Esegue `PRAGMA wal_checkpoint(TRUNCATE)` su `scheduler.db` ogni 6h (quiet window).
5. Check `hitl_pending.expires_at < now` → expire.

### W1.2.H — Scheduler daemon entrypoint

**File**: `src/aria/scheduler/daemon.py` (gia stub da Phase 0; implementare contenuto).

Struttura asyncio:

```python
async def main() -> None:
    config = AriaConfig.load()
    setup_logging(config)
    store = TaskStore(config.runtime / "scheduler/scheduler.db", config)
    await store.connect()
    bus = EventBus()
    budget = BudgetGate(store, config)
    policy = PolicyGate(config, now_clock)
    hitl = HitlManager(store, bus, config)
    notifier = SdNotifier()
    reaper = Reaper(store, config)
    runner = TaskRunner(store, budget, policy, hitl, bus, config)

    await notifier.start()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(notifier.run_forever())
        tg.create_task(reaper.run_forever())
        tg.create_task(runner.run_forever())

if __name__ == "__main__":
    asyncio.run(main())
```

**TaskRunner**:
- Loop: `acquire_due(worker_id, lease_ttl=300, limit=5)` ogni 5s.
- Per ogni task: valutare `policy_gate` → `budget_gate.pre_check` → (se ask: `hitl.ask` + wait) → esegui via `exec_task(task)` → `report_run(run)`.
- `exec_task`: **in Sprint 1.2, stub** — il task `payload.sub_agent` viene semplicemente registrato e completato con `outcome='success'` se `category=system`, altrimenti `outcome='not_implemented'`. Sprint 1.3 wiraggera Conductor.

### W1.2.I — Gateway: auth + sessions

**File**: `src/aria/gateway/auth.py`, `src/aria/gateway/session_manager.py`.

Auth:
```python
class AuthGuard:
    def __init__(self, whitelist: list[str]): ...
    def is_allowed_telegram_user(self, user_id: int) -> bool: ...
    def verify_webhook_hmac(self, body: bytes, signature: str, secret: str) -> bool: ...
```

SessionManager:
- Schema `gateway_sessions` (blueprint §7.2) gia in `sqlite_full.sql`. Verificare presenza.
- API async: `get_or_create(channel, external_user_id, locale="it-IT") -> SessionRow`, `touch(session_id)`, `set_state(session_id, state_dict)`.

### W1.2.J — Gateway: Telegram adapter

**File**: `src/aria/gateway/telegram_adapter.py`.

**Implementazione PTB 22.x** (verificare docs: https://docs.python-telegram-bot.org/).

Struttura:

```python
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

class TelegramAdapter:
    def __init__(self, cm: CredentialManager, auth: AuthGuard, sessions: SessionManager, bus: EventBus, config: AriaConfig): ...
    async def build_app(self) -> Application: ...
    async def start_polling(self) -> None: ...    # run in daemon
    async def stop(self) -> None: ...
```

Handlers da registrare:
- `/start`, `/help`, `/status` — commands
- `/run <task_id>` — trigger manual scheduler task
- `/schedule list|add|remove` — delegate a scheduler CLI
- Message handler (filters.TEXT & ~filters.COMMAND): invia a Conductor via `bus.publish("gateway.user_message", {...})` (Sprint 1.3 wiraggera consumer reale; in 1.2 un **echo handler** di test)
- Photo handler: download → OCR via `multimodal.py`
- Voice handler: download → STT via `multimodal.py`
- CallbackQuery handler: risposta a `hitl_pending` (inline keyboard) → `hitl.resolve`

Hardening:
- Whitelist check FIRST, prima di qualunque download.
- Rate limit per-user: max 30 msg/min (in-memory bucket).
- Download limit: file size ≤ 20MB (Telegram limit per bot API).
- Timeout HTTP: 30s.

**HITL inline keyboard**:

```
"Approve the following action? [✅ Yes] [❌ No] [⏸ Later]"
```

Payload CallbackQuery: `hitl:<id>:yes|no|later`. Resolve via `hitl.resolve(id, response)`.

### W1.2.K — Gateway: multimodal

**File**: `src/aria/gateway/multimodal.py`.

Componenti:
- `ocr_image(path: Path) -> str` con `pytesseract` (optional dep `[ml]`). Fallback vuoto + warning se package non installato.
- `transcribe_audio(path: Path) -> str` con `faster-whisper` small model (optional dep). Lazy load del modello; cache modello in `.aria/runtime/models/`.

**ADR-0007 obbligatorio se si abilita voice**: documenta scelta `faster-whisper` vs `openai-whisper` fallback.

**Acceptance**:
- Se package non installato, path codice chiaramente degrado (non crash) e log warning.
- Test con audio fixture 5s (`tests/fixtures/audio/hello.wav`) → trascrizione contiene "hello" (case-insensitive).

### W1.2.L — Gateway daemon + metrics

**File**: `src/aria/gateway/daemon.py` (gia stub), `src/aria/utils/metrics.py`.

Struttura simile a scheduler daemon (sd_notify, asyncio.TaskGroup).

Expose Prometheus metrics su `127.0.0.1:9090/metrics` (scelto gateway perche primo ad avviarsi in topologia):
- usare `prometheus_client` (aggiungere a `pyproject.toml` Sprint 1.2: `prometheus-client>=0.20`)
- bind **obbligatoriamente** `127.0.0.1` (no `0.0.0.0`); in Phase 2 mTLS.

### W1.2.M — CLI `aria schedule`

Estendere `bin/aria` schedule subcommand → `src/aria/scheduler/cli.py` (nuovo file tipicamente typer).

Comandi:
- `aria schedule list [--status STATUS] [--category CAT]`
- `aria schedule add --name N --cron 'expr' --category CAT --payload '{json}' [--policy allow|ask|deny]`
- `aria schedule remove <id>`
- `aria schedule run <id>` (manual trigger, no wait)
- `aria schedule replay <id>` (riprende da DLQ)
- `aria schedule status [--verbose]`

### W1.2.N — Systemd units finalization

Modificare `systemd/aria-scheduler.service` e `systemd/aria-gateway.service` (esistenti da Phase 0) per:
- `Type=notify` (gia presente)
- `ExecStart=%h/coding/aria/.venv/bin/python -m aria.scheduler.daemon` / `aria.gateway.daemon`
- Verificare `ReadWritePaths=%h/coding/aria/.aria/runtime %h/coding/aria/.aria/kilocode/sessions`
- `WatchdogSec=60`, `RestartSec=5s`
- Hardening completo (blueprint §6.6)

Script install `scripts/install_systemd.sh` (esistente): aggiornare se necessario per linkare i nuovi unit. Verificare `systemd-analyze verify` senza warning `security-score`.

### W1.2.O — HITL responder bridge

**File**: `src/aria/gateway/hitl_responder.py`.

Consumer del bus event `hitl.created`:
- Legge `hitl_pending`, invia Telegram message a `owner_user_id` (o whitelist primary se null) con inline keyboard.
- CallbackQuery → `HitlManager.resolve(hitl_id, response)` → pubblica `hitl.resolved`.

Test integration: creazione `hitl_pending` mock → adapter simula messaggio → `resolve` aggiorna row.

## 4) Piano sprint (5 giorni)

### D1 — Schema store + trigger evaluator
- W1.2.A store + migrazioni `0003__lease_columns.sql`
- W1.2.B triggers (cron/oneshot/event stub)
- End-of-day: `TaskStore.acquire_due` verde in test concorrenza

### D2 — Budget/Policy/HITL + reaper
- W1.2.C budget_gate
- W1.2.D policy_gate (con quiet hours)
- W1.2.E hitl manager
- W1.2.F notifier + W1.2.G reaper
- End-of-day: scheduler daemon avvia in dev, logga heartbeat

### D3 — Gateway Telegram base
- W1.2.I auth + sessions
- W1.2.J telegram adapter (echo handler, no HITL ancora)
- Verifica su bot di test: `/start`, `/help`, messaggio testo echo
- End-of-day: `aria gateway` avvia, riceve e risponde su Telegram reale (account test)

### D4 — Multimodal + HITL responder + metrics
- W1.2.K multimodal (OCR + STT se installati)
- W1.2.O hitl responder
- W1.2.L metrics endpoint
- End-of-day: HITL end-to-end: scheduler crea pending → utente risponde su Telegram → task riprende

### D5 — Systemd install + CLI + quality gate
- W1.2.M CLI `aria schedule`
- W1.2.N install systemd + test con `systemctl --user start/stop/restart`
- Quality gates completi + evidence
- ADR-0005 accepted, ADR-0007 accepted se STT attivo

## 5) Exit criteria Sprint 1.2

- [ ] `systemctl --user start aria-scheduler.service aria-gateway.service` → running, watchdog regolare
- [ ] Telegram bot risponde su account whitelisted
- [ ] HITL: test end-to-end scripted (`tests/e2e/test_hitl_flow.py`) passa
- [ ] `aria schedule add/list/run` funzionante
- [ ] Metrics endpoint risponde 200 su `curl 127.0.0.1:9090/metrics`
- [ ] Reaper rilascia lease scaduti in test simulato
- [ ] Coverage scheduler ≥ 75%, gateway ≥ 70%
- [ ] ADR-0005 accepted

## 6) Deliverable checklist (Definition of Done)

- [ ] `src/aria/scheduler/{schema,store,triggers,budget_gate,policy_gate,hitl,notify,reaper,daemon,cli}.py`
- [ ] `src/aria/gateway/{schema,daemon,telegram_adapter,session_manager,auth,multimodal,hitl_responder,metrics_server}.py`
- [ ] `src/aria/memory/migrations/0003__lease_columns.sql`
- [ ] `systemd/aria-scheduler.service`, `systemd/aria-gateway.service` finalizzati
- [ ] `scripts/install_systemd.sh` funzionante (idempotente)
- [ ] `tests/unit/{scheduler,gateway}/`
- [ ] `tests/integration/scheduler/test_end_to_end_hitl.py`
- [ ] `tests/e2e/test_hitl_flow.py` (con PTBTestApp, senza chiamate reali Telegram)
- [ ] `docs/operations/runbook.md` — aggiornato con procedure start/stop/restart/restore
- [ ] ADR-0005 (Scheduler Concurrency Model) Accepted
- [ ] Implementation Log entry

## 7) Quality gates

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/aria/scheduler src/aria/gateway

uv run pytest tests/unit tests/integration -q --cov=aria.scheduler --cov=aria.gateway --cov-report=term-missing

# Systemd
systemd-analyze verify systemd/aria-scheduler.service systemd/aria-gateway.service
systemctl --user daemon-reload
systemctl --user start aria-scheduler.service aria-gateway.service
systemctl --user status aria-scheduler.service aria-gateway.service   # deve essere active (running)
sleep 90 && systemctl --user is-active aria-scheduler.service         # watchdog OK

# Metrics
curl -s http://127.0.0.1:9090/metrics | grep aria_tasks_total

# Telegram smoke (con account test)
./bin/aria gateway --test-ping <your_test_user_id>  # richiede `--test-ping` subcommand hooking
```

## 8) Risk register

| ID  | Rischio                                                         | Impatto | Mitigazione                                                                        |
|-----|-----------------------------------------------------------------|---------|------------------------------------------------------------------------------------|
| R21 | PTB 22.x breaking change vs esempi blueprint                    | Medio   | Testare con docs ufficiali; esempi handler in fixture `tests/fixtures/ptb_examples/` |
| R22 | Race condition su lease con 2+ scheduler instance               | Alto    | Transazione esplicita in `acquire_due`; test 2 worker                              |
| R23 | Systemd `ReadWritePaths` troppo restrittivo → WAL write fail   | Alto    | Test su `/tmp/aria-dev-runtime` prima, poi path reale; monitor `journalctl`        |
| R24 | Telegram webhook vs polling — scelta in MVP                    | Basso   | MVP = polling (zero inbound, funziona dietro NAT)                                  |
| R25 | `faster-whisper` pesante a startup → watchdog timeout          | Medio   | Lazy load modello; inizio load out-of-watchdog-critical-path                       |
| R26 | Prometheus endpoint esposto fuori `127.0.0.1`                  | Alto    | Hardcode bind + test `curl` da interfaccia secondaria → connection refused         |
| R27 | HITL timeout mal gestito → task orfani                         | Medio   | Reaper processa `hitl_pending.expires_at`; caller `wait_for_response` fault-tolerant |
| R28 | Quiet hours DST (passaggio ora legale)                         | Basso   | Usare `zoneinfo` + `croniter` tz-aware; test cross-DST                              |
| R29 | Budget gate token-count errato con model non-Claude            | Medio   | Implementare estimator conservativo (tiktoken non richiesto in Sprint 1.2; TODO)   |

## 9) ADR collegati

- **ADR-0005 — Scheduler Concurrency Model** (nuovo, Accepted in Sprint 1.2): lease-based con `lease_owner`/`lease_expires_at`, reaper rilascia scaduti, single-writer per task in-flight.
- **ADR-0007 — STT Stack Dual** (opzionale, solo se voice abilitato): default `faster-whisper`, fallback `openai-whisper`, mai Whisper API cloud senza flag esplicito.

## 10) Tracciabilita blueprint -> task

| Sezione blueprint            | Task Sprint 1.2            |
|------------------------------|----------------------------|
| §6.1 Schema scheduler        | W1.2.A                     |
| §6.1.1 SQLite reliability    | W1.2.G reaper (checkpoint) |
| §6.2 Tipi trigger            | W1.2.B                     |
| §6.3 Budget gate             | W1.2.C                     |
| §6.4 Policy gate + quiet hrs | W1.2.D                     |
| §6.5 DLQ + retry             | W1.2.A + W1.2.G            |
| §6.6 Systemd user + sd_notify| W1.2.F + W1.2.N            |
| §6.7 Quiet hours/rate/circuit | W1.2.D + W1.2.J (rate lim) |
| §7.1-7.3 Gateway arch        | W1.2.I + W1.2.J            |
| §7.4 Multimodal              | W1.2.K                     |
| §14.2 Metriche Prometheus    | W1.2.L                     |
| §14.3 Policy sicurezza       | W1.2.I (auth + HMAC)       |

## 11) Note prescrittive per l'LLM implementatore (anti-allucinazione)

### 11.1 PTB 22.x specifico

- USA la classe `telegram.ext.Application` (NON `Updater.dispatcher`, rimosso in v20+).
- Build: `Application.builder().token(t).build()`.
- Start: `await application.initialize()`, `await application.updater.start_polling()`.
- Handlers: `application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler))`.
- Inline keyboard: `InlineKeyboardMarkup([[InlineKeyboardButton("Yes", callback_data="hitl:<id>:yes")]])`.
- CallbackQueryHandler: mai usare `callback_query.answer()` dopo 30s (timeout API).

### 11.2 Errori comuni

1. **NON** mischiare sync e async in PTB v22: tutti gli handler sono `async def`. Se serve chiamare codice sync: `asyncio.to_thread`.
2. **NON** usare `Updater.idle()` (deprecato). Usare `asyncio.Event` su `SIGTERM`/`SIGINT`.
3. **NON** mettere segreti in `CallbackQuery.data` (64 byte max + visibile a client). Solo ID opachi.
4. **NON** emettere `publish("gateway.user_message", ...)` con payload > 8KB: per messaggi lunghi salvare episodic prima, pubblicare solo `episodic_id`.
5. **NON** scrivere `WatchdogSec=60` e `ping` ogni 30s ma bloccare su I/O > 60s — la ping loop deve essere separata e non-bloccante.
6. **NON** creare due handler polling per lo stesso bot (systemd gia uno): se avvii `aria gateway --dev` disattiva unit systemd prima.

### 11.3 Non-requisiti

- NON implementare Slack/WhatsApp/Discord (Fase 2).
- NON implementare OCR AWS/GCP (solo pytesseract locale).
- NON creare dashboard Grafana (Fase 2).
- NON fare tool direct calling dal gateway: **il gateway publica eventi e basta**, Conductor orchestra.

### 11.4 Sicurezza specifica gateway

- Whitelist enforcing PRIMA di `await update.message.reply_text`: log attempt e scarta silenzioso.
- Download file: sempre `tempfile.NamedTemporaryFile(dir=tmp_dir, delete=True)` con cleanup; `tmp_dir = ARIA_RUNTIME/tmp/gateway/`.
- HMAC webhook: `hmac.compare_digest` (timing-safe), MAI `==` raw.
- Metrics endpoint: se trovi `bind_host = "0.0.0.0"` nel codice → blocco hard con assertion.

### 11.5 Testing policy gateway

- Usare `python-telegram-bot[test]` extras (se disponibili) o mock manuale di `Bot.send_message`.
- Per e2e, `pytest-asyncio` + custom `MockTelegramBot` in `tests/fixtures/telegram/`.
- Nessuna chiamata HTTP reale a `api.telegram.org` in test.

---

**Fine Sprint 1.2.** Exit criteria verdi → procedere con `sprint-03.md`.
