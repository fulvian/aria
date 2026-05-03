# ADR-0016: Proxy HTTP Headers Support + Development Search Capability

**Status**: Implemented
**Date**: 2026-05-03
**Authors**: fulvio
**Related**: ADR-0009 (MCP Catalog), ADR-0015 (FastMCP-Native Proxy)

## Context

ARIA's search-agent covers web search, social, academic, and deep scrape, but lacks
a specialized workflow for **development-oriented research**: library docs lookup,
repo discovery/evaluation, and comparative open-source analysis.

Two existing MCP servers provide exactly these capabilities:

1. **Context7** (`https://mcp.context7.com/mcp`) — Live library documentation lookup
   with version-aware docs and code examples. Uses HTTP MCP transport with
   `Authorization: Bearer` header authentication. Already configured in the global
   KiloCode environment (`~/.kilocode/mcp.json`) but **not integrated into the ARIA
   proxy system**.

2. **github-discovery** — KiloOrg repository discovery/screening/evaluation MCP.
   Already present in the ARIA catalog (`mcp_catalog.yaml`) but **incompletely
   integrated**: missing credential wiring (`env.GHDISC_GITHUB_TOKEN`), missing
   capability matrix entries for search-agent, and no E2E verification via proxy.

## Problem

Two structural gaps prevented real ARIA integration:

### Gap 1: Proxy HTTP Header Support
The `BackendSpec` data model (`catalog.py`) lacked support for HTTP `headers`,
which are required by Context7 (and other HTTP MCP backends like Helium) for
bearer-token authentication. The existing `CredentialInjector` only resolved
`${VAR}` placeholders in `env`, not in `headers`.

### Gap 2: Incomplete Catalog/Capability Integration
- `github-discovery` had no `env:` in its catalog entry, so the
  `GHDISC_GITHUB_TOKEN` credential was never wired to the backend process.
- Neither `github-discovery__*` nor `context7__*` were listed in search-agent's
  `allowed_tools` in the capability matrix, making them unreachable via policy.
- `context7` had no catalog entry at all in the ARIA system.

## Decision

### 1. Extend BackendSpec with `headers` support

Add `headers: dict[str, str]` to `BackendSpec` dataclass, extend `_parse_entry()`
to read headers from YAML, and extend `to_mcp_entry()` to include headers in the
FastMCP-compatible entry dict for HTTP/SSE backends.

### 2. Extend CredentialInjector for header resolution

The `_resolve()` method now handles **inline** `${VAR}` placeholders (e.g.,
`"Bearer ${CONTEXT7_API_KEY}"`) in addition to whole-value placeholders.
The `inject()` method resolves placeholders in both `env` and `headers`.

### 3. Extend CredentialManager for env-style lookup

Add `get(key)` method and `_register_secret_aliases()` infrastructure to
`CredentialManager` to support `${VAR}`-style credential resolution for the proxy,
with support for a custom `env_name` override per provider key item.

### 4. Register backends in catalog and capability matrix

- `github-discovery`: add `env.GHDISC_GITHUB_TOKEN` to catalog entry
- `context7`: new catalog entry with `transport: http`, `url`, `headers`
- Both backends added to search-agent's `allowed_tools` (as `github-discovery__*`
  and `context7__*`)
- `development` intent added to search-agent's `intent_categories`

### 5. Create `code-discovery` skill

New skill under `.aria/kilocode/skills/code-discovery/` providing the search-agent
with a structured workflow for development-oriented research:
- Phase 1: Context7 docs lookup (resolve-library-id → query-docs)
- Phase 2: github-discovery repo analysis (discover → screen → assess → compare)
- Phase 3: Synthesis with provenance tracking
- Phase 4: Fallback to standard web search providers

### 6. Add secrets to credential store

Both `GHDISC_GITHUB_TOKEN` (GitHub PAT for github-discovery) and `CONTEXT7_API_KEY`
(Context7 API key) added to:
- SOPS-encrypted credential store (`.aria/credentials/secrets/api-keys.enc.yaml`)
- `.env` runtime fallback
- `.env.example` documentation

## Consequences

### Positive
- HTTP MCP backends with bearer-token auth are now natively supported by the proxy
  (unblocks Context7, Helium, and future HTTP MCP integrations)
- `github-discovery` is now fully integrated with credentials wired through the
  catalog → injector → credential manager pipeline
- `context7` is reachable through the proxy with proper header authentication
- search-agent gains a structured development research workflow via the
  `code-discovery` skill
- CredentialManager `get()` method enables env-style proxy credential lookup both
  from SOPS and from environment variables

### Negative
- Additional credential maintenance burden (two new API keys)
- Context7 is a freemium service (rate limits may apply)
- The double-underscore naming convention (`server__tool`) must be maintained
  until the codebase-wide migration is completed

### Neutral
- `development` intent routing is heuristic (keyword-based), may need tuning
- The `code-discovery` skill is prompt-based, not runtime-enforced

## Compliance

- `AGENTS.md`: all quality gates respected, Context7-first verification for library
  documentation enforced in skill
- Isolation first: backend calls go through the proxy, never direct
- Upstream invariance: no fork/modify of KiloCode source
- Tool priority: Context7 > github-discovery > web search (maintaining MCP > skill > local script)

## Files Changed

| File | Change |
|------|--------|
| `src/aria/mcp/proxy/catalog.py` | Added `headers` to `BackendSpec`, updated `to_mcp_entry()` and `_parse_entry()` |
| `src/aria/mcp/proxy/credential.py` | Inline `${VAR}` resolution, headers placeholder support |
| `src/aria/credentials/manager.py` | `get()` method, `_register_secret_aliases()`, `env_name` override |
| `.aria/config/mcp_catalog.yaml` | Added `env` to github-discovery, new `context7` entry with headers |
| `.aria/config/agent_capability_matrix.yaml` | Added `github-discovery__*`, `context7__*`, `development` intent |
| `.aria/kilocode/agents/search-agent.md` | DEVELOPMENT tier ladder, code-discovery skill |
| `.aria/kilocode/skills/code-discovery/SKILL.md` | New skill |
| `.aria/credentials/secrets/api-keys.enc.yaml` | Added ghdisc + context7 providers |
| `.env` | Added GHDISC_GITHUB_TOKEN |
| `.env.example` | Added GHDISC_GITHUB_TOKEN, CONTEXT7_API_KEY docs |
| `tests/unit/mcp/proxy/test_catalog.py` | 9 new tests (HTTP/SSE, headers, parsing) |
| `tests/unit/mcp/proxy/test_credential.py` | 5 new tests (headers resolution) |
