---
document: ARIA Operations Runbook
version: 1.0.0
status: draft
date_created: 2026-04-20
last_review: 2026-04-21
owner: fulvio
scope: phase-1
---

# ARIA Operations Runbook

Operazioni day-to-day per i servizi ARIA su systemd user mode.

**Servizi:** `aria-scheduler.service`, `aria-gateway.service`, `aria-memory.service`  
**Runtime:** `.aria/runtime/`  
**Credentials:** `.aria/credentials/` (SOPS+age encrypted)  
**Logs:** `journalctl --user -u <service>`

---

## 1. Avvio, Stop, Restart

### 1.0 Isolamento Kilo (obbligatorio)

`./bin/aria` avvia Kilo in isolamento totale dal profilo globale utente.

Env runtime effettivo:

- `HOME=~/coding/aria/.aria/kilo-home`
- `XDG_CONFIG_HOME=~/coding/aria/.aria/kilo-home/.config`
- `XDG_DATA_HOME=~/coding/aria/.aria/kilo-home/.local/share`
- `XDG_STATE_HOME=~/coding/aria/.aria/kilo-home/.local/state`
- `KILO_CONFIG_DIR=~/coding/aria/.aria/kilocode`
- `KILO_DISABLE_EXTERNAL_SKILLS=true`

Verifica rapida:

```bash
./bin/aria run "ping" --print-logs --log-level DEBUG 2>&1 | \
  grep -E "service=config path="
```

Output atteso: solo path sotto `.aria/kilo-home` e `.aria/kilocode`.
Nessun path sotto `~/.config/kilo`, `~/.kilocode`, `~/.kilo`, `~/.opencode`.

### 1.1 Prerequisites

```bash
# Verificare linger (obbligatorio per systemd --user)
loginctl show-user $USER | grep Linger
# Output atteso: Linger=yes

# Se Linger=no:
loginctl enable-linger $USER
```

### 1.2 Installare / Aggiornare unit

```bash
# Eseguire dalla root del repo:
cd ~/coding/aria

# Installa (idempotente — copia solo se cambia):
./scripts/install_systemd.sh install

# Ricarica systemd dopo modifiche:
./scripts/install_systemd.sh reload   # equivalente a systemctl --user daemon-reload
```

### 1.3 Start / Stop / Status

```bash
# Start first-start path (core only)
./scripts/install_systemd.sh start

# Start memory opzionale (manuale)
systemctl --user start aria-memory.service

# Stop principali (+ memory opzionale)
systemctl --user stop aria-scheduler.service aria-gateway.service
systemctl --user stop aria-memory.service

# Status singolo
systemctl --user status aria-scheduler.service --no-pager
systemctl --user status aria-gateway.service --no-pager
systemctl --user status aria-memory.service --no-pager

# Status con journal
./scripts/install_systemd.sh status
```

### 1.4 Restart (dopo modifica codice / config)

```bash
# Restart singolo
systemctl --user restart aria-scheduler.service
systemctl --user restart aria-gateway.service

# Restart entrambi (ordine: gateway prima, poi scheduler)
systemctl --user restart aria-gateway.service aria-scheduler.service
```

### 1.5 Abilitare avvio automatico

```bash
# Enable first-start path (core only)
./scripts/install_systemd.sh enable
# Equivalente a (core):
# systemctl --user enable aria-scheduler.service
# systemctl --user enable aria-gateway.service

# Memory opzionale (manuale)
# systemctl --user enable aria-memory.service
```

### 1.6 watchdog verification

```bash
# Verificare che il watchdog scatti (90s senza ping → restart)
sleep 95 && systemctl --user is-active aria-scheduler.service
# Output atteso: active (non failed)
```

---

## 2. Log e Monitoraggio

### 2.1 Journal (logs systemd)

```bash
# Logs scheduler (tail -f live)
journalctl --user -u aria-scheduler.service -f

# Logs gateway
journalctl --user -u aria-gateway.service -f

# Logs ultimi errori
journalctl --user -u aria-scheduler.service -p err -f

# Log file specifico (con timestamp)
journalctl --user -u aria-gateway.service --no-pager -o short-iso
```

### 2.2 Metrics Prometheus

```bash
# Verificare endpoint metrics (deve rispondere 200)
curl -s http://127.0.0.1:9090/metrics | grep "^aria_"

# Metrics chiave
curl -s http://127.0.0.1:9090/metrics | grep aria_hitl_pending
curl -s http://127.0.0.1:9090/metrics | grep aria_tasks_total
```

### 2.3 Integrità DB

```bash
# Verificare che scheduler.db sia raggiungibile
ls -la ~/coding/aria/.aria/runtime/scheduler/scheduler.db

# Check WAL size (alert se > 256MB)
du -h ~/coding/aria/.aria/runtime/scheduler/scheduler.db-wal

# Check sessioni gateway
ls -la ~/coding/aria/.aria/runtime/gateway/sessions.db
```

---

## 3. Credential Management

### 3.1 Bot Token Telegram

Il token del bot Telegram è salvato in KeyringStore (o fallback age-encrypted):

```bash
# Verificare che il token sia caricato (non stampa il valore)
uv run python -c "
from aria.credentials import CredentialManager
cm = CredentialManager()
t = cm.get_oauth('telegram', 'bot')
print(f'Telegram bot token: {\"configured\" if t else \"MISSING\"}')"

# Aggiornare token
uv run python -m aria.credentials put telegram.bot_token --value "NUOVO_TOKEN"
```

### 3.2 API Keys (SOPS)

```bash
# Decrypt e visualizzare (solo dev, mai in production)
cd ~/coding/aria
age --decrypt -i ~/.config/sops/age/keys.txt -d .aria/credentials/secrets/api-keys.enc.yaml

# Modificare con editor SOPS
sops .aria/credentials/secrets/api-keys.enc.yaml
```

### 3.3 Rotazione API Key

```bash
# Status credenziali
uv run python -m aria.credentials status

# Rotate key provider
uv run python -m aria.credentials rotate <provider>
```

---

## 4. CLI Scheduler

### 4.1 Liste task

```bash
# Lista tutti i task attivi
uv run python -m aria.scheduler.cli list

# Lista per categoria
uv run python -m aria.scheduler.cli list --category search

# Lista per stato
uv run python -m aria.scheduler.cli list --status active
```

### 4.2 Aggiungere task

```bash
# Task cron giornaliero (8:00 Rome)
uv run python -m aria.scheduler.cli add \
  --name "Morning briefing" \
  --cron "0 8 * * *" \
  --category search \
  --payload '{"prompt": "Fammi un briefing delle news di oggi"}'

# Task oneshot
uv run python -m aria.scheduler.cli add \
  --name "One-time task" \
  --type oneshot \
  --payload '{"prompt": "Fai questo"}'

# Task con policy ASK (HITL required)
uv run python -m aria.scheduler.cli add \
  --name "Send email" \
  --type manual \
  --policy ask \
  --payload '{"sub_agent": "workspace"}'
```

### 4.3 Rimuovere / Rieseguire

```bash
# Rimuovere task
uv run python -m aria.scheduler.cli remove <task_id>

# Rieseguire manualmente
uv run python -m aria.scheduler.cli run <task_id>

# Replay da DLQ
uv run python -m aria.scheduler.cli replay <task_id>
```

### 4.4 Status

```bash
uv run python -m aria.scheduler.cli status --verbose
```

---

## 5. HITL (Human-In-The-Loop)

### 5.1 Task in attesa

```bash
# Verificare task in attesa HITL
uv run python -c "
import asyncio
from aria.scheduler.store import TaskStore
from aria.config import get_config

async def check():
    config = get_config()
    store = TaskStore(config.paths.runtime / 'scheduler/scheduler.db')
    await store.connect()
    cursor = await store._conn.execute('SELECT id, task_id, question, created_at FROM hitl_pending WHERE resolved_at IS NULL')
    print(await cursor.fetchall())

asyncio.run(check())
"
```

### 5.2 Risposta manuale (fallback CLI)

```bash
# Risolvere HITL manualmente (se Telegram non disponibile)
uv run python -c "
import asyncio
from aria.scheduler.store import TaskStore
from aria.scheduler.hitl import HitlManager
from aria.scheduler.triggers import EventBus
from aria.config import get_config

async def resolve(hitl_id, response='yes'):
    config = get_config()
    store = TaskStore(config.paths.runtime / 'scheduler/scheduler.db')
    await store.connect()
    bus = EventBus()
    hitl = HitlManager(store, bus, config)
    await hitl.resolve(hitl_id, response)
    print(f'HITL {hitl_id} resolved: {response}')

# asyncio.run(resolve('hitl_id_from_db', 'yes'))
"
```

---

## 6. Backup e Restore

### 6.1 Backup manuale

```bash
# Backup runtime (SQLite + credential metadata)
cd ~/coding/aria
./scripts/backup.sh

# Backup solo scheduler
cp ~/coding/aria/.aria/runtime/scheduler/scheduler.db ~/.aria-backups/scheduler-$(date +%Y%m%d).db
```

### 6.2 Restore

```bash
# Elencare backup disponibili
ls -la ~/.aria-backups/

# Restore scheduler.db
cp ~/.aria-backups/scheduler-20260420.db ~/coding/aria/.aria/runtime/scheduler/scheduler.db
# ⚠️ Stop scheduler prima di restore: systemctl --user stop aria-scheduler.service
```

---

## 7. Troubleshooting

### 7.1 Servizio non parte

```bash
# 1. Verificare journal per errore
journalctl --user -u aria-scheduler.service -p err --no-pager -n 20

# Errori comuni:
# - "Failed to load environment files": manca .env → cp .env.example .env
# - "Failed to drop capabilities" + status=218/CAPABILITIES:
#   in user mode desktop non usare PrivateDevices=true o ProtectKernelModules=true
#   (vedi ADR-0008)
# - "No such file or directory": path sbagliato in EnvironmentFile o ReadWritePaths
```

### 7.2 Gateway non si connette a Telegram

```bash
# 1. Verificare token configurato
journalctl --user -u aria-gateway.service --no-pager | grep -i token

# 2. Testare bot API direttamente
curl -s https://api.telegram.org/bot<TOKEN>/getMe | python -m json.tool

# 3. Verificare whitelist in .env
grep ARIA_TELEGRAM_WHITELIST ~/coding/aria/.env
```

### 7.3 HITL non arriva su Telegram

```bash
# 1. Verificare che hitl_responder riceva eventi
journalctl --user -u aria-gateway.service --no-pager | grep hitl

# 2. Verificare che HITL pending sia stato creato
journalctl --user -u aria-scheduler.service --no-pager | grep hitl

# 3. Verificare che il bot sia stato avviato con polling attivo
journalctl --user -u aria-gateway.service --no-pager | grep -E "getUpdates|getMe"
```

### 7.4 Lease scaduti non rilasciati

```bash
# 1. Verificare che reaper stia girando
journalctl --user -u aria-scheduler.service --no-pager | grep reaper

# 2. Forzare rilascio lease manualmente
uv run python -c "
import asyncio
from aria.scheduler.store import TaskStore
from aria.config import get_config

async def fix():
    config = get_config()
    store = TaskStore(config.paths.runtime / 'scheduler/scheduler.db')
    await store.connect()
    count = await store.reap_stale_leases(9999999999999)  # forza tutti
    print(f'Released {count} stale leases')

asyncio.run(fix())
"
```

### 7.5 Metrics endpoint non risponde

```bash
# 1. Verificare che gateway sia attivo
systemctl --user is-active aria-gateway.service

# 2. Verificare binding 127.0.0.1 (non 0.0.0.0)
curl -v http://127.0.0.1:9090/metrics 2>&1 | head -5

# 3. Se "Connection refused": metrics server non partito
# Verificare che gateway non crashi all'avvio
journalctl --user -u aria-gateway.service --no-pager | grep metrics
```

---

## 8. Estrarre Config e Secreti

### 8.1 Config attiva

```bash
uv run python -c "
from aria.config import get_config
c = get_config()
print(f'ARIA_HOME={c.paths.home}')
print(f'ARIA_RUNTIME={c.paths.runtime}')
print(f'Telegram whitelist: {c.telegram.whitelist}')
print(f'Timezone: {c.operational.timezone}')
"
```

### 8.2 Environment variabili critiche

```bash
# Verificare .env
cat ~/coding/aria/.env
cat ~/coding/aria/.env | grep -E "ARIA_|TELEGRAM|QUIET"
```

---

## 9. Referenze

- Blueprint: `docs/foundation/aria_foundation_blueprint.md` §6.6, §7
- Sprint plan: `docs/plans/phase-1/sprint-02.md`
- Systemd units: `systemd/aria-scheduler.service`, `systemd/aria-gateway.service`, `systemd/aria-memory.service`
- ADR-0008: `docs/foundation/decisions/ADR-0008-systemd-user-capability-limits.md`
- ADR-0005: `docs/foundation/decisions/ADR-0005-scheduler-concurrency.md`
- Credential architecture: `src/aria/credentials/` (SOPS + KeyringStore)

---

**Fine runbook.**
