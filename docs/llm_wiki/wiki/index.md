# ARIA LLM Wiki — Index

**Last Updated**: 2026-04-27T22:15 (ADR-0006 approvato, push su GitHub)
**Status**: ✅ COMPLETE — Ricerca: 6 provider operativi + 3 MCP nuovi (PubMed, Scientific Papers, Reddit). ADR-0006 accepted. Feature branch su GitHub.

## Purpose

This wiki is the single source of project knowledge for LLMs working in this repository. Per AGENTS.md, all meaningful changes must update the wiki. Ogni fatto qui riportato ha provenienza tracciata (source path + data).

## Wiki Structure

```
docs/llm_wiki/
├── ext_knowledge/          # Raw extracted sources (external docs)
│   └── README.md
├── wiki/                  # Synthesized knowledge
│   ├── index.md          # This file — wiki overview
│   ├── log.md            # Implementation log
│   ├── memory-subsystem.md
│   ├── memory-v3.md
│   ├── research-routing.md
│   ├── google-workspace-mcp-write-reliability.md
│   ├── mcp-api-key-operations.md
│   ├── aria-launcher-cli-compatibility.md
│   └── <future pages>
└── SKILL.md              # Reserved for future skill system
```

## Raw Sources Table

| Source | Description | Last Updated |
|--------|-------------|--------------|
| `docs/foundation/aria_foundation_blueprint.md` | Primary technical reference (blueprint §1-16) | 2026-04-20 |
| `docs/analysis/research_agent_enhancement.md` | Analisi pre-implementazione 4 nuovi provider | 2026-04-27 |
| `docs/plans/research_academic_reddit_1.md` | Piano espansione v1 (SUPERSEDED da v2) | 2026-04-27 |
| `docs/plans/research_academic_reddit_2.md` | **Piano espansione v2 audit-corrected**: PubMed, scientific-papers (Europe PMC + arXiv), Reddit OAuth | 2026-04-27 |
| `docs/foundation/decisions/ADR-0006-research-agent-academic-social-expansion.md` | ADR divergence blueprint §11 | 2026-04-27 |
| `scripts/wrappers/pubmed-wrapper.sh` | PubMed MCP wrapper (CredentialManager + SOPS) | 2026-04-27 |
| `scripts/wrappers/scientific-papers-wrapper.sh` | Scientific Papers MCP wrapper (keyless) | 2026-04-27 |
| `scripts/wrappers/reddit-wrapper.sh` | Reddit MCP wrapper (OAuth via CredentialManager) | 2026-04-27 |
| `tests/unit/agents/search/test_provider_pubmed.py` | Test: PubMed enum, tier, health | 2026-04-27 |
| `tests/unit/agents/search/test_provider_scientific_papers.py` | Test: Scientific Papers enum, keyless | 2026-04-27 |
| `tests/unit/agents/search/test_provider_reddit.py` | Test: Reddit enum, SOCIAL tier | 2026-04-27 |
| `tests/unit/agents/search/test_intent_social.py` | Test: SOCIAL intent classification | 2026-04-27 |
| `tests/unit/agents/search/test_router_academic_tiers.py` | Test: ACADEMIC tier ordering, fallback | 2026-04-27 |
| `tests/unit/agents/search/test_router_social_tiers.py` | Test: SOCIAL tier ordering, Reddit DOWN | 2026-04-27 |
| `docs/plans/rispristino_agenti_ricerca_google.md` | Piano ripristino multi-fase (RC-1..RC-9) | 2026-04-27 |
| `docs/plans/auto_persistence_echo.md` | Memory v3: Kilo+Wiki Fusion | 2026-04-27 |
| `docs/plans/research_restore_plan.md` | Research routing restore plan | 2026-04-26 |
| `docs/plans/memory_recovery.md` | Memory recovery plan | 2026-04-26 |
| `.aria/kilocode/mcp.json` | MCP server runtime config (12 server) | 2026-04-27 |
| `.aria/credentials/secrets/api-keys.enc.yaml` | SOPS+age YAML credential store | 2026-04-27 |
| `.aria/runtime/credentials/providers_state.enc.yaml` | Rotator runtime state (SOPS) | 2026-04-27 |
| `.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json` | Google OAuth token (write scopes) | 2026-04-27 |
| `bin/aria` | ARIA launcher (hard isolation, MCP migration) | 2026-04-27 |
| `scripts/wrappers/tavily-wrapper.sh` | Tavily MCP wrapper | 2026-04-27 |

| `scripts/wrappers/exa-wrapper.sh` | Exa MCP wrapper | 2026-04-27 |
| `scripts/wrappers/searxng-wrapper.sh` | SearXNG MCP wrapper (auto-detect Docker 8888) | 2026-04-27 |
| `scripts/wrappers/brave-wrapper.sh` | Brave MCP wrapper (env normalize + auto-acquire) | 2026-04-27 |
| `scripts/wrappers/google-workspace-wrapper.sh` | GWS MCP wrapper v2 (single-user, gmail/calendar) | 2026-04-27 |
| `scripts/oauth_first_setup.py` | PKCE verifier/challenge generators | 2026-04-24 |
| `scripts/oauth_exchange.py` | Self-contained OAuth PKCE flow + token exchange | 2026-04-27 |
| `scripts/workspace_auth.py` | OAuth scope verification | 2026-04-24 |
| `src/aria/credentials/manager.py` | CredentialManager facade | 2026-04-27 |
| `src/aria/credentials/rotator.py` | Rotator: circuit breaker, rotation strategies | 2026-04-27 |
| `src/aria/credentials/sops.py` | SOPS adapter (encrypt/decrypt YAML) | 2026-04-27 |
| `src/aria/credentials/keyring_store.py` | KeyringStore (OS keyring + age fallback) | 2026-04-27 |
| `src/aria/agents/search/router.py` | ResearchRouter: tier routing, fallback, health | 2026-04-26 |
| `src/aria/agents/search/intent.py` | Intent classifier (keyword-based) | 2026-04-26 |
| `src/aria/memory/wiki/db.py` | WikiStore (wiki.db CRUD, FTS5) | 2026-04-27 |
| `src/aria/memory/wiki/tools.py` | MCP tools: wiki_update, wiki_recall, wiki_show, wiki_list | 2026-04-27 |
| `src/aria/memory/wiki/prompt_inject.py` | Profile auto-inject in conductor template | 2026-04-27 |
| `src/aria/memory/wiki/kilo_reader.py` | Kilo.db read-only reader | 2026-04-27 |
| `src/aria/memory/wiki/watchdog.py` | Gap detection + catch-up | 2026-04-27 |
| `src/aria/gateway/conductor_bridge.py` | Gateway: post-session CLM hook, HITL | 2026-04-24 |
| `.aria/kilocode/agents/search-agent.md` | Search agent prompt (tier ladder esplicito) | 2026-04-27 |
| `.aria/kilocode/skills/deep-research/SKILL.md` | Deep research skill (tier ladder) | 2026-04-27 |
| `.sops.yaml` | SOPS config (age key, encrypted_regex) | 2026-04-20 |

## Pages

| Page | Description | Status |
|------|-------------|--------|
| [[memory-subsystem]] | Memory subsystem: 5D model, 11 MCP tools, HITL flow, CLM, retention | Active |
| [[memory-v3]] | Memory v3 Kilo+Wiki Fusion: wiki.db, 4 wiki MCP tools, profile auto-inject | Active |
| [[research-routing]] | **Ricerca multi-tier**: 6 provider attivi (searxng, tavily, exa, brave, pubmed, scientific-papers) + reddit (OAuth gated) + SOCIAL intent | Active ✅ v2 Implemented |
| [[google-workspace-mcp-write-reliability]] | GWS MCP: **write scopes concessi**, single-user, Gmail/Calendar, 10 scopes | Active ✅ Write-enabled |
| [[mcp-api-key-operations]] | **Runbook**: 5 provider, 17 keys, multi-account rotation, circuit breaker | Active ✅ Restored |
| [[aria-launcher-cli-compatibility]] | bin/aria launcher: CLI invocation, hard isolation, MCP migration | Active (Fixed v2) |
| [[log]] | Implementation log with timestamps | Active |

## Implementation Branch

- **Branch**: `feature/research-academic-social-v2`
- **Commit finale**: `1eeec32` (2026-04-27T17:28) — feat(search): add academic+social provider expansion
- **ADR**: `ADR-0006-research-agent-academic-social-expansion.md` (status: Accepted)
- **Status**: ✅ **ESPANSIONE V2 COMPLETA** — 6 provider ricerca + 3 MCP nuovi
  - Memory v3: profile persists, wiki_recall, 4 wiki MCP tools, watchdog, Phase E pending
  - Ricerca multi-tier: 6 provider (searxng > tavily > exa > brave > pubmed > scientific_papers)
  - `Intent.SOCIAL`: nuovo intent per social (reddit > searxng > tavily > brave)
    - Reddit: **OAuth required** — HITL gate per setup (vedi research-routing.md)
  - PubMed MCP: 9 tool, NCBI_API_KEY opzionale via CredentialManager
  - Scientific Papers MCP: keyless, 6 sorgenti (arXiv, Europe PMC, OpenAlex, etc.)
  - ADR-0006 accettato (P10 compliance: blueprint §11 divergence registrata)
  - Google Workspace: write scopes (10), single-user, Gmail/Calendar abilitato
  - **Performance**: review 66s→~5s (gitignore + resolve_kilo_cli fix)
- **Phase E pending**: Hard delete frozen memory modules after 30 days

## Bootstrap Log

- 2026-04-24: Wiki bootstrapped during memory gap remediation Sprint 1.2
- 2026-04-24: Added Google Workspace MCP write reliability page
- 2026-04-27: Comprehensive update after ripristino ricerca + Google Workspace

## Git & GitHub Rules

Definite in `AGENTS.md` § "Git & GitHub Workflow Rules". Regole chiave:
- **MAI** forzare push su `main` senza HITL
- **MAI** usare `git filter-branch` / `filter-repo` senza backup e approvazione
- **MAI** committare segreti in chiaro; bypassare push protection per credenziali documentate tramite URL GitHub dedicati
- **SEMPRE** tenere il working tree pulito: meno di 10 untracked files prima di iniziare un task
- **SEMPRE** fare backup del branch (`git branch <branch>-backup`) prima di operazioni distruttive
- **Stash** come strumento di recovery primario: `git stash --include-untracked` prima di rebase/merge/filter

## Relevant Files

- `AGENTS.md` — coding standards and agent rules
- `docs/llm_wiki/wiki/research-routing.md` — tier policy (searxng > tavily > exa > brave > fetch)
