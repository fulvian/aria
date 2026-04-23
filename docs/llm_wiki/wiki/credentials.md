---
title: Credentials
sources:
  - docs/foundation/aria_foundation_blueprint.md §13
  - docs/foundation/decisions/ADR-0001-dependency-baseline-2026q2.md
  - docs/foundation/decisions/ADR-0003-oauth-security-posture.md
last_updated: 2026-04-23
tier: 1
---

# Credential Management

## Architettura

ARIA usa un approccio a 3 livelli per la gestione delle credenziali:

| Livello | Scopo | Storage |
|---------|-------|---------|
| **SOPS+age** | API keys cifrate | `.aria/credentials/secrets/api-keys.enc.yaml` (IN GIT, cifrato) |
| **OS Keyring** | OAuth refresh tokens | Linux Secret Service (Gnome-keyring/KWallet) |
| **Runtime state** | Usage counters, circuit state | `.aria/runtime/credentials/providers_state.enc.yaml` (NO GIT, cifrato) |

*source: `docs/foundation/aria_foundation_blueprint.md` §13.1*

## SOPS+age Schema

**File cifrato**: `.aria/credentials/secrets/api-keys.enc.yaml`

Contenuto (decrypted):
```yaml
version: 1
providers:
  tavily:
    - id: tvly-1
      key: tvly-dev-XXXXXXXXXXXX
      credits_total: 1000
  firecrawl:
    - id: fc-1
      key: fc-XXXXXXXXXXXX
      credits_total: 500
  brave:
    - id: brave-1
      key: BSA-XXXXXXXXXXXX
  exa:
    - id: exa-1
      key: exa-XXXXXXXXXXXX
  github:
    token: ghp_XXXXXXXXXXXX
```

**Config SOPS** (`.sops.yaml`): usa age public key, cifra solo campi `key|token|api_key|secret|password`.

**ADR-0001**: SOPS Python binding deprecato → SOPS CLI Go binary v3.12.2 installato in `~/.local/bin/sops`.

*source: `docs/foundation/decisions/ADR-0001-dependency-baseline-2026q2.md`*

## OS Keyring per OAuth

Solo refresh_token Google Workspace:

```python
import keyring
keyring.set_password("aria.google_workspace", "primary", refresh_token)
rt = keyring.get_password("aria.google_workspace", "primary")
```

**Fallback** (se Secret Service non disponibile): file cifrato age in `.aria/credentials/keyring-fallback/` con chiave separata dal SOPS master key.

*source: `docs/foundation/aria_foundation_blueprint.md` §13.3, `docs/foundation/decisions/ADR-0003-oauth-security-posture.md` §2.3*

## Unified CredentialManager

API pubblica (`src/aria/credentials/manager.py`):

```python
from aria.credentials import CredentialManager

cm = CredentialManager()

# API key acquisition con rotation
key_info = cm.acquire(provider="tavily", strategy="least_used")

# OAuth token
oauth = cm.get_oauth(service="google_workspace", account="primary")

# Success/failure reporting
cm.report_success(provider="tavily", key_id=key_info.id, credits_used=1)
cm.report_failure(provider="tavily", key_id=key_info.id, reason="rate_limit")

# Status
status = cm.status(provider="tavily")
```

*source: `docs/foundation/aria_foundation_blueprint.md` §13.4*

## Circuit Breaker

| Stato | Condizione | Comportamento |
|-------|-----------|---------------|
| **Closed** | Normale operazione | Errori rari tollerati |
| **Open** | 3 failure in 5min | Cooldown 30min, acquire() skippa |
| **Half-open** | Dopo cooldown | 1 tentativo; ok → closed, fail → open esteso |

Parametri tunabili in config.

*source: `docs/foundation/aria_foundation_blueprint.md` §13.5*

## Audit Logging

Ogni operazione `cm.acquire/report_*` produce JSON in `.aria/runtime/logs/credentials_YYYY-MM-DD.log`:
```json
{"ts":"2026-04-20T14:32:10Z","op":"acquire","provider":"tavily","key_id":"tvly-1","result":"ok","credits_remaining":847}
```
Retention: 90gg, rotazione giornaliera.

*source: `docs/foundation/aria_foundation_blueprint.md` §13.6*

## Implementazione Codice

```
src/aria/credentials/
├── __init__.py
├── __main__.py       # CLI entry point
├── manager.py        # CredentialManager unified API
├── sops.py           # SOPS+age integration
├── keyring_store.py  # OS keyring wrapper
├── rotator.py        # Circuit breaker + key rotation
└── audit.py          # Audit logging
```

## CLI

```bash
aria creds status          # Status credenziali
aria creds reload          # Ricarica stato
aria creds rotate <prov>   # Rotazione key provider
aria creds put <key> --val # Inserimento nuova credenziale
```

## Vedi anche

- [[search-agent]] — Rotation e circuit breaker in uso
- [[workspace-agent]] — OAuth flow e keyring
- [[governance]] — Audit e security policy
