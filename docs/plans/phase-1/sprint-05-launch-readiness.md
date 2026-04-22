---
document: ARIA Phase 1 — Sprint 1.5 Launch Readiness & First Real Run
version: 1.0.0
status: draft
date_created: 2026-04-21
last_review: 2026-04-21
owner: fulvio
phase: 1
sprint: "1.5"
canonical_blueprint: docs/foundation/aria_foundation_blueprint.md
phase_overview: docs/plans/phase-1/README.md
depends_on: docs/plans/phase-1/sprint-04.md
---

# Sprint 1.5 — Launch Readiness, Credentials Finalization, First Real End-to-End Run

## 1) Objective

Close all remaining operational gaps after B1-B4 remediation and define a deterministic, production-safe first startup procedure for:

1. ARIA via CLI (`./bin/aria repl` and `./bin/aria run ...`)
2. ARIA via Telegram Gateway (`systemd --user` + real bot interaction)

This sprint is implementation + operations-hardening only (no new features).

## 2) Inputs and Current State (as-is)

- Phase 0 and Phase 1 implementation are present; quality gates are green (`ruff`, `mypy`, `pytest`).
- B2/B3/B4 are completed at data level (SOPS migration + `.env` clarification).
- Remaining user actions are known:
  - Fill real `ARIA_TELEGRAM_WHITELIST` in `.env`
  - Store Telegram bot token in keyring
  - Align `providers_state.enc.yaml` `key_id` values with real keys in `api-keys.enc.yaml`
  - Delete backup `api-keys.enc.yaml.age-bak` only after verification

## 3) Official Documentation Baseline (Context7, mandatory)

The implementation and run procedure MUST follow the latest official docs resolved through Context7:

1. `python-telegram-bot` v22.5 (`/python-telegram-bot/python-telegram-bot/v22.5`)
   - Async `Application` + handlers (`CommandHandler`, `MessageHandler`, `CallbackQueryHandler`)
   - Polling lifecycle and clean shutdown expectations
2. `sops` (`/getsops/sops`)
   - `.sops.yaml` `creation_rules`, `path_regex`, `encrypted_regex`, `unencrypted_regex`
   - `sops <file>` edit workflow and `sops -d` round-trip verification
3. `keyring` (`/jaraco/keyring`)
   - `set_password`, `get_password`, `delete_password` usage model
4. `google_workspace_mcp` (`/taylorwilsdon/google_workspace_mcp`)
   - OAuth env contract (`GOOGLE_OAUTH_CLIENT_ID`, redirect URI, PKCE mode via wrapper/env)

## 4) Critical Gaps to Resolve Before First Real Launch

### G1 — Bootstrap/SOPS path drift

Observed drift:
- `.sops.yaml` is now at repo root, but `scripts/bootstrap.sh` still validates `.aria/credentials/.sops.yaml`.

Required fix:
- Update bootstrap checks and bootstrap messages to root `.sops.yaml`.
- Update docs/runbook examples to use `sops -d` (not `age -d`) for SOPS-managed files.

Acceptance:
- `./scripts/bootstrap.sh --check` passes on clean machine with root `.sops.yaml`.

### G2 — API keys schema vs `CredentialManager` loader

Observed risk:
- `src/aria/credentials/manager.py` expects `providers.<provider>.keys[]` with `key_id`.
- Current `.aria/credentials/secrets/api-keys.enc.yaml` uses `providers.<provider>[]` with `id`.

Impact:
- Provider key loading can silently skip keys in real runtime, causing no-key availability despite encrypted secrets being present.

Required fix (one of two, choose and standardize):
- Option A (preferred): normalize secrets file to canonical schema (`keys[]`, `key_id`).
- Option B: add backward-compatible loader mapping for list-style provider payload (`id` -> `key_id`).

Acceptance:
- `aria creds status --provider tavily` shows all configured Tavily keys.
- Provider wrapper smoke tests can acquire at least 1 key per configured provider.

### G3 — providers_state key alignment

Observed drift:
- Runtime state contains placeholder/legacy key IDs not matching real IDs in encrypted secrets.

Required fix:
- Align `providers_state.enc.yaml` `key_id`s to the canonical IDs loaded from `api-keys.enc.yaml`.
- Preserve counters where mapping is deterministic; otherwise reset provider runtime state safely.

Acceptance:
- `CredentialManager.acquire(<provider>)` returns key IDs that actually exist in encrypted secrets.

### G4 — Telegram bootstrap and whitelist hardening

Required actions:
- Set `ARIA_TELEGRAM_WHITELIST` to real numeric Telegram user ID(s).
- Store bot token using canonical command path:
  - `./bin/aria creds put telegram.bot_token -v "<token>"`

Acceptance:
- Gateway starts without `Telegram bot token not available`.
- Non-whitelisted user messages are dropped; whitelisted user can run `/start`, `/status`.

### G5 — Operations documentation drift

Required updates:
- `docs/operations/runbook.md` first-launch section aligned with current codebase and wrappers.
- Explicitly document first launch both CLI and Telegram.
- Add troubleshooting decision tree for credential misalignment and OAuth/token issues.

Acceptance:
- A fresh operator can execute first launch using only runbook + this sprint document.

## 5) Work Breakdown Structure (WBS)

### W1.5.A — Credential data model convergence

Deliverables:
- Canonical credential schema documented in one place (`api-keys.enc.yaml` contract).
- Migration utility or runtime compatibility layer.
- Tests for both canonical and legacy formats (if backward compatibility retained).

Verification:
- Unit tests in `tests/unit/credentials/` cover parser behavior.
- Integration smoke on real encrypted file succeeds.

### W1.5.B — Runtime state reconciliation tool/procedure

Deliverables:
- Deterministic reconciliation command or script (idempotent):
  - decrypt runtime state
  - map/replace key IDs from encrypted source of truth
  - re-encrypt atomically
- Operator-safe instructions with pre/post checks.

Verification:
- Before/after report lists changed key IDs.
- `aria creds status` consistent with secrets file.

### W1.5.C — Bootstrap/runbook hardening

Deliverables:
- Fix `scripts/bootstrap.sh` SOPS path assumptions.
- Update runbook commands for SOPS and keyring flows.
- Add explicit preflight command bundle.

Verification:
- `./scripts/bootstrap.sh --check` green.
- Documented preflight command block passes on target environment.

### W1.5.D — First launch via CLI (real)

Procedure (must be codified in docs):
1. `./scripts/bootstrap.sh --check`
2. `uv sync --extra dev`
3. Ensure `.env` has real `ARIA_TELEGRAM_WHITELIST`
4. Verify SOPS decrypt round-trip:
   - `sops -d .aria/credentials/secrets/api-keys.enc.yaml >/dev/null`
   - `sops -d .aria/runtime/credentials/providers_state.enc.yaml >/dev/null`
5. Verify credential loader:
   - `./bin/aria creds status --provider tavily`
6. CLI smoke:
   - `./bin/aria run "Test isolamento ARIA: rispondi solo OK"`
   - `./bin/aria repl` then simple memory/search command

Acceptance:
- CLI answers are returned; no credential-loading errors in logs.

### W1.5.E — First launch via Telegram (real)

Procedure (must be codified in docs):
1. Store bot token in keyring:
   - `./bin/aria creds put telegram.bot_token -v "<BotFather-token>"`
2. Install/reload user services:
   - `./scripts/install_systemd.sh install`
   - `./scripts/install_systemd.sh reload`
3. Start services:
   - `systemctl --user start aria-gateway.service aria-scheduler.service`
4. Check service health:
   - `systemctl --user status aria-gateway.service --no-pager`
   - `systemctl --user status aria-scheduler.service --no-pager`
5. Open Telegram and run:
   - `/start`
   - `/status`
   - Send text message and verify gateway reply path
6. HITL check:
   - Trigger a known `policy=ask` task and verify inline keyboard callback flow

Acceptance:
- End-to-end Telegram interaction works for whitelisted user.
- HITL callback path emits and resolves events correctly.

### W1.5.F — Post-verification cleanup and hardening

Deliverables:
- Remove backup artifact only after successful round-trip and startup:
  - `.aria/credentials/secrets/api-keys.enc.yaml.age-bak`
- Record evidence in `docs/implementation/phase-1/`.
- Update `.workflow/state.md` and phase tracker.

Acceptance:
- No stale transitional secret artifacts remain.
- Evidence package includes exact command outputs and timestamps.

## 6) First Real Launch Checklist (Operator Run Card)

### 6.1 Preflight

- [ ] `./scripts/bootstrap.sh --check`
- [ ] `sqlite3 --version` >= 3.51.3
- [ ] `python -c "import sqlite3; print(sqlite3.sqlite_version)"` >= 3.51.3
- [ ] `.env` updated with real `ARIA_TELEGRAM_WHITELIST`
- [ ] `sops -d` works for both encrypted credentials files

### 6.2 Credentials

- [ ] `api-keys.enc.yaml` schema validated against `CredentialManager`
- [ ] `providers_state.enc.yaml` key IDs aligned
- [ ] `./bin/aria creds status --provider tavily` shows expected keys
- [ ] Telegram bot token stored in keyring

### 6.3 Services

- [ ] `aria-gateway.service` active
- [ ] `aria-scheduler.service` active
- [ ] `journalctl --user -u aria-gateway.service -n 100 --no-pager` has no auth/token fatal errors

### 6.4 Functional tests

- [ ] CLI command returns expected output
- [ ] Telegram `/start` and `/status` pass
- [ ] Telegram text message reaches bridge path
- [ ] HITL callback resolves in scheduler store

### 6.5 Cleanup

- [ ] Remove `.age-bak` only after all checks pass
- [ ] Store implementation evidence document

## 7) Quality Gates

Run before declaring launch-ready:

```bash
ruff check src tests
ruff format --check src tests
mypy src
pytest -q
./scripts/bootstrap.sh --check
systemd-analyze verify systemd/aria-*.service
```

Operational validation gates:

```bash
./bin/aria creds status --provider tavily
./bin/aria run "healthcheck"
systemctl --user is-active aria-gateway.service aria-scheduler.service
journalctl --user -u aria-gateway.service -n 50 --no-pager
```

## 8) Risk Register

| ID | Risk | Impact | Mitigation |
|----|------|--------|------------|
| R51 | Credential schema mismatch persists | High | Enforce canonical schema + parser tests |
| R52 | providers_state misalignment blocks provider rotation | High | Reconciliation step before any launch |
| R53 | Telegram whitelist misconfigured | Medium | Dedicated preflight with explicit fail-fast logs |
| R54 | bootstrap check stale after .sops.yaml move | Medium | Update script + CI check |
| R55 | accidental deletion of `.age-bak` before validation | Medium | Delete only at W1.5.F gate |

## 9) Exit Criteria

Sprint 1.5 is complete only if all are true:

- [ ] Credential loading works with real encrypted files (no placeholder mismatch)
- [ ] CLI launch path verified with real runtime state
- [ ] Telegram launch path verified with real bot token + whitelist
- [ ] HITL callback round-trip verified from Telegram inline buttons
- [ ] bootstrap + runbook aligned with actual repo paths and commands
- [ ] Transitional backup `api-keys.enc.yaml.age-bak` removed post-verification
- [ ] Evidence document committed under `docs/implementation/phase-1/`

## 10) Implementation Order (recommended)

1. W1.5.A (schema convergence)
2. W1.5.B (runtime state reconciliation)
3. W1.5.C (bootstrap/runbook hardening)
4. W1.5.D (CLI first launch)
5. W1.5.E (Telegram first launch)
6. W1.5.F (cleanup + evidence)

This order minimizes false negatives during launch testing.
