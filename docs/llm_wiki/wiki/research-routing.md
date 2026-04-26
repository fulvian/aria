# Research Routing — Tier Policy

**Last Updated**: 2026-04-26
**Status**: APPROVED — Single Source of Truth

## Purpose

This page documents the canonical provider routing policy for research operations. All references (blueprint, skill, agent, code) must align with this policy. Per `docs/plans/research_restore_plan.md`, policy drift is the root cause of routing inconsistencies.

## Provider Tier Matrix

| Intent | Tier 1 | Tier 2 | Tier 3 | Tier 4 | Tier 5 |
|--------|--------|--------|--------|--------|--------|
| `general/news` | **searxng** | **tavily** | **firecrawl** | **exa** | **brave** |
| `academic` | **searxng** | **tavily** | **firecrawl** | **exa** | **brave** |
| `deep_scrape` | **firecrawl_extract** | **firecrawl_scrape** | **fetch** | — | — |

### Tier Definitions

| Provider | Type | Key Required | Cost | Notes |
|----------|------|--------------|------|-------|
| `searxng` | Self-hosted meta-search | No | Zero (infra only) | Always tier 1; privacy-first |
| `tavily` | Commercial LLM-ready API | Yes | 1000 req/mo free, then $0.008/req | Tier 2 commercial |
| `firecrawl` | Commercial scraping API | Yes | 500 credits lifetime, then ~$0.005-0.015/page | Tier 3; `extract`/`scrape` specialized |
| `exa` | Commercial semantic search | Yes | 1000 req/mo free, then $0.007/req | Tier 4 academic |
| `brave` | Commercial search API | Yes | $5/mo free credits | Tier 5 fallback |

### Rationale

Order follows "real API key availability to rotate" principle:
1. **SearXNG** — self-hosted, unlimited, no API key required; always attempted first
2. **Tavily** — has free tier, LLM-ready synthesis
3. **Firecrawl** — credits exhausted quickly (500 lifetime); specialized for deep scrape
4. **Exa** — good for academic/semantic search
5. **Brave** — last fallback (has $5/mo free but lower priority for rotation)

## Implementation

**File**: `src/aria/agents/search/router.py` (planned, not yet implemented as of 2026-04-26)

### Fallback Behavior

When a provider fails with classified reason, the router advances to next tier consecutively:

| Failure Reason | Action |
|----------------|--------|
| `rate_limit` | Skip to next tier; log `provider_skipped` |
| `credits_exhausted` | Skip to next tier; mark provider exhausted |
| `circuit_open` | Skip to next tier; log circuit breaker state |
| `timeout` | Retry once, then fallback to next tier |
| `network_error` | Retry once, then fallback to next tier |

### Degraded Mode

If all tiers fail, the router enters `local-only` mode:
- Return cached results with `degraded` banner
- Log `degraded_mode_entered` event
- Notify via system_event

## Alignment Sources

| Source | Location | Alignment Status |
|--------|----------|------------------|
| Blueprint routing | `docs/foundation/aria_foundation_blueprint.md` §11.2 | ✅ Aligned (2026-04-26) |
| Blueprint fallback | `docs/foundation/aria_foundation_blueprint.md` §11.6 | ✅ Aligned (2026-04-26) |
| Search-Agent | `.aria/kilocode/agents/search-agent.md` | ✅ Aligned (2026-04-26) |
| Deep-Research Skill | `.aria/kilocode/skills/deep-research/SKILL.md` | ✅ Aligned (2026-04-26) |
| MCP config | `.aria/kilocode/mcp.json` | ✅ Aligned (SearXNG present) |

## Removed Providers

| Provider | Reason |
|----------|--------|
| `serpapi` | Not in `mcp.json`; redundant with defined fallback chain |

## Verification Matrix

1. `general/news`: tier 1 healthy → uses searxng, no fallback
2. `general/news`: tier 1 quota exhausted → fallback to tavily (tier 2)
3. `general/news`: tier 1+2 down → fallback to firecrawl (tier 3)
4. `deep_scrape`: firecrawl_extract failure → fallback to firecrawl_scrape (tier 2)
5. `deep_scrape`: firecrawl_scrape failure → fallback to fetch (tier 3)
6. All providers unavailable → explicit `local-only/degraded` response

## SerpAPI Decision

**SerpAPI removed from blueprint** (2026-04-26). Rationale:
- Not present in `mcp.json` (not configured as MCP server)
- Redundant with the defined 5-tier fallback chain
- If all 5 tiers fail, degraded mode is more appropriate than adding another commercial provider