# ARIA LLM Wiki — Index

**Last Updated**: 2026-04-30T19:30 (v4.9 — Stabilizzazione: F0 completa, main consolidato)
**Status**: ✅ **v4.9** — Stabilizzazione ARIA pre-Fase 2: F0 completata. Productivity-agent-mvp merged in `main`. Wiki title field fix merged. Quality gate: ruff 0, mypy 0, pytest 548/548. Baseline LKG tag pending.

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
│   ├── productivity-agent.md
│   ├── mcp-architecture.md
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
| `scripts/wrappers/scientific-papers-wrapper.sh` | Scientific Papers MCP wrapper (keyless, auto-patching) | 2026-04-29 |
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
| `.aria/kilocode/mcp.json` | MCP server runtime config (**16 server dichiarati / 15 abilitati** osservati durante l'audit refoundation) | 2026-04-29 |
| `.aria/credentials/secrets/api-keys.enc.yaml` | SOPS+age YAML credential store | 2026-04-27 |
| `.aria/runtime/credentials/providers_state.enc.yaml` | Rotator runtime state (SOPS) | 2026-04-27 |
| `.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json` | Google OAuth token (write scopes) | 2026-04-27 |
| `bin/aria` | ARIA launcher (hard isolation, MCP migration) | 2026-04-27 |
| `scripts/wrappers/tavily-wrapper.sh` | Tavily MCP wrapper | 2026-04-27 |
| `docs/analysis/report_gemme_reddit_mcp.md` | **Report github-discovery**: Reddit MCP keyless alternatives (eliasbiondo, adhikasp, cmpxchg16) | 2026-04-29 |
| `docs/plans/agents/productivity_agent_plan_draf_1.md` | **Draft 2** (revisione austera): `productivity-agent` MVP, gate no-bloat MCP, 13 open questions | 2026-04-29 |
| `docs/analysis/ricerca_mcp_produttività.md` | **Report github-discovery**: 40+ MCP server per produttività AI (Word, Calendar, Task, Knowledge, M365, Email) — hidden gems classificate | 2026-04-29 |
| `docs/analysis/analisi_sostenibilita_mcp_report.md` | **Report sostenibilità MCP**: 10 pattern di scaling, architettura ibrida 4 livelli, GitHub ecosystem, roadmap implementativa per sistemi con 50+ MCP server e decine di agenti | 2026-04-29 |
| `docs/analysis/mcp_gateway_evaluation.md` | **Gateway evaluation**: metriche startup/latency reali (9 server), conclusione gateway NON giustificato, raccomandazione lazy loading per intent | 2026-04-29 |
| `scripts/benchmarks/mcp_startup_latency.py` | **Benchmark tool**: misura cold/warm start + tools/list per MCP server. Output markdown/JSON. | 2026-04-29 |
| `docs/plans/gestione_mcp_refoundation_plan.md` | **Piano di refoundation MCP**: inventory authority, eliminazione drift, catalogo canonico, ottimizzazione misurata e gateway selettivo | 2026-04-29 |
| `docs/plans/gestione_mcp_refoundation_plan_v2.md` | **Piano di refoundation MCP v2**: rollback-first, baseline LKG, profili baseline/candidate/shadow, cutover gates e rollback matrix | 2026-04-29 |
| `docs/plans/mcp_productivity_coordination_optimization_plan_2026-04-29.md` | **Piano ottimizzazione coordinamento agenti + MCP accademici**: fix esposizione pubmed/scientific, integrazione productivity-agent nel conductor, hardening wrapper, capability matrix cross-agent | 2026-04-29 |
| `docs/foundation/agent-capability-matrix.md` | **Capability Matrix canonica**: tool per agente, MCP deps, handoff protocol, routing policy unificata. pubmed-mcp rimosso 2026-04-30. | 2026-04-30 |
| `tests/unit/agents/search/test_config_consistency.py` | **22 test**: verifica allineamento YAML search-agent ↔ router Python | 2026-04-29 |
| `tests/unit/agents/test_conductor_dispatch.py` | **12 test**: conductor sub-agent registry, handoff protocol, YAML config | 2026-04-29 |
| `src/aria/agents/search/capability_probe.py` | **Capability probe framework**: initialize + tools/list MCP probe, snapshot, quarantine | 2026-04-29 |
| `tests/unit/agents/search/test_capability_probe.py` | **12 test**: snapshot integrity, quarantine logic, ProbeResult | 2026-04-29 |
| `src/aria/agents/search/query_preprocessor.py` | **Query preprocessor centralizzato**: regole formatting per 7 sorgenti accademiche, BUG 1/2/3 fix | 2026-04-29 |
| `tests/unit/agents/search/test_query_preprocessor.py` | **26 test**: arXiv Boolean AND, EuropePMC sort fix, tutte le sorgenti | 2026-04-29 |
| `tests/integration/agents/search/test_academic_smoke.py` | **Smoke E2E**: 16 test su fallback chain, intent classification, preprocessor, snapshot | 2026-04-29 |
| `scripts/rollback_baseline.sh` | **Rollback drill**: restore baseline profile da git in <5 min, backup + verify | 2026-04-29 |
| `docs/plans/agents/productivity_agent_foundation_plan.md` | **Piano implementazione approvato**: productivity-agent MVP, 13 Q&A utente, architecture 2-hop, markitdown-mcp | 2026-04-29 |
| `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md` | **ADR-0008**: productivity-agent austere MVP, Context7 verified: /microsoft/markitdown Bench 90.05 | 2026-04-29 |
| `.aria/kilocode/agents/productivity-agent.md` | **Agent definition**: 11 tool, 4 skill, boundary delega workspace-agent | 2026-04-29 |
| `.aria/kilocode/skills/office-ingest/SKILL.md` | **Skill office-ingest@2.0.0**: office file → markdown via markitdown-mcp, deprecates pdf-extract | 2026-04-29 |
| `.aria/kilocode/skills/consultancy-brief/SKILL.md` | **Skill consultancy-brief@1.0.0**: multi-doc executive summary | 2026-04-29 |
| `.aria/kilocode/skills/meeting-prep/SKILL.md` | **Skill meeting-prep@1.0.0**: calendar event-driven meeting briefings | 2026-04-29 |
| `src/aria/agents/productivity/ingest.py` | **Ingest module**: detect_format, hash_file, parse_markitdown_output, IngestResult | 2026-04-29 |
| `src/aria/agents/productivity/synthesizer.py` | **Synthesizer module**: compose_brief, BriefOutline, render_markdown | 2026-04-29 |
| `src/aria/agents/productivity/meeting_prep.py` | **Meeting Prep module**: MeetingBrief, build_meeting_brief, workspace delegate mock | 2026-04-29 |
| `tests/unit/agents/productivity/test_ingest.py` | **25 unit tests**: format detection, hashing, yaml parsing, IngestResult | 2026-04-29 |
| `tests/unit/agents/productivity/test_synthesizer.py` | **10 unit tests**: brief composition, wiki context, rendering | 2026-04-29 |
| `tests/unit/agents/productivity/test_meeting_prep.py` | **14 unit tests**: event parsing, participant truncation, build/render flow | 2026-04-29 |
| `tests/integration/productivity/test_office_ingest_mcp.py` | **13 integration tests**: E2E with real markitdown-mcp subprocess | 2026-04-29 |
| `tests/fixtures/office_files/` | **5 fixture files**: PDF, DOCX, XLSX, PPTX, TXT | 2026-04-29 |
| `.aria/kilocode/skills/email-draft/SKILL.md` | **Skill email-draft@1.0.0** (Sprint 2): bozze email con stile dinamico (Q7), nessuna lesson statica | 2026-04-29 |
| `src/aria/agents/productivity/email_style.py` | **Email style module** (Sprint 2): derive_style, draft_email, StyleProfile, style extraction helpers | 2026-04-29 |
| `tests/unit/agents/productivity/test_email_style.py` | **33 unit tests** (Sprint 2): style extraction, profile building, drafting | 2026-04-29 |
| `tests/integration/productivity/test_email_draft_e2e.py` | **5 E2E tests** (Sprint 2): mock workspace-agent, formal/cordial style, draft creation flow | 2026-04-29 |

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
| `.aria/kilocode/agents/search-agent.md` | **v4.0**: tool pubmed-mcp/* e scientific-papers-mcp/* aggiunti a allowed-tools e mcp-dependencies | 2026-04-29 |
| `.aria/kilocode/agents/aria-conductor.md` | **v4.0**: productivity-agent aggiunto ai sub-agenti con regole dispatch | 2026-04-29 |
 | ~~`scripts/wrappers/pubmed-wrapper.sh`~~ | **RIMOSSO 2026-04-30**: scientific-papers-mcp copre PubMed via source="europepmc" | 2026-04-30 |
 | `src/aria/memory/wiki/schema.py` | **v4.6**: `_validate_title_on_create` fix (P1) — ora logga warning su create+no title con ValidationInfo | 2026-04-30 |
 | `src/aria/memory/wiki/db.py` | **v4.6**: auto-estrazione title da body_md heading Markdown (P2) — fallback robusto | 2026-04-30 |
 | `.aria/kilocode/agents/aria-conductor.md` | **v4.6**: colonna `title` in Regole per patch + nota auto-estrazione (P0) | 2026-04-30 |
 | `.aria/kilo-home/.kilo/agents/_aria-conductor.template.md` | **v4.6**: stesso fix P0 del conductor attivo | 2026-04-30 |
| `scripts/wrappers/scientific-papers-wrapper.sh` | **v4.0**: checksum guard, version pin 0.1.40, hard fail diagnostico | 2026-04-29 |
| `docs/patches/scientific-papers-mcp/MANIFEST.md` | **v4.0**: checksum manifest + update procedure | 2026-04-29 |
| `.aria/kilocode/skills/deep-research/SKILL.md` | Deep research skill (tier ladder) | 2026-04-27 |
| `.sops.yaml` | SOPS config (age key, encrypted_regex) | 2026-04-20 |

## Pages

| Page | Description | Status |
|------|-------------|--------|
| [[memory-subsystem]] | Memory subsystem: 5D model, 11 MCP tools, HITL flow, CLM, retention | Active |
| [[memory-v3]] | Memory v3 Kilo+Wiki Fusion: wiki.db, 4 wiki MCP tools, profile auto-inject | Active |
| [[research-routing]] | **Ricerca multi-tier**: 9 tool pubmed-mcp + 5 tool scientific-papers-mcp esposti in search-agent; policy fully alignata v4.0 | Active ✅ v4.0 |
| [[google-workspace-mcp-write-reliability]] | GWS MCP: **write scopes concessi**, single-user, Gmail/Calendar, 10 scopes | Active ✅ Write-enabled |
| [[mcp-api-key-operations]] | **Runbook**: 5 provider, 17 keys, multi-account rotation, circuit breaker | Active ✅ Restored |
| [[aria-launcher-cli-compatibility]] | bin/aria launcher: CLI invocation, hard isolation, MCP migration | Active (Fixed v2) |
| [[mcp-architecture]] | Inventario MCP reale, drift strutturali e direzione di refoundation con baseline/candidate/fallback path | Active ✅ v2 |
| [[agent-capability-matrix]] | Capability matrix, handoff protocol e routing policy unificata per i 3 agenti | Active ✅ v1.0 |
| [[log]] | Implementation log with timestamps | Active |

## Implementation Branch

- **Branch**: `feature/research-academic-social-v2`
- **Commit finale**: `1eeec32` (2026-04-27T17:28) — feat(search): add academic+social provider expansion
- **ADR**: `ADR-0006-research-agent-academic-social-expansion.md` (status: Accepted)
- **Status**: ✅ **ESPANSIONE V2 COMPLETA** — 6 provider ricerca + 3 MCP nuovi
  - Memory v3: profile persists, wiki_recall, 4 wiki MCP tools, watchdog, Phase E pending
  - Ricerca multi-tier: 6 provider (searxng > tavily > exa > brave > pubmed > scientific_papers)
  - `Intent.SOCIAL`: nuovo intent per social (reddit > searxng > tavily > brave)
    - Reddit: **KEYLESS ATTIVA v3** — `eliasbiondo/reddit-mcp-server` (6 tool, PyPI `reddit-no-auth-mcp-server`) — OAuth wrapper rimosso, `KEYLESS_PROVIDERS` aggiornato
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
- 2026-04-29: v3.1 — Scientific Papers MCP query formulation fix (3 npm bugs: arXiv quote-wrapping, EuropePMC sort + hasFullText, centralized preprocessor)
- 2026-04-29: v3.4 — MCP refoundation plan + mcp-architecture wiki page added after current-state audit and external verification
- 2026-04-29: v3.6 — MCP refoundation plan v2 adds rollback-first discipline, LKG baseline, and cutover/fallback model
- 2026-04-29: piano dedicato su failure `pubmed/scientific` + coordinamento search/workspace/productivity con remediation roadmap e gate operativi
- 2026-04-29: **v4.0** — Implementazione Fase A+B del piano: search-agent exposure fix, conductor+productivity-agent, wrapper hardening con checksum/version pin, MANIFEST.md
- 2026-04-29: **v4.1** — Fase C+D: capability matrix canonica, handoff protocol, routing policy, 34 nuovi test di coerenza configurativa e dispatch
- 2026-04-29: **v4.2** — Fase P2: benchmark startup/latency per 9 MCP server (6.5s cold, 6.1s warm, 49 tools totali). Gateway search: NON giustificato. Alternativa: lazy loading per intent.
- 2026-04-29: **v4.3** — PIANO COMPLETO: B-2 capability probe framework, B-3 query preprocessor centralizzato (7 sorgenti), D-2 smoke E2E academic (16 test), D-3 rollback drill script. 203 test totali.
- 2026-04-30: **v4.4** — pubmed-mcp fix: bunx→npx (stdio reliable), npm v0.1.0→v2.6.6 tool mapping, 9 tool rimpiazzati da 5 nuovi. Cache bunx stale pulita.
  - 2026-04-30: **v4.5** — pubmed-mcp RIMOSSO. Non risolveva startup failure. Sostituito da scientific-papers-mcp/source="europepmc". 2 file cancellati, 9 modificati. 182 test.
  - 2026-04-30: **v4.6** — FIX: wiki_update_tool title field BUG (P0+P1+P2). Prompt aggiornato, validatore Pydantic implementato, auto-extraction `# Heading` da body_md. 146 wiki test pass.

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
