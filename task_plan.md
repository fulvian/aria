# Ripristino Agenti Ricerca + Google Workspace

## Goal
Implementare `docs/plans/rispristino_agenti_ricerca_google.md` — ripristinare ricerca multi-tier (searxng/tavily/firecrawl/exa/brave) + Google Workspace (Gmail/Calendar/Drive/Docs/Sheets/Slides).

## Root Causes (9)
- **RC-1**: `api-keys.enc.yaml` raw age binary → `sops -d` fails → `acquire()` returns None
- **RC-2**: `.env` ha tutte le chiavi commentate (nessun env fallback)
- **RC-3**: `brave-mcp` env var name `BRAVE_API_KEY_ACTIVE` ma upstream richiede `BRAVE_API_KEY`
- **RC-4**: searxng default URL `127.0.0.1:8080` non in esecuzione
- **RC-5**: `google_workspace --tools docs sheets slides drive` (manca gmail+calendar)
- **RC-6**: `GOOGLE_OAUTH_CLIENT_ID/_SECRET` non esportati
- **RC-7**: workspace-mcp non in `--single-user` mode → refresh_token non auto-caricato
- **RC-8**: profilo wiki memoria non contiene `user_google_email`
- **RC-9**: token access scaduto (expiry 2026-04-24)

## Phases

### Phase 0 — Diagnostic Lockdown [DONE ✅]
- [x] Backup `api-keys.enc.yaml` → `*.bak.20260427`
- [x] Backup `fulviold@gmail.com.json` → `*.bak.20260427`
- [x] Save credentials status → `.workflow/cred-status-baseline.log`
- [x] Save kilo log → `.workflow/kilo-log-baseline.log`
- [x] Verify all RC confirmed via probe

### Phase 1 — Ricostruzione Credential Store [HITL: API keys]
- [ ] HITL: Fornire chiavi API reali per Tavily/Firecrawl/Exa/Brave
- [ ] Decrypt: verify age key `~/.config/sops/age/keys.txt`
- [ ] Create plaintext YAML schema
- [ ] `sops --encrypt` → `api-keys.enc.yaml`
- [ ] `shred` plaintext
- [ ] Verify `sops -d` returns structured YAML
- [ ] Verify `acquire("tavily")` returns KeyInfo non-None

### Phase 2 — Env Configuration [HITL: secrets]
- [ ] HITL: Uncomment/populate `.env` with real key values
- [ ] Update `.env.example`
- [ ] Update wiki profile with `google_email`
- [ ] Verify `bin/aria env-print` shows vars

### Phase 3 — Brave MCP Wrapper
- [ ] Create `scripts/wrappers/brave-wrapper.sh`
- [ ] Patch `.aria/kilocode/mcp.json` → `BRAVE_API_KEY`
- [ ] Verify brave-mcp healthy in `/mcps`

### Phase 4 — Google Workspace MCP Expansion
- [ ] Patch `scripts/wrappers/google-workspace-wrapper.sh` → single-user + gmail/calendar
- [ ] Patch `.aria/kilocode/mcp.json` → expanded tools + single-user
- [ ] HITL: OAuth re-auth (browser flow)
- [ ] Verify scopes post-auth

### Phase 5 — SearXNG Tier-1
- [ ] HITL: Choose option A/B/C
- [ ] Implement chosen option

### Phase 6 — Acceptance Tests
- [ ] Credential smoke test (4× OK)
- [ ] MCP smoke via REPL
- [ ] Tier policy compliance
- [ ] Quality gate: ruff, mypy, pytest

### Documentation Updates
- [ ] Update wiki index.md raw sources + Last Updated
- [ ] Append entry in log.md
- [ ] Update google-workspace-mcp-write-reliability.md (Gmail/Calendar section)
- [ ] Update mcp-api-key-operations.md (Brave wrapper, schema)
- [ ] Update research-routing.md if SearXNG option C

## HITL Gates (per §6 del piano)
1. API keys for credential store
2. OAuth re-authentication browser flow (Phase 4.3)
3. `.env` modification with real secrets
4. Removal of `.broken` file after verification

## Quality Gates (per AGENTS.md)
- `ruff check .`
- `ruff format --check .`
- `mypy src`
- `pytest -q`
