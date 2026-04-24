# ARIA LLM Wiki — Index

**Last Updated**: 2026-04-24
**Status**: BOOTSTRAPPED

## Purpose

This wiki is the single source of project knowledge for LLMs working in this repository. Per AGENTS.md, all meaningful changes must update the wiki.

## Wiki Structure

```
docs/llm_wiki/
├── ext_knowledge/          # Raw extracted sources (external docs)
│   └── (empty - bootstrap pending)
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

## Pages

| Page | Description | Status |
|------|-------------|--------|
| [[memory-subsystem]] | Memory subsystem architecture, gaps, tools (updated 2026-04-24) | Active |
| [[log]] | Implementation log with timestamps | Active |

## Bootstrap Log

- 2026-04-24: Wiki bootstrapped during memory gap remediation Sprint 1.2
- Prior to bootstrap, wiki directory existed but was empty (only `.obsidian/`)

## Relevant Files

- `AGENTS.md` — coding standards and agent rules
- `CLAUDE.md` — KiloCode context file