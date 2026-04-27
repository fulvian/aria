# Ripristino Agenti Ricerca + Google Workspace — Final Findings

## Root Cause Resolution

| RC | Component | Status | Fix |
|----|-----------|--------|-----|
| RC-1 | `api-keys.enc.yaml` raw age binary | ✅ FIXED | Ricreato come SOPS+age YAML con 17 keys (8 Tavily, 6 Firecrawl, 1 Exa, 1 Brave) |
| RC-2 | `.env` chiavi commentate | ✅ FIXED | Aggiunte: SEARXNG_SERVER_URL, GOOGLE_OAUTH_CLIENT_ID/SECRET, USER_GOOGLE_EMAIL |
| RC-3 | `brave-mcp` env var `BRAVE_API_KEY_ACTIVE` | ✅ FIXED | Creato brave-wrapper.sh, mcp.json → BRAVE_API_KEY |
| RC-4 | searxng URL default 127.0.0.1:8080 | ✅ FIXED | Docker già attivo su 8888, wrapper auto-rileva, .env punta a 8888 |
| RC-5 | google_workspace --tools senza gmail/calendar | ✅ FIXED | Wrapper v2: `gmail drive calendar docs sheets slides` |
| RC-6 | GOOGLE_OAUTH_CLIENT_ID non esportato | ✅ FIXED | In .env + wrapper fallback da token JSON |
| RC-7 | workspace-mcp non in single-user mode | ✅ FIXED | `--single-user` flag nel wrapper |
| RC-8 | profilo wiki senza google_email | ✅ FIXED | `wiki_update` → profile con `google_email: fulviold@gmail.com` |
| RC-9 | token scaduto | ⚠️ MITIGATED | Refresh_token nel JSON; single-user + env vars permettono auto-refresh a runtime. **Scopes ancora readonly** — serve OAuth re-auth per write. |

## System State

### Credential Rotation
- **Tavily**: 8 keys, strategy: `least_used`
- **Firecrawl**: 6 keys, strategy: `least_used`
- **Exa**: 1 key, strategy: `least_used`
- **Brave**: 1 key, strategy: `least_used`
- **Circuit breaker**: CLOSED per tutti (0 failures)

### SearXNG
- Docker container `searxng` su `127.0.0.1:8888`
- `restart: unless-stopped` — auto-riavvio al boot
- Config bind mount: `.aria/runtime/searxng/settings.yml`
- HTTP test: 200 OK

### Google Workspace (pending OAuth re-auth)
- Token JSON presente con refresh_token
- client_id: `22168029632-om1sdk9h9alt1khjoa6edm7sfkhseepi.apps.googleusercontent.com`
- client_secret: presente
- Scopes attuali: **readonly** per docs/sheets/slides/drive, **modify** per gmail
- Write scopes mancanti: `documents`, `spreadsheets`, `presentations`, `drive.file`
