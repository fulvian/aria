# Phase 0 Implementation Notes

Piano sprint-level canonico:
- `docs/plans/phase-0/sprint-00.md`

## Stato

Phase 0 completata e verificata con audit tecnico del 2026-04-20.

## Remediation applicate in audit

- allineati entrypoint runtime placeholder:
  - `src/aria/memory/mcp_server.py`
  - `src/aria/scheduler/daemon.py`
  - `src/aria/gateway/daemon.py`
  - `src/aria/credentials/__main__.py`
- corretto comportamento help launcher: `bin/aria` gestisce `repl --help` senza invocare binari esterni;
- corretta policy segreti in `.gitignore`:
  - tracciati solo `.aria/credentials/.sops.yaml` e `.aria/credentials/secrets/*.enc.yaml`;
  - ignorati file plaintext e artefatti `.age.pub`;
- aggiunto checkpoint WAL pre-backup in `scripts/backup.sh` (coerenza con policy SQLite);
- completato backlog ADR richiesto da sprint plan:
  - `docs/foundation/decisions/ADR-0003-oauth-security-posture.md`
  - `docs/foundation/decisions/ADR-0004-associative-memory-persistence-format.md`

## Evidenze verifica

Comandi eseguiti con esito OK:

```bash
ruff check .
ruff format --check .
uv run mypy src
uv run pytest -q
./scripts/bootstrap.sh --check
./scripts/smoke_db.sh
./bin/aria --help
./bin/aria memory --help
systemd-analyze verify systemd/aria-scheduler.service
```

Nota operativa: il comando `aria repl` resta dipendente dalla disponibilita del binario KiloCode nel sistema target (rischio R1 dello sprint).
