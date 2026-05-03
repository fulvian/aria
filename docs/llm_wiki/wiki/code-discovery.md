# Code Discovery Skill

**Last Updated**: 2026-05-03T18:35+02:00
**Status**: Active ✅ — v1.0.0
**Primary sources**: `.aria/kilocode/skills/code-discovery/SKILL.md`, `.aria/config/mcp_catalog.yaml` (context7 + github-discovery entries), `.aria/config/agent_capability_matrix.yaml` (search-agent allowed_tools), `docs/foundation/decisions/ADR-0016-proxy-http-headers-code-discovery.md`

## Purpose

La skill `code-discovery` estende `search-agent` con un workflow specializzato per ricerca **development-oriented**: docs lookup version-aware via Context7, repo discovery/screening/assessment via github-discovery, e fallback controllato su provider search standard ARIA.

## Backend MCP

### context7 (tier 1 — development docs)

| Proprietà | Valore |
|-----------|--------|
| Transport | HTTP |
| URL | `https://mcp.context7.com/mcp` |
| Auth | `Authorization: Bearer ${CONTEXT7_API_KEY}` |
| Tools | `resolve-library-id`, `query-docs` |
| Integrazione | Catalogo ARIA (`mcp_catalog.yaml`), proxy HTTP headers |
| Stato | ✅ Attivo |

Context7 è un MCP server HTTP remoto che fornisce documentazione ufficiale di librerie/framework con code examples. È il primo tier per l'intent `development` perché fornisce documentazione **grounded e version-aware**, superiore a ricerche web non strutturate.

### github-discovery (tier 2 — development repo analysis)

| Proprietà | Valore |
|-----------|--------|
| Transport | STDIO |
| Source of truth | `/home/fulvio/coding/github-discovery/.venv/bin/python -m github_discovery.mcp serve --transport stdio` |
| Credential | `GHDISC_GITHUB_TOKEN` (GitHub PAT) |
| Tools | 16 tool (discover_repos, screen_candidates, deep_assess, compare_repos, etc.) |
| Integrazione | Catalogo ARIA, env var wiring, SOPS credential store |
| Stato | ✅ Attivo |

github-discovery fornisce discovery, screening e valutazione comparativa di repository GitHub. Usato come secondo tier per l'intent `development`.

## Tier Ladder Development

| Step | Provider | Scopo |
|------|----------|-------|
| 1 | **context7** | Docs lookup ufficiale, version-aware |
| 2 | **github-discovery** | Repo discovery, screening, assessment |
| 3 | **searxng** | Fallback ricerca web generale |
| 4 | **tavily** | Fallback aggiuntivo |
| 5 | **exa** | Fallback premium |
| 6 | **brave** | Fallback |
| 7 | **fetch** | Fallback deep scrape |

## Workflow

### Fase 1 — Context7 Docs Lookup
1. `context7__resolve-library-id(query, libraryName)` → ottiene Context7 library ID
2. `context7__query-docs(libraryId, query)` → documentazione ufficiale e code examples
3. Massimo 3 chiamate `query-docs` per domanda

### Fase 2 — github-discovery Repo Analysis
1. `github-discovery__discover_repos(query)` → candidati repository
2. `github-discovery__screen_candidates(pool_id, gate_level)` → screening qualità
3. `github-discovery__quick_assess` / `deep_assess` → valutazione approfondita
4. `github-discovery__compare_repos` → confronto affiancato

### Fase 3 — Synthesis
Combinare docs ufficiali (Context7) + assessment repo (github-discovery) + fallback web in report strutturato con provenance tracciata.

### Fase 4 — Fallback
Se context7 o github-discovery non rispondono, scala attraverso la tier ladder standard.

## Proxy Integration

Tutte le chiamate ai backend MCP passano dal proxy tramite `aria-mcp-proxy__call_tool(name="call_tool", arguments={"name": "<server__tool>", "arguments": {...}, "_caller_id": "search-agent"})`.

### HTTP Headers Support (v7.3)
Per integrare Context7, il proxy ARIA è stato esteso per supportare backend HTTP con `headers` autenticati:
- `BackendSpec` ora include campo `headers: dict[str, str]`
- `to_mcp_entry()` produce `{"url": ..., "transport": ..., "headers": {...}}` per backend HTTP/SSE
- `CredentialInjector` risolve `${VAR}` placeholder sia in `env` che in `headers`
- Supporto placeholder inline: `"Bearer ${CONTEXT7_API_KEY}"` viene risolto correttamente

## Credential Pipeline

| Secret | Provider SOPS | Env Var | Uso |
|--------|--------------|---------|-----|
| GitHub PAT | `ghdisc` (key_id: `ghdisc-github-primary`, env_name: `GHDISC_GITHUB_TOKEN`) | `GHDISC_GITHUB_TOKEN` | github-discovery backend |
| Context7 API Key | `context7` (key_id: `context7-primary`, env_name: `CONTEXT7_API_KEY`) | `CONTEXT7_API_KEY` | context7 backend auth header |

## ADR

- **ADR-0016**: "Proxy HTTP Headers Support + Development Search Capability" — documenta le motivazioni architetturali e le decisioni tecniche.

## Provenance

- `.aria/kilocode/skills/code-discovery/SKILL.md` — skill definition v1.0.0
- `.aria/config/mcp_catalog.yaml` — context7 + github-discovery entries
- `.aria/config/agent_capability_matrix.yaml` — search-agent allowed_tools con `github-discovery__*` e `context7__*`
- `.aria/kilocode/agents/search-agent.md` — DEVELOPMENT tier ladder
- `src/aria/mcp/proxy/catalog.py` — headers field in BackendSpec
- `src/aria/mcp/proxy/credential.py` — inline `${VAR}` resolution
- `src/aria/credentials/manager.py` — `get()` + `_register_secret_aliases()`
- `docs/foundation/decisions/ADR-0016-proxy-http-headers-code-discovery.md`
