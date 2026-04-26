# ARIA LLM Wiki — Index

**Last Updated**: 2026-04-26
**Status**: BOOTSTRAPPED — memory recovery applied

## Purpose

This wiki is the single source of project knowledge for LLMs working in this repository. Per AGENTS.md, all meaningful changes must update the wiki.

## Wiki Structure

```
docs/llm_wiki/
├── ext_knowledge/          # Raw extracted sources (external docs)
│   └── README.md
├── wiki/                  # Synthesized knowledge
│   ├── index.md          # This file - wiki overview
│   ├── log.md            # Implementation log
│   └── memory-subsystem.md  # Memory subsystem reference
└── SKILL.md              # Reserved for future skill system
```

## Raw Sources Table

| Source | Description | Last Updated |
|--------|-------------|--------------|
| `docs/foundation/aria_foundation_blueprint.md` | Primary technical reference | 2026-04-20 |
| `docs/plans/memory_gaps_remediation_plan_2026-04-24.md` | Memory gap remediation plan | 2026-04-24 |
| `src/aria/memory/episodic.py` | EpisodicStore implementation | varies |
| `src/aria/memory/mcp_server.py` | MCP server with 11 tools | varies |
| `src/aria/gateway/conductor_bridge.py` | Gateway conductor bridge | 2026-04-24 |
| `src/aria/gateway/daemon.py` | Gateway daemon | 2026-04-24 |
| `.aria/kilocode/mcp.json` | MCP server runtime configuration | 2026-04-24 |
| `docs/handoff/mcp_google_workspace_oauth_handoff.md` | OAuth callback failure handoff | 2026-04-21 |
| `.aria/kilo-home/.google_workspace_mcp/logs/mcp_server_debug.log` | Runtime MCP auth/tool logs | 2026-04-24 |
| `docs/implementation/workspace-write-reliability/baseline-inventory.md` | Phase 0 baseline inventory | 2026-04-24 |
| `scripts/oauth_first_setup.py` | PKCE utilities | 2026-04-24 |
| `scripts/workspace_auth.py` | OAuth scope verification | 2026-04-24 |
| `scripts/workspace-write-health.py` | Health check CLI | 2026-04-24 |
| `scripts/wrappers/google-workspace-wrapper.sh` | MCP wrapper | 2026-04-24 |
| `scripts/wrappers/firecrawl-wrapper.sh` | Firecrawl MCP compatibility wrapper | 2026-04-25 |
| `scripts/wrappers/searxng-wrapper.sh` | SearXNG MCP wrapper with env fallback | 2026-04-25 |
| `bin/aria` | ARIA launcher with hard runtime isolation + CLI compatibility | 2026-04-25 |
| `docs/plans/research_restore_plan.md` | Piano di ripristino routing ricerca con tier consecutivi e policy free-first | 2026-04-26 |
| `docs/plans/research_restore_plan.md` | Ricerca deterministica: searxng > tavily > firecrawl > exa > brave (approved 2026-04-26) | 2026-04-26 |
| `docs/plans/memory_recovery.md` | Piano di recupero memoria (auto-persistence, VACUUM safety, CLM inclusivo) | 2026-04-26 |

## Pages

| Page | Description | Status |
|------|-------------|--------|
| [[memory-subsystem]] | Memory subsystem architecture, gaps, tools (updated 2026-04-24) | Active |
| [[google-workspace-mcp-write-reliability]] | Root causes and remediation for Docs/Sheets/Slides write path | Active |
| [[aria-launcher-cli-compatibility]] | Root cause and robust fix for startup, isolation, and MCP restoration | Active |
| [[research-routing]] | Research routing tier policy: searxng > tavily > firecrawl > exa > brave | Active |
| [[log]] | Implementation log with timestamps | Active |

## Bootstrap Log

- 2026-04-24: Wiki bootstrapped during memory gap remediation Sprint 1.2
- Prior to bootstrap, wiki directory existed but was empty (only `.obsidian/`)
- 2026-04-24: Added Google Workspace MCP write reliability page and remediation plan provenance

## Implementation Branch

- **Branch**: `feature/workspace-write-reliability`
- **Status**: Launcher isolation + research MCP restoration validated (2026-04-25)
- **Focus**: ARIA runtime isolation + CLI compatibility hardening

## Relevant Files

- `AGENTS.md` — coding standards and agent rules
- `CLAUDE.md` — KiloCode context file
