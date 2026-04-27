# MCP API Key Operations (Research Stack)

**Last Updated**: 2026-04-27T15:36  
**Status**: ✅ FULLY RESTORED — multi-account rotation con 17 keys totali (8 Tavily, 6 Firecrawl, 1 Exa, 1 Brave) + SearXNG self-hosted  
**Scope**: `tavily-mcp`, `firecrawl-mcp`, `exa-script`, `searxng-script`, `brave-mcp` — key loading, rotation-aware startup, circuit breaker

## 1) Objective

Documentare in modo operativo come ARIA avvia i MCP di ricerca quando le API key arrivano da environment, placeholder `${VAR}`, o da storage cifrato con rotazione.

## 2) Credential Store

### Architettura Generale

```
┌─────────────────────────────────────────────────────────┐
│                    CredentialManager                      │
│  (src/aria/credentials/manager.py)                       │
│                                                          │
│  ├── SopsAdapter    → decrypt api-keys.enc.yaml          │
│  ├── Rotator        → circuit breaker + key rotation     │
│  ├── KeyringStore   → OS keyring + age fallback          │
│  └── AuditLogger    → telemetry                          │
└─────────────────────────────────────────────────────────┘
```

### File Chiave

| File | Scopo | SOPS? |
|------|-------|-------|
| `.aria/credentials/secrets/api-keys.enc.yaml` | Chiavi API cifrate (17 keys totali) | ✅ SOPS+age |
| `.aria/runtime/credentials/providers_state.enc.yaml` | Stato runtime rotator (circuit breaker, credits, cooldown) | ✅ SOPS+age |
| `.env` (gitignorato) | Env fallback per OAuth creds + SearXNG URL | ❌ Plaintext (gitignorato) |

### Schema api-keys.enc.yaml

```yaml
version: 1
providers:
  tavily:
    keys:
      - key_id: tvly-fulviold
        api_key: "tvly-dev-..."
        free_tier_credits: 1000
      # ... 7 altre chiavi (grazia, pietro, fulvio-vr, federica, github-pro, microsoft, fulvian)
  firecrawl:
    keys:
      - key_id: fc-fulviold
        api_key: "fc-..."
        free_tier_credits: 500
      # ... 5 altre chiavi (grazia, pietro, fulvio-vr, federica, github-pro)
  exa:
    keys:
      - key_id: exa-primary
        api_key: "..."
        free_tier_credits: 1000
  brave:
    keys:
      - key_id: brave-primary
        api_key: "BSA-..."
        free_tier_credits: 2000
google_oauth:
  client_id: "...apps.googleusercontent.com"
  client_secret: "GOCSPX-..."
```

**Nota**: `google_oauth` non è usato dal Rotator ma dal wrapper google-workspace-wrapper.sh come fallback (o da `.env`).

### Cifratura SOPS

```bash
# Verifica decrypt
sops -d .aria/credentials/secrets/api-keys.enc.yaml

# Re-encrypt (se serve modificare)
# 1. decrpyta → modifica → encrypt
sops -d api-keys.enc.yaml > plain.yaml
# modifica plain.yaml poi:
sops --encrypt plain.yaml > api-keys.enc.yaml
shred -u plain.yaml
```

## 3) Provider Configuration

### 3.0 Panoramica Wrapper

Tutti i wrapper seguono lo stesso pattern:
1. Strip placeholder `${VAR}` letterali (trattati come unset)
2. Backward-compat alias (es. `BRAVE_API_KEY_ACTIVE` → `BRAVE_API_KEY`)
3. Auto-acquire via `CredentialManager.acquire(provider)` se env var mancante
4. Avvio server anche senza chiave (warning su stderr — evita stato `disabled` in `/mcps`)

### 3.1 Tavily (`tavily-mcp`)

| Campo | Valore |
|-------|--------|
| Wrapper | `scripts/wrappers/tavily-wrapper.sh` |
| Comando | `npx -y tavily-mcp@0.2.19` |
| Env var | `TAVILY_API_KEY` |
| Keys (Rotator) | 8 (multi-account: fulviold, grazia, pietro, fulvio-vr, federica, github-pro, microsoft, fulvian) |
| Rotator strategy | `least_used` |
| Free tier | 1000 req/mo per chiave |

### 3.2 Firecrawl (`firecrawl-mcp`)

| Campo | Valore |
|-------|--------|
| Wrapper | `scripts/wrappers/firecrawl-wrapper.sh` |
| Comando | `npx -y firecrawl-mcp@3.10.3` |
| Env var | `FIRECRAWL_API_KEY`, `FIRECRAWL_API_URL` |
| Keys (Rotator) | 6 (multi-account: fulviold, grazia, pietro, fulvio-vr, federica, github-pro) |
| Rotator strategy | `least_used` |
| Free tier | 500 credits lifetime |

### 3.3 Exa (`exa-script`)

| Campo | Valore |
|-------|--------|
| Wrapper | `scripts/wrappers/exa-wrapper.sh` |
| Comando | `npx -y exa-mcp-server@3.2.1` |
| Env var | `EXA_API_KEY` |
| Keys (Rotator) | 1 (exa-primary) |
| Rotator strategy | `least_used` |
| Free tier | 1000 req/mo |

### 3.4 Brave (`brave-mcp`) — NEW 2026-04-27

| Campo | Valore |
|-------|--------|
| Wrapper | `scripts/wrappers/brave-wrapper.sh` |
| Comando | `npx -y @brave/brave-search-mcp-server --transport stdio` |
| Env var | `BRAVE_API_KEY` (NO `_ACTIVE`) |
| Backward-compat | `BRAVE_API_KEY_ACTIVE` → `BRAVE_API_KEY` |
| Keys (Rotator) | 1 (brave-primary) |
| Rotator strategy | `least_used` |
| Free tier | $5/mo free credits |

**Context7 verification**: `/brave/brave-search-mcp-server` — env var name è `BRAVE_API_KEY`.

### 3.5 SearXNG (`searxng-script`)

| Campo | Valore |
|-------|--------|
| Wrapper | `scripts/wrappers/searxng-wrapper.sh` |
| Comando | `npx -y searxng-mcp@1.0.1` |
| Env var | `SEARXNG_SERVER_URL` (o `SEARXNG_URL` fallback) |
| URL runtime | `http://127.0.0.1:8888` |
| Docker | ✅ `searxng/searxng:latest`, `restart: unless-stopped` |
| Auto-detect | Wrapper fa `curl` su port 8888 alla startup; se OK usa quello, altrimenti 8080 |

## 4) Rotation Internals (ARIA)

### Rotator (`src/aria/credentials/rotator.py`)

**Strategie di rotazione**:
- `least_used` (default): seleziona chiave con più crediti rimanenti
- `round_robin`: seleziona chiave con `last_used_at` più vecchio
- `failover`: seleziona prima chiave disponibile

**Circuit Breaker**:
| Stato | Condizione | Azione |
|-------|-----------|--------|
| CLOSED | Funzionamento normale | Chiave disponibile |
| OPEN | 3 failure in 5 minuti | Cooldown 30 min |
| HALF_OPEN | Cooldown scaduto | 1 probe request |
| OPEN (con escalation) | Failure in HALF_OPEN | Cooldown raddoppiato (max 120 min) |

### Provider Health (`ResearchRouter`)

La health state di ogni provider viene aggiornata ogni 5 minuti:
- `AVAILABLE` → almeno una chiave `CLOSED` nel Rotator
- `DEGRADED` → almeno una chiave `OPEN`
- `CREDITS_EXHAUSTED` → crediti esauriti
- `DOWN` → nessuna chiave registrata

SearXNG ha health sempre `AVAILABLE` (self-hosted, nessun Rotator coinvolto).

## 5) Operatività (runbook)

### 5.1 Verifica stato

```bash
# Stato di tutti i provider
python -m aria.credentials status

# Stato specifico
python -m aria.credentials status --provider tavily

# Richiedi una chiave (test)
python -m aria.credentials rotate tavily

# Ricarica chiavi da SOPS
python -m aria.credentials reload

# Audit log
python -m aria.credentials audit --tail 20
```

### 5.2 MCP in runtime

1. `./bin/aria repl`
2. In TUI: `/mcps` → deve mostrare 12 MCP enabled:
   - filesystem, git, github, sequential-thinking, fetch, aria-memory
   - tavily-mcp, firecrawl-mcp, exa-script, searxng-script, brave-mcp
   - google_workspace

### 5.3 Log diagnostici

```
.aria/kilo-home/.local/share/kilo/log/*.log
.aria/runtime/logs/credentials-YYYY-MM-DD.log
```

### 5.4 Nota: Brave richiede la chiave a startup

**Critical difference**: A differenza di Tavily, Firecrawl, ed Exa (che partono anche senza chiave e falliscono solo al tool call), **il server Brave Search MCP richiede `BRAVE_API_KEY` obbligatoriamente a startup** e termina immediatamente se non presente.

Senza la chiave:
1. Wrapper stampa `WARN: BRAVE_API_KEY missing` (stderr)
2. `npx @brave/brave-search-mcp-server` parte senza `--brave-api-key`
3. Server termina con `Error: --brave-api-key is required`
4. Kilo vede connessione chiusa → marca `brave-mcp` come `disabled`

**Fix**: Assicurarsi che `SOPS_AGE_KEY_FILE` sia nell'environment del wrapper (di default non lo è in Kilo MCP). Il wrapper `brave-wrapper.sh` ha fallback automatico.

**Diagnostica rapida**:
```bash
# Verificare che la chiave sia acquisibile
cd /home/fulvio/coding/aria
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
.venv/bin/python -m aria.credentials rotate brave

# Verificare che il wrapper parta senza errori
unset BRAVE_API_KEY
bash scripts/wrappers/brave-wrapper.sh  # deve partire senza WARN
```

## 6) Failure Modes

| Problema | Sintomo | Causa | Fix |
|----------|---------|-------|-----|
| Placeholder `${VAR}` | Validazione fallita a startup | Env var non risolta | Wrapper normalizza `${VAR}` → unset |
| Wrapper mancante | `ENOENT posix_spawn` | File non presente | Creare/symlink wrapper |
| Tool call 422 | Brave search error | `BRAVE_API_KEY_ACTIVE` (sbagliata) vs `BRAVE_API_KEY` | Usare `BRAVE_API_KEY` |
| Tool call 401 | Token/API error | Chiave scaduta/invalida | `python -m aria.credentials status` |
| `acquire()` returns None | Provider non disponibile | Credential store non decriptabile | `sops -d api-keys.enc.yaml` |
| SearXNG fetch failed | Timeout | Docker non avviato | `docker start searxng` |

### 6.4 Context7 Verification Matrix (2026-04-27)

| Provider | Context7 ID | Env Var | Status |
|----------|-------------|---------|--------|
| Tavily MCP | `/tavily-ai/tavily-mcp` | `TAVILY_API_KEY` | ✅ |
| Firecrawl MCP Server | `/firecrawl/firecrawl-mcp-server` | `FIRECRAWL_API_KEY`, `FIRECRAWL_API_URL` | ✅ |
| Exa MCP Server | `/exa-labs/exa-mcp-server` | `EXA_API_KEY` | ✅ |
| Brave Search MCP | `/brave/brave-search-mcp-server` | `BRAVE_API_KEY` (CLI: `--brave-api-key`) | ✅ — NOTA: richiede chiave **a startup** |
| Google Workspace MCP | `/taylorwilsdon/google_workspace_mcp` | `GOOGLE_OAUTH_CLIENT_ID/SECRET` | ✅ |
| SearXNG MCP | wiki-cached | `SEARXNG_SERVER_URL` | ✅ — Docker 8888 |

## 7) Provenance

- `.aria/kilocode/mcp.json` (canonical config, aggiornato 2026-04-27)
- `.aria/credentials/secrets/api-keys.enc.yaml` (17 keys, SOPS+age, 2026-04-27)
- `scripts/wrappers/{tavily,firecrawl,exa,searxng,brave,google-workspace}-wrapper.sh`
- `src/aria/credentials/manager.py` (CredentialManager, 2026-04-27)
- `src/aria/credentials/rotator.py` (circuit-breaker policy, 2026-04-27)
- `src/aria/credentials/sops.py` (SOPS adapter, 2026-04-27)
- Context7 `/brave/brave-search-mcp-server` (env var verification, 2026-04-27)
- Context7 `/taylorwilsdon/google_workspace_mcp` (single-user, tools list, 2026-04-27)
