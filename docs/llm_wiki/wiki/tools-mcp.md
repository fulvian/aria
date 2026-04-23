---
title: Tools & MCP Ecosystem
sources:
  - docs/foundation/aria_foundation_blueprint.md §10
  - docs/foundation/decisions/ADR-0009-kilo-agent-frontmatter-and-mcp-bin-resolution.md
  - src/aria/tools/*/mcp_server.py
  - .aria/kilocode/kilo.json
last_updated: 2026-04-23
tier: 1
---

# Tools & MCP Ecosystem

## Tool Priority Ladder (P8)

Quando serve una nuova capability:

| Priorità | Opzione | Quando |
|----------|---------|-------|
| 1 | **MCP esistente maturo** | Configurare un server MCP pronto |
| 2 | **Skill che compone MCP** | Scrivere SKILL.md che orchestra tool esistenti |
| 3 | **Script Python locale** | `src/aria/tools/<provider>/cli.py` → promuovere a MCP entro 2 sprint |

**Vietato**: aggiungere Python se MCP equivalente esiste; aggiungere MCP se skill copre il caso.

*source: `docs/foundation/aria_foundation_blueprint.md` §10.1*

---

## MCP Server — Registry Completo

### Search Providers

| Server ID (kilo.json) | FastMCP name | Tipo | Tool esposti | Avvio | Key rotation |
|-----------------------|-------------|------|-------------|-------|-------------|
| `tavily-mcp` | `"tavily-mcp"` | Custom (FastMCP) | `search` | `scripts/wrappers/tavily-wrapper.sh` | ✅ Max 5 attempts |
| `exa-script` | `"exa-script"` | Custom (FastMCP) | `search` | `scripts/wrappers/exa-wrapper.sh` | ✅ Max 5 attempts |
| `firecrawl-mcp` | `"firecrawl-mcp"` | Custom (FastMCP) | `search`, `scrape`, `extract` | `scripts/wrappers/firecrawl-wrapper.sh` | ✅ (search), single (scrape/extract) |
| `searxng-script` | `"searxng-script"` | Custom (FastMCP) | `search` | `scripts/wrappers/searxng-wrapper.sh` | N/A (no key) |
| `brave-mcp` | npm package | npm | `brave_web_search` etc. | `scripts/wrappers/brave-wrapper.sh` | N/A (single key via env) |

### Workspace & Productivity

| Server ID | Tipo | Scopo | Avvio |
|-----------|------|-------|-------|
| `google_workspace` | Upstream (`uvx`) | Gmail, Calendar, Drive, Docs, Sheets, Slides | `scripts/wrappers/google-workspace-wrapper.sh` |

### Infrastructure

| Server ID | Tipo | Scopo | Avvio |
|-----------|------|-------|-------|
| `aria-memory` | Custom (FastMCP) | Memoria 5D (remember, recall, distill...) | Python via KiloCode |
| `filesystem` | npm (`@modelcontextprotocol/server-filesystem`) | File system access | npx |
| `git` | uvx (`mcp-server-git`) | Git operations | uvx |
| `github` | npm (`@modelcontextprotocol/server-github`) | GitHub API | `scripts/wrappers/github-wrapper.sh` |
| `sequential-thinking` | npm | Structured reasoning | npx |
| `fetch` | uvx (`mcp-server-fetch`) | Web fetching | uvx |

*source: `.aria/kilocode/kilo.json`, `docs/foundation/aria_foundation_blueprint.md` §10.3*

---

## Search MCP Server Architecture

Ogni search MCP server segue questo pattern:

```
┌─────────────────────────────────────────┐
│  Wrapper bash (scripts/wrappers/)       │
│  - env -i (clean environment)           │
│  - SOPS_AGE_KEY_FILE per decrypt        │
│  - exec python -m aria.tools.X.mcp      │
├─────────────────────────────────────────┤
│  FastMCP Server (src/aria/tools/X/)     │
│  - @mcp.tool decorated async functions  │
│  - Key rotation loop (provider a pagamento) │
│  - CredentialManager integration        │
│  - ToolError on failure → isError: true │
│  - Transport: stdio                     │
├─────────────────────────────────────────┤
│  Provider Adapter (src/aria/agents/search/) │
│  - HTTP client (httpx)                  │
│  - request_json_with_retry (tenacity)   │
│  - KeyExhaustedError → ProviderError    │
│  - Normalizzazione SearchHit            │
└─────────────────────────────────────────┘
```

**SearXNG è l'eccezione**: niente API key, niente key rotation, niente CredentialManager.
Il provider usa un lazy singleton e si disabilita automaticamente se `ARIA_SEARCH_SEARXNG_URL` è vuoto.

*source: `src/aria/tools/*/mcp_server.py`, `scripts/wrappers/*-wrapper.sh`*

---

## ADR-0009: Risoluzione Problemi MCP

### Problema 1: npx bin resolution per scoped package

Server MCP come `@modelcontextprotocol/server-filesystem` fallivano con `sh: 1: @scope/pkg: not found` perché npx non risolve il bin name dal package scope.

**Soluzione**: Forma esplicita:
```json
["npx", "-y", "--package=<@scope/pkg>", "<bin-name>", "<args...>"]
```

### Problema 2: MCP config location

KiloCode legge MCP config dal blocco `mcp:` inline in `kilo.json`, NON da un file `mcp.json` separato (quello è formato Claude-Desktop).

**Soluzione**: Tutti i server MCP inlineati in `.aria/kilocode/kilo.json` sotto `mcp:`.

### Problema 3: Wrapper scripts per secret injection

I wrapper bash (`scripts/wrappers/`) decryptano SOPS, estraggono la key necessaria, exportano come env var, e poi eseguono il server MCP. Questo garantisce che le secret non entrino mai in plaintext in config files.

*source: `docs/foundation/decisions/ADR-0009-kilo-agent-frontmatter-and-mcp-bin-resolution.md`*

---

## MCP Tool ID Namespacing

KiloCode espone MCP tools come `<sanitize(serverKey)>_<sanitize(toolName)>` dove `sanitize` sostituisce caratteri non alfanumerici con `_` (hyphens preservati).

Esempi:
- `tavily-mcp_search` → server "tavily-mcp", tool "search"
- `exa-script_search` → server "exa-script", tool "search"
- `firecrawl-mcp_scrape` → server "firecrawl-mcp", tool "scrape"
- `searxng-script_search` → server "searxng-script", tool "search"
- `aria-memory_remember` → server "aria-memory", tool "remember"
- `google_workspace_send_gmail_message` → server "google_workspace", tool "send_gmail_message"

## Tool Surface Totale

12+ server MCP → ~197 tools totali (al 2026-04-23). Ogni sub-agente vede un sottoinsieme ≤ 20 (P9).

---

## Implementazione Codice

```
src/aria/tools/
├── tavily/
│   └── mcp_server.py    # FastMCP("tavily-mcp") — search + key rotation
├── firecrawl/
│   └── mcp_server.py    # FastMCP("firecrawl-mcp") — search/scrape/extract + key rotation
├── exa/
│   └── mcp_server.py    # FastMCP("exa-script") — search + key rotation
└── searxng/
    └── mcp_server.py    # FastMCP("searxng-script") — search, no key needed

scripts/wrappers/
├── tavily-wrapper.sh    # env isolation + SOPS key → tavily mcp_server
├── exa-wrapper.sh       # env isolation + SOPS key → exa mcp_server
├── firecrawl-wrapper.sh # env isolation + SOPS key → firecrawl mcp_server
├── searxng-wrapper.sh   # env isolation + ARIA_SEARCH_SEARXNG_URL
└── brave-wrapper.sh     # npm wrapper for @brave/brave-search-mcp-server
```

---

## Vedi anche

- [[agents-hierarchy]] — Tool access matrix per sub-agente
- [[search-agent]] — Provider search dettaglio (key rotation, error handling, fallback tree)
- [[workspace-agent]] — Google Workspace tools
- [[credentials]] — SOPS+age, CredentialManager, circuit breaker
