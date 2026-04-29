# ARIA Kilo TUI Freeze — RCA & Definitive Fix (2026-04-29)

## Symptom

Avviando una nuova sessione kilo dalla root `/home/fulvio/coding/aria/`
(via `bin/aria repl`, `bin/aria run`, o `kilocode` diretto) la TUI freeza
subito dopo il caricamento dei plugin. Lo stesso problema NON si verifica
in altre directory (`coding/`, `coding/github-discovery/`, `coding/qlora/`).
Le sessioni avviate prima del problema continuano a funzionare.

## Root cause analysis

### Direct cause: zombie session + DB bloat + heavy review prompt

1. **Zombie aria-conductor session**. Una sessione precedente (PID 206509)
   restava `Sl+` con 12 figli MCP (PIDs 206870-207019), tenendo lock sul
   database SQLite e mantenendo 8.9GB di RAM in uso.
2. **kilo.db = 3.1GB** con WAL = 431MB. La tabella `message` da sola pesa
   2.4GB. Le query di startup (workspace fromDirectory) diventano lente.
3. **Branch diff enorme**. `feature/research-academic-social-v2` aveva 31
   file modificati / 211KB diff vs `origin/main`. All'avvio kilo invoca
   `service=review buildReviewPromptBranch` per popolare la sidebar PR;
   con 211KB di diff il rendering OpenTUI si bloccava 8.5+ minuti.
4. **Snapshot dir 4.5GB** (`.aria/kilo-home/.local/share/kilo/snapshot/`).
   Ogni sessione kilo crea un git bare repo del workspace; non c'è TTL
   automatico in kilo 7.2.x.

### Underlying root cause: missing watcher/snapshot config in isolated kilo

L'ARIA launcher (`bin/aria`) crea un Kilo isolato sotto
`.aria/kilo-home/` riassegnando `HOME`/`XDG_*`. Il `kilo.jsonc` generato
dal migration step **non aveva** le ottimizzazioni che invece
`~/.kilocode/kilo.json` (config globale dell'utente) aveva da tempo:

```jsonc
{
  "snapshot": false,           // disabilita git-snapshot per sessione
  "logLevel": "WARN",
  "watcher": {
    "ignore": [".venv", "node_modules", ".git", ...]
  }
}
```

Senza queste, il file watcher di kilo scansionava tutto `.aria/` (11GB,
soprattutto `.aria/kilo-home/.local/share/kilo/` ricorsivo!), e la
modalità snapshot creava un nuovo bare-repo a ogni avvio. Loop di
crescita inevitabile.

## Definitive fix

### 1. Config: forced defaults nel kilo.jsonc isolato

`bin/aria` ora inietta nella migration Python questi default
(idempotenti, preservano valori esistenti via `setdefault`):

- `snapshot: false`
- `logLevel: "WARN"`
- `watcher.ignore` con `.aria`, `.venv`, `node_modules`, `.git`,
  `__pycache__`, `*.db*`, cache dirs, `medical_knowledge`,
  `dist`, `build`

### 2. Pre-flight script: `bin/aria-preflight`

Eseguito automaticamente da `bin/aria` prima di `repl|run|mode`:

- **Kill zombie sessions**: cerca processi `kilo` con `ppid=1` e
  `cwd=$ARIA_HOME`, li termina (TERM). Reap dei figli MCP orfani.
- **WAL checkpoint**: se `kilo.db-wal` > 50MB e nessun processo legge
  il DB, esegue `PRAGMA wal_checkpoint(TRUNCATE)`.
- **Snapshot prune**: rimuove dirs sotto `kilo/snapshot/` più vecchie
  di `ARIA_SNAPSHOT_TTL_DAYS` (default 2).
- **Branch diff warning**: se `git diff origin/main` > 200KB stampa
  warning (rebase/push consigliato per evitare review hang).
- **Uncommitted warning**: stesso threshold per `git diff HEAD`.

Override: `ARIA_SKIP_PREFLIGHT=1`, `ARIA_SNAPSHOT_TTL_DAYS=N`,
`ARIA_BRANCH_DIFF_WARN_BYTES=N`, `ARIA_PREFLIGHT_VERBOSE=1`.

### 3. Cleanup eseguito (incident 2026-04-29)

| Azione | Recupero |
|--------|----------|
| Kill 12 procs zombie aria-conductor | 8.9GB RAM |
| WAL checkpoint kilo.db | 431MB → 0 |
| VACUUM kilo.db | 3.1GB → 2.8GB |
| Delete snapshot stale | 4.5GB |
| Stash uncommitted (`git stash` con tag `pre-restart cleanup 2026-04-29`) | review prompt 211KB → 187KB (committed only) |
| Backup + remove file `-` (SARIF dump 65KB in root) | -- |

## Funzionalità preservate

- ✅ Tutte le sessioni storiche restano nel DB (no perdita chat).
- ✅ Tutti i 13 MCP server restano abilitati.
- ✅ `ARIA_DEFAULT_AGENT` invariato.
- ✅ Permessi/allowlist invariati.
- ❌ Snapshot per-sessione disabilitati — kilo non offre rollback
  workspace via `/snapshot`. Mitigazione: usa `git stash`.

## Trigger condizioni che potrebbero ricreare il freeze

1. Abilitare `snapshot: true` manualmente in `kilo.jsonc`.
2. Branch con > 500 file modificati o > 1MB diff vs base.
3. DB > 5GB (richiede pruning sessioni vecchie).
4. Disattivare `bin/aria-preflight` (`ARIA_SKIP_PREFLIGHT=1`).

## Verifica futura

Comando smoke test post-deploy:

```bash
ARIA_PREFLIGHT_VERBOSE=1 /home/fulvio/coding/aria/bin/aria-preflight
# atteso: zombie kill: 0, WAL ok, no stale snapshots, branch diff ok
```
