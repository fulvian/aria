---
title: Tools & MCP Ecosystem
sources:
  - docs/foundation/aria_foundation_blueprint.md §10
  - docs/foundation/decisions/ADR-0009-kilo-agent-frontmatter-and-mcp-bin-resolution.md
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

## MCP Server MVP

| Server | Tipo | Scopo | Avvio |
|--------|------|-------|-------|
| `aria-memory` | Custom (FastMCP) | Memoria 5D (remember, recall, distill...) | Python via KiloCode |
| `tavily` | Custom wrapper | Search synthesis | `scripts/wrappers/tavily-wrapper.sh` |
| `firecrawl` | Custom wrapper | Deep scraping, AI extract | `scripts/wrappers/firecrawl-wrapper.sh` |
| `brave` | npm package | Privacy search | `scripts/wrappers/brave-wrapper.sh` |
| `exa` | Custom (FastMCP) | Semantic academic search | Python via KiloCode |
| `searxng` | Custom (FastMCP) | Meta search self-hosted | Python via KiloCode |
| `google_workspace` | Upstream (`uvx`) | Gmail, Calendar, Drive, Docs, Sheets | `scripts/wrappers/google-workspace-wrapper.sh` |
| `filesystem` | npm (`@modelcontextprotocol/server-filesystem`) | File system access | npx |
| `git` | uvx (`mcp-server-git`) | Git operations | uvx |
| `github` | npm wrapper (`@modelcontextprotocol/server-github`) | GitHub API | `scripts/wrappers/github-wrapper.sh` |
| `sequential-thinking` | npm | Reasoning | npx |
| `fetch` | uvx (`mcp-server-fetch`) | Web fetching | uvx |

*source: `docs/foundation/aria_foundation_blueprint.md` §10.3*

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

## MCP Tool ID Namespacing

KiloCode espone MCP tools come `<sanitize(serverKey)>_<sanitize(toolName)>` dove `sanitize` sostituisce caratteri non alfanumerici con `_` (hyphens preservati).

Esempi:
- `tavily-mcp_search`
- `aria-memory_remember`
- `google_workspace_send_gmail_message`

## Tool Surface Totale

12 server MCP → ~197 tools totali (al 2026-04-21). Ogni sub-agente vede un sottoinsieme ≤ 20 (P9).

## Implementazione Codice

```
src/aria/tools/
├── __init__.py
├── tavily/          # FastMCP Tavily server
├── firecrawl/       # FastMCP Firecrawl server
├── exa/             # FastMCP Exa server
└── searxng/         # FastMCP SearXNG server
```

## Vedi anche

- [[agents-hierarchy]] — Tool access matrix per sub-agente
- [[search-agent]] — Provider search dettaglio
- [[workspace-agent]] — Google Workspace tools
