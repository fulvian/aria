# Ripristino Agenti Ricerca + Google Workspace — Progress

## 2026-04-27T14:10 — Ripristino completato

**Plan**: `docs/plans/rispristino_agenti_ricerca_google.md`
**Branch**: `fix/memory-recovery`

## Phase Status

| Phase | Status | Key Deliverables |
|-------|--------|-----------------|
| Phase 0: Diagnostic Lockdown | ✅ COMPLETE | Backup files, baseline log, RC confirmed |
| Phase 1: Credential Store | ✅ COMPLETE | SOPS YAML, 8+6+1+1 keys, acquire() OK |
| Phase 2: Env Configuration | ✅ COMPLETE | .env vars, .env.example, wiki profile google_email |
| Phase 3: Brave MCP Wrapper | ✅ COMPLETE | wrapper.sh, mcp.json patch |
| Phase 4: Google Workspace MCP | ⚠️ PARTIAL | wrapper+mcp.json OK, OAuth re-auth PENDING (HITL) |
| Phase 5: SearXNG | ✅ COMPLETE | Docker già attivo (8888), URL fix |
| Phase 6: Quality Gates | ✅ COMPLETE | ruff ✅, mypy ✅, pytest 36+52 ✅ |

## Credential Store — Multi-Account Rotation

| Provider | Keys | Strategy |
|----------|------|----------|
| Tavily | 8 (multi-account) | least_used |
| Firecrawl | 6 (multi-account) | least_used |
| Exa | 1 | least_used |
| Brave | 1 | least_used |

## Pending
- **OAuth re-auth** (Phase 4.3): richiede browser flow per write scopes
- **Test MCP REPL live**: verificare che `/mcps` mostra tutti i server enabled

## Quality Gates
| Check | Status |
|-------|--------|
| ruff check src/aria/credentials/ | ✅ PASS |
| mypy src/aria/credentials/ | ✅ SUCCESS |
| pytest tests/unit/credentials/ | ✅ 36 PASSED |
| pytest tests/unit/agents/search/ | ✅ 52 PASSED |
| SearXNG HTTP test | ✅ 200 OK |
| Credential acquire (4/4) | ✅ ALL OK |
