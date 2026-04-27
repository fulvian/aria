# Piano Ripristino Agenti Ricerca + Google Workspace

**Created**: 2026-04-27
**Branch**: `fix/memory-recovery`
**Status**: DRAFT — pending approval
**Scope**: ricerca multi-tier (`searxng`/`tavily`/`firecrawl`/`exa`/`brave`) + Google Workspace (Drive/Docs/Sheets/Slides/**Gmail**/**Calendar**)
**Stella Polare**: `docs/foundation/aria_foundation_blueprint.md`
**Wiki sources**:
- `docs/llm_wiki/wiki/research-routing.md`
- `docs/llm_wiki/wiki/google-workspace-mcp-write-reliability.md`
- `docs/llm_wiki/wiki/mcp-api-key-operations.md`
- `docs/llm_wiki/wiki/aria-launcher-cli-compatibility.md`
**Context7 refs**: `/taylorwilsdon/google_workspace_mcp` (queried 2026-04-27), `/brave/brave-search-mcp-server` (queried 2026-04-27)

---

## 1. Sintomi Osservati

### Sessione `ses_23188b734ffe1CUAxuBnHmwi2p` (ricerca crime 2026)
- `firecrawl_search` → `API key is required for the cloud API. Set FIRECRAWL_API_KEY env or pass apiKey.`
- `brave_web_search` → `422 SUBSCRIPTION_TOKEN_INVALID`
- `tavily_search` → `MCP error -32600: TAVILY_API_KEY environment variable is required.`
- `exa_web_search_exa` → `(401) API key must be provided ... EXA_API_KEY`
- `searxng_search_web` → `Failed to fetch search results: TypeError: fetch failed`
- `fetch_fetch`/`webfetch` su rotten/imdb → 404 / readability extractor crash
- Tier ladder NON applicato: il conduttore prova provider in ordine arbitrario, non `searxng → tavily → firecrawl → exa → brave`.

### Sessione `ses_2317f07dbffe2tWTen102iBqEb` (email Francesco Minchillo)
- `aria-memory_wiki_recall_tool` → restituisce profilo senza email Google.
- Conductor non trova `user_google_email` → chiede a Fulvio.
- `google_workspace_search_drive_files` → richiesta OAuth con URL contenente literal `%24%7BGOOGLE_OAUTH_CLIENT_ID%7D` (placeholder non risolto).
- `task workspace-agent` → segnala assenza scope Gmail nel server MCP (`--tools docs sheets slides drive`).
- Sessione muore senza recuperare email/documenti.

### Diagnosi sintetica
Sistema **degraded multi-livello**:
1. provider chiavi non disponibili runtime (env + credential store down)
2. `google_workspace` MCP avviato senza Gmail/Calendar tools
3. OAuth client Google non esportato in env
4. profilo memoria non contiene `user_google_email`
5. `brave-mcp` env var name mismatch
6. `searxng` punta a 127.0.0.1:8080 inattivo

---

## 2. Root Cause Analysis

| ID | Componente | Causa Verificata | Evidence |
|----|-----------|-------------------|----------|
| **RC-1** | `.aria/credentials/secrets/api-keys.enc.yaml` | File è **raw age binary** (`age-encryption.org/v1` header), non SOPS-encrypted YAML. `SopsAdapter.decrypt()` fallisce: `Error unmarshalling input yaml: invalid leading UTF-8 octet`. `CredentialManager.acquire(prov)` ritorna `None` per **tutti** i provider. | `file ...api-keys.enc.yaml` → `age encrypted file, X25519 recipient`; `sops -d` → unmarshal error; probe Python `acquire()` → `tavily/firecrawl/exa/brave => NONE` |
| **RC-2** | `.env` | Tutte le chiavi commentate (`# TAVILY_API_KEY=...`, `# BRAVE_API_KEY=...`, `# FIRECRAWL_API_KEY=...`, `# EXA_API_KEY=...`, `# GOOGLE_OAUTH_CLIENT_ID=...`). Nessun fallback env. | `.env:36-45` |
| **RC-3** | `brave-mcp` in `mcp.json` | Avviato senza wrapper; env var name = `BRAVE_API_KEY_ACTIVE` ma upstream richiede `BRAVE_API_KEY` (Context7 `/brave/brave-search-mcp-server`). Placeholder `${BRAVE_API_KEY_ACTIVE}` mai sostituito → token 0-byte → 422. | `.aria/kilocode/mcp.json:54`; Context7 conferma var name |
| **RC-4** | `searxng-script` | Default fallback `http://127.0.0.1:8080` ma nessuna istanza SearXNG locale attiva. SEARXNG_SERVER_URL non impostato. | `scripts/wrappers/searxng-wrapper.sh:20`; sessione → `fetch failed` |
| **RC-5** | `google_workspace` MCP `--tools` flag | Configurato `docs sheets slides drive`. Upstream supporta `gmail drive calendar docs sheets chat forms slides tasks contacts search appscript` (verifica `uvx workspace-mcp --help`). Gmail e Calendar **non registrati**. | `mcp.json:74-82`; `workspace-mcp --help` output |
| **RC-6** | `GOOGLE_OAUTH_CLIENT_ID`/`_SECRET` | Mancano in `.env`. `mcp.json` passa `${GOOGLE_OAUTH_CLIENT_ID}` literal al server. Server genera URL OAuth invalido. | `.env:43-44` (commentato); URL OAuth contiene `%24%7BGOOGLE_OAUTH_CLIENT_ID%7D` |
| **RC-7** | Workspace MCP non in `--single-user` mode | Server cerca mappatura sessione→credenziale; richiede `user_google_email` ad ogni call. Credenziali esistenti `fulviold@gmail.com.json` (refresh_token + scopes Gmail/Drive/Docs/Sheets/Slides/Calendar già concessi 2026-04-23) **non auto-caricate**. | `runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json` (scopes presenti); Context7 `--single-user` flag spec |
| **RC-8** | Memoria profilo wiki | Slug `profile` non contiene `user_google_email`. Conductor deve chiederlo o derivarlo dal file `google_workspace_user_email.txt`. | session log shows ask-user; `runtime/credentials/google_workspace_user_email.txt` presente ma non letto |
| **RC-9** | Token access scaduto | `expiry: 2026-04-24T11:12:55` → scaduto da 3 giorni. Refresh automatico richiede `client_id`+`client_secret` in env (RC-6) o presenti nel JSON (presenti, ma server li usa solo se `--single-user`). | JSON file expiry field |

### Catena di causazione

```
RC-1 (store corrotto)  ─┐
RC-2 (.env vuoto)       ├─→ CredentialManager.acquire = NONE → wrapper warn-only
RC-3 (brave var name)   ─┘                                      → MCP avviato → tool call 4xx
RC-4 (searxng URL)      ────→ tier 1 instance not running → fetch fails

RC-5 (--tools manca gmail) ─→ workspace MCP no gmail tools → conductor non trova email
RC-6 (no client_id env)    ─→ OAuth URL literal placeholder → user click fa 404
RC-7 (no --single-user)    ─→ refresh_token esistente non usato → server chiede re-auth
RC-8 (profile no email)    ─→ conductor non sa user_google_email → chiede a utente
RC-9 (token expired)       ─→ chiamate API 401 anche se MCP partisse
```

---

## 3. Verifica Context7 (CLAUDE.md mandate)

| Library | Context7 ID | Purpose | Findings |
|---------|-------------|---------|----------|
| Google Workspace MCP | `/taylorwilsdon/google_workspace_mcp` | Verify env vars, single-user, tools list | `GOOGLE_OAUTH_CLIENT_ID` + `GOOGLE_OAUTH_CLIENT_SECRET` mandatory; `USER_GOOGLE_EMAIL` per single-user; `--single-user` flag bypassa session mapping; `--tools gmail drive calendar docs sheets` syntax |
| Brave Search MCP | `/brave/brave-search-mcp-server` | Verify env var name | `BRAVE_API_KEY` (no `_ACTIVE` suffix); default transport stdio (post 2.x) |
| Tavily MCP | wiki-cached `tavily-mcp@0.2.19` | Verify env | `TAVILY_API_KEY` standard |
| Firecrawl MCP | wiki-cached `firecrawl-mcp@3.10.3` | Verify env | `FIRECRAWL_API_KEY` + optional `FIRECRAWL_API_URL` |
| Exa MCP | wiki-cached `exa-mcp-server@3.2.1` | Verify env | `EXA_API_KEY` standard |
| SearXNG MCP | wiki-cached `searxng-mcp@1.0.1` | Verify URL contract | `SEARXNG_SERVER_URL` required at startup |

Reject criteria: nessun deliverable usa libreria/var name non verificati.

---

## 4. Strategia di Ripristino — Phased

### Phase 0 — Diagnostic Lockdown (15 min)

Goal: snapshot stato prima di modifiche.

- [ ] `git stash --keep-index` su modifiche pending non correlate.
- [ ] Backup file: `.aria/credentials/secrets/api-keys.enc.yaml` → `*.bak.20260427`
- [ ] Backup `runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json` → `*.bak`
- [ ] Salva output `python -m aria.credentials status` (anche se vuoto).
- [ ] Salva log `.aria/kilo-home/.local/share/kilo/log/*.log` (ultimo) per regressione baseline.

**Acceptance**: backup files presenti, baseline log salvato.

### Phase 1 — Ricostruzione Credential Store (30 min) [RC-1, RC-2]

Goal: ripristinare `api-keys.enc.yaml` come SOPS-encrypted YAML conforme a `.sops.yaml`.

#### 1.1 Verifica age key
```bash
test -f ~/.config/sops/age/keys.txt && echo OK
age-keygen -y ~/.config/sops/age/keys.txt
# atteso: age1ar7v0rm6kxlrm33slxkvt3qp25807pksav4ptpc0vyguekvhhprse68gja
```

#### 1.2 Genera schema baseline
File `.aria/credentials/secrets/api-keys.enc.yaml` deve essere YAML con campi `key`/`api_key`/`secret`/`token`/`client_secret` cifrati per regex (per `.sops.yaml`).

Schema target (pre-encrypt):
```yaml
version: 1
providers:
  tavily:
    keys:
      - id: tavily_primary
        api_key: "tvly-XXXXXXXXXXXX"
        free_tier_credits: 1000
        rotation_policy: monthly
  firecrawl:
    keys:
      - id: firecrawl_primary
        api_key: "fc-XXXXXXXXXXXX"
        api_url: "https://api.firecrawl.dev"
        free_tier_credits: 500
  exa:
    keys:
      - id: exa_primary
        api_key: "exa_XXXXXXXXXXXX"
        free_tier_credits: 1000
  brave:
    keys:
      - id: brave_primary
        api_key: "BSA-XXXXXXXXXXXX"
        free_tier_credits: 2000
google_oauth:
  client_id: "PLACEHOLDER_CLIENT_ID"
  client_secret: "PLACEHOLDER_CLIENT_SECRET"
```

> Note: gli ID in `google_oauth` esistono già in `runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json` (Phase 4 li riutilizza).

#### 1.3 Cifratura
```bash
cd /home/fulvio/coding/aria
mv .aria/credentials/secrets/api-keys.enc.yaml .aria/credentials/secrets/api-keys.enc.yaml.broken
# scrivi nuovo plaintext temporaneo .aria/credentials/secrets/api-keys.plaintext.yaml
sops --encrypt --age age1ar7v0rm6kxlrm33slxkvt3qp25807pksav4ptpc0vyguekvhhprse68gja \
  --encrypted-regex '^(key|token|api_key|secret|password|client_secret)$' \
  .aria/credentials/secrets/api-keys.plaintext.yaml > .aria/credentials/secrets/api-keys.enc.yaml
shred -u .aria/credentials/secrets/api-keys.plaintext.yaml
```

#### 1.4 Verifica ciclo decrypt
```bash
sops -d .aria/credentials/secrets/api-keys.enc.yaml | head -20
.venv/bin/python -m aria.credentials status
.venv/bin/python -m aria.credentials status --provider tavily
```

**Acceptance**:
- `sops -d` ritorna YAML strutturato (no `invalid leading UTF-8 octet`).
- `aria.credentials status` mostra `tavily/firecrawl/exa/brave: AVAILABLE`.
- `acquire("tavily")` ritorna `KeyInfo` non-`None`.

### Phase 2 — Env Configuration (15 min) [RC-2, RC-6, RC-8]

Goal: `.env` contiene tutto il necessario per fallback diretto + bootstrap OAuth.

#### 2.1 Patch `.env`
Aggiungere (NON committare):
```bash
# === Provider API Keys (loaded by bin/aria) ===
TAVILY_API_KEY=tvly-XXXXXXXXXXXX
FIRECRAWL_API_KEY=fc-XXXXXXXXXXXX
EXA_API_KEY=exa_XXXXXXXXXXXX
BRAVE_API_KEY=BSA-XXXXXXXXXXXX

# === Google Workspace OAuth ===
GOOGLE_OAUTH_CLIENT_ID=PLACEHOLDER_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET=PLACEHOLDER_CLIENT_SECRET
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8080/callback
USER_GOOGLE_EMAIL=fulviold@gmail.com

# === SearXNG (deferred — see Phase 5) ===
# SEARXNG_SERVER_URL=https://searx.be
```

#### 2.2 Aggiorna `.env.example`
Inserire le nuove variabili come placeholder commentati (non valori reali).

#### 2.3 Aggiorna profilo wiki memoria
Tramite tool MCP:
```python
wiki_update(
  kind="profile",
  slug="profile",
  patch={
    "section": "Identity",
    "fields": {"google_email": "fulviold@gmail.com"}
  }
)
```

**Acceptance**:
- `bin/aria` esporta correttamente le var (verify via `bin/aria env-print` o `printenv` in shell-out).
- `wiki_recall("email")` restituisce profilo con `google_email` field.

### Phase 3 — Brave MCP Wrapper (15 min) [RC-3]

Goal: env var name allineata + uniformità con altri research wrapper.

#### 3.1 Crea `scripts/wrappers/brave-wrapper.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

# Strip placeholder
if [[ "${BRAVE_API_KEY:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset BRAVE_API_KEY
fi
# Backward-compat alias
if [[ -z "${BRAVE_API_KEY:-}" ]] && [[ -n "${BRAVE_API_KEY_ACTIVE:-}" ]]; then
  if [[ ! "$BRAVE_API_KEY_ACTIVE" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
    export BRAVE_API_KEY="$BRAVE_API_KEY_ACTIVE"
  fi
fi

# Auto-acquire via rotator
if [[ -z "${BRAVE_API_KEY:-}" ]] && [[ -x "$PYTHON_BIN" ]]; then
  ACQUIRED_KEY="$($PYTHON_BIN - <<'PY' || true
import asyncio
from aria.config import get_config
from aria.credentials.manager import CredentialManager
async def main() -> str:
    cm = CredentialManager(get_config())
    k = await cm.acquire("brave")
    return k.key.get_secret_value() if k else ""
print(asyncio.run(main()), end="")
PY
)"
  [[ -n "$ACQUIRED_KEY" ]] && export BRAVE_API_KEY="$ACQUIRED_KEY"
fi

if [[ -z "${BRAVE_API_KEY:-}" ]]; then
  echo "WARN: BRAVE_API_KEY missing; brave-mcp will start but tool calls return 422." >&2
fi

exec npx -y @brave/brave-search-mcp-server --transport stdio
```
Make executable: `chmod +x scripts/wrappers/brave-wrapper.sh`

#### 3.2 Patch `.aria/kilocode/mcp.json`
```jsonc
"brave-mcp": {
  "command": "/home/fulvio/coding/aria/scripts/wrappers/brave-wrapper.sh",
  "disabled": false,
  "env": {
    "BRAVE_API_KEY": "${BRAVE_API_KEY}"
  }
}
```

**Acceptance**:
- `/mcps` mostra `brave-mcp` enabled e healthy.
- Tool call `brave_web_search` ritorna risultati (HTTP 200, no 422).

### Phase 4 — Google Workspace MCP Expansion (45 min) [RC-5, RC-6, RC-7, RC-9]

Goal: Gmail + Calendar abilitati; `--single-user` mode per riutilizzo refresh_token; OAuth env propagato.

#### 4.1 Patch `.aria/kilocode/mcp.json`
```jsonc
"google_workspace": {
  "command": "/home/fulvio/coding/aria/scripts/wrappers/google-workspace-wrapper.sh",
  "disabled": false,
  "env": {
    "GOOGLE_OAUTH_CLIENT_ID": "${GOOGLE_OAUTH_CLIENT_ID}",
    "GOOGLE_OAUTH_CLIENT_SECRET": "${GOOGLE_OAUTH_CLIENT_SECRET}",
    "GOOGLE_OAUTH_REDIRECT_URI": "http://127.0.0.1:8080/callback",
    "GOOGLE_OAUTH_USE_PKCE": "true",
    "OAUTHLIB_INSECURE_TRANSPORT": "1",
    "USER_GOOGLE_EMAIL": "${USER_GOOGLE_EMAIL}",
    "GOOGLE_WORKSPACE_TOOLS": "gmail drive calendar docs sheets slides"
  },
  "_comment": "@phase1 write-enabled — single-user, gmail+calendar incluse"
}
```

#### 4.2 Aggiorna `scripts/wrappers/google-workspace-wrapper.sh`
- Default `TOOLS="${GOOGLE_WORKSPACE_TOOLS:-gmail drive calendar docs sheets slides}"`
- Aggiungi flag `--single-user` al comando finale.
- Fallback: se env client_id/secret mancanti, leggi dal JSON `runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json` (campi `client_id`/`client_secret`) e esporta.

Diff principale:
```bash
# Build command — sempre single-user con tool set esteso
CMD="uvx workspace-mcp --single-user --tools $TOOLS"
```

#### 4.3 OAuth re-authentication (token scaduto)
Se `expiry < now`:
```bash
cd /home/fulvio/coding/aria
source .env
python3 scripts/oauth_first_setup.py  # genera nuovi PKCE + URL
```
Gli scope da richiedere (write completi):
```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.modify
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/calendar
https://www.googleapis.com/auth/calendar.events
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/drive.file
https://www.googleapis.com/auth/documents
https://www.googleapis.com/auth/spreadsheets
https://www.googleapis.com/auth/presentations
```

**HITL CHECKPOINT** — re-auth richiede browser utente; lo invochiamo solo dopo conferma di Fulvio (Comandamento P7).

#### 4.4 Verifica scopes post-auth
```bash
python3 scripts/workspace_auth.py
python3 scripts/workspace-write-health.py --verbose
```

**Acceptance**:
- `uvx workspace-mcp --help` confirma supporto Gmail/Calendar (già verificato).
- `mcp.json` runtime contiene `--single-user` e `--tools gmail drive calendar docs sheets slides`.
- Tool call `search_gmail_messages` (o equivalente) ritorna risultati per `from:francesco.minchillo`.
- Token JSON ha `expiry > now`.

### Phase 5 — SearXNG Tier-1 Re-enable (variabile) [RC-4]

Goal: opzione realistica per tier 1.

Tre alternative — scegliere UNA:

**Opzione A** — Public SearXNG instance (immediato, nessun infra):
```bash
# .env
SEARXNG_SERVER_URL=https://searx.be
```
Trade-off: rate limit pubblico, latenza variabile.

**Opzione B** — SearXNG self-hosted via Docker (1-2 ore setup):
```yaml
# docker-compose.yml
services:
  searxng:
    image: searxng/searxng:latest
    ports: ["8888:8080"]
    environment:
      - BASE_URL=http://127.0.0.1:8888/
```
Poi: `SEARXNG_SERVER_URL=http://127.0.0.1:8888`

**Opzione C** — Disabilitare temporaneamente, accettare degraded tier 1→2:
- `disabled: true` in `mcp.json` per `searxng-script`
- Aggiornare `research-routing.md`: tavily diventa de-facto tier 1 finché SearXNG manca.
- ADR-0008 da aprire (Comandamento P10: Self-Documenting Evolution).

**Acceptance** (opz A/B):
- `searxng_search_web("test query")` ritorna ≥3 risultati.

### Phase 6 — Acceptance Tests (30 min)

#### 6.1 Sanity script
Crea `scripts/diagnostics/check_research_stack.py`:
```python
"""Smoke test ricerca + workspace post-restore."""
import asyncio
from aria.config import get_config
from aria.credentials.manager import CredentialManager

async def main():
    cm = CredentialManager(get_config())
    for prov in ["tavily","firecrawl","exa","brave"]:
        k = await cm.acquire(prov)
        print(f"{prov}: {'OK' if k else 'MISSING'}")

asyncio.run(main())
```
Atteso: 4×OK.

#### 6.2 MCP smoke (REPL)
```
./bin/aria repl
> /mcps
# atteso: tutti 7 MCP enabled (filesystem, git, github, fetch, aria-memory,
#   tavily-mcp, firecrawl-mcp, exa-script, searxng-script, brave-mcp,
#   google_workspace, sequential-thinking)
> "fai una ricerca: best crime tv series 2026"
# atteso: search-agent usa tier 1 (searxng o tavily se opz C),
#   non chiede chiavi, ritorna risultati strutturati
> "cerca le mie email da Francesco Minchillo nell'ultimo mese"
# atteso: workspace-agent usa search_gmail_messages, ritorna lista email
```

#### 6.3 Tier policy compliance
Verifica search-agent.md e blueprint §11.2 ancora aligned (no drift).

#### 6.4 Quality gate
```
make lint
make typecheck
pytest -q tests/unit/credentials
pytest -q tests/unit/agents/search
```

---

## 5. Rollback Strategy

| Phase | Rollback action |
|-------|-----------------|
| P1 | `mv api-keys.enc.yaml.bak.20260427 api-keys.enc.yaml` |
| P2 | `git checkout .env.example`; rimuovi var aggiunte da `.env` |
| P3 | `rm scripts/wrappers/brave-wrapper.sh`; ripristina entry brave-mcp originale in `mcp.json` |
| P4 | `git checkout scripts/wrappers/google-workspace-wrapper.sh .aria/kilocode/mcp.json`; restore JSON token |
| P5 | `disabled: true` su `searxng-script` |

Tutti gli artefatti modificati sono tracciati git → `git diff` permette revert chirurgico.

---

## 6. HITL Gates (Comandamento P7)

Azioni che richiedono conferma esplicita di Fulvio:
1. **Fornire chiavi API reali** (Tavily/Firecrawl/Exa/Brave) per scrivere `api-keys.enc.yaml` — l'agente non genera chiavi.
2. **OAuth re-authentication browser flow** (Phase 4.3) — richiede click utente.
3. **Modifica `.env`** con segreti reali — Fulvio fornisce e verifica `.env` non committato.
4. **Rimozione del file `.broken`** dopo verifica positiva del nuovo store.

---

## 7. Documentation Updates (Comandamento P10)

Al completamento:
- Aggiornare `docs/llm_wiki/wiki/index.md` (raw sources table + Last Updated).
- Append entry in `docs/llm_wiki/wiki/log.md` con timestamp + operazione + verifica.
- Aggiornare `docs/llm_wiki/wiki/google-workspace-mcp-write-reliability.md` (sezione Gmail/Calendar enabled).
- Aggiornare `docs/llm_wiki/wiki/mcp-api-key-operations.md` (sezione Brave wrapper, schema api-keys).
- Aggiornare `docs/llm_wiki/wiki/research-routing.md` se Phase 5 opzione C → tavily promosso tier 1.
- Eventuale ADR-0008 se cambiamento policy routing.

---

## 8. Acceptance Criteria (Definition of Done)

Sistema considerato ripristinato quando:
- [ ] `python -m aria.credentials status` → tutti 4 provider AVAILABLE
- [ ] `/mcps` REPL → 12 MCP enabled, nessun disabled inatteso
- [ ] Search agent esegue `tier 1 → 2 → ...` documentato in tier policy
- [ ] `search_gmail_messages` ritorna email reali per query "from:francesco.minchillo"
- [ ] `search_drive_files` ritorna file reali per query con `name contains 'Minchillo'`
- [ ] `create_doc` (HITL-approved) crea documento Google Docs riutilizzabile
- [ ] Quality gate passa: `make lint && make typecheck && pytest -q`
- [ ] Wiki aggiornato (index + log + 2 pagine subsystem)
- [ ] HITL checkpoint Phase 4.3 superato (refresh_token aggiornato)

---

## 9. Stima Effort

| Phase | Tempo stimato | Rischio |
|-------|---------------|---------|
| P0 | 15 min | LOW |
| P1 | 30 min | MEDIUM (richiede chiavi reali + age key valida) |
| P2 | 15 min | LOW |
| P3 | 15 min | LOW |
| P4 | 45 min | HIGH (browser OAuth flow, token expiry) |
| P5 | 0–2h | variabile (opzione A=0, B=2h, C=15min) |
| P6 | 30 min | LOW |
| **Totale** | **2.5–4.5 h** | |

---

## 10. Provenance

- `bin/aria` (verified: env loading, isolation) — read 2026-04-27
- `.aria/kilocode/mcp.json` — read 2026-04-27
- `.aria/kilo-home/.config/kilo/kilo.jsonc` (runtime) — read 2026-04-27
- `.aria/credentials/secrets/api-keys.enc.yaml` — `file` 2026-04-27 → raw age binary
- `.sops.yaml` — read 2026-04-27 (creation_rules + encrypted_regex)
- `.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json` — read 2026-04-27 (scopes + expiry)
- `.aria/runtime/credentials/google_workspace_user_email.txt` — read 2026-04-27
- `scripts/wrappers/{tavily,firecrawl,exa,searxng,google-workspace}-wrapper.sh` — read 2026-04-27
- `src/aria/credentials/{manager,sops,rotator}.py` — inspected 2026-04-27
- `uvx workspace-mcp --help` — invoked 2026-04-27 (tools list verification)
- `npx @brave/brave-search-mcp-server --help` — invoked 2026-04-27 (env var verification)
- Context7 `/taylorwilsdon/google_workspace_mcp` — queried 2026-04-27
- Context7 `/brave/brave-search-mcp-server` — queried 2026-04-27
- Wiki pages: `research-routing.md`, `google-workspace-mcp-write-reliability.md`, `mcp-api-key-operations.md`, `aria-launcher-cli-compatibility.md`
- Session logs: `ses_23188b734ffe1CUAxuBnHmwi2p`, `ses_2317f07dbffe2tWTen102iBqEb`
