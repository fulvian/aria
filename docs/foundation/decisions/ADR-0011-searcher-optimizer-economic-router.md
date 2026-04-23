# ADR-0011: Searcher Optimizer — Free-First Economic Router

**Status**: Approved
**Date**: 2026-04-23
**Deciders**: ARIA technical lead
**References**: `docs/plans/searcher_optimizer_plan.md`

## Context

The ARIA search-agent routes queries to multiple search providers (SearXNG, Brave, Tavily, Exa, Firecrawl, SerpAPI). Before this ADR:

1. **No cost-aware policy**: Provider selection used intent-based routing without considering marginal cost or quota exhaustion.
2. **Routing misalignment**: `schema.py` INTENT_ROUTING for GENERAL used `brave → tavily` (both paid), while the search-agent doc promoted Exa as primary.
3. **No quality gates**: The router returned whatever results providers gave, with no evaluation of result sufficiency before escalating to more expensive providers.
4. **No result fusion**: When multiple providers returned results, the router simply concatenated and deduplicated — no score-based fusion across heterogeneous providers.
5. **No telemetry**: No structured metrics on cost/quality/provider outcomes for continuous optimization.

## Decision

Implement a **Free-First Economic Router** with the following architecture:

### 1. Cost Tier Classification (`cost_policy.py`)

- **Tier A** (free-unlimited): SearXNG — self-hosted, zero marginal cost.
- **Tier B** (free-limited): Brave, Tavily, Exa — monthly free credits (1000/month each).
- **Tier C** (costly extraction): Firecrawl — per-page pricing, limited credits.
- **Tier D** (paid fallback): SerpAPI — $25/1k searches, 250/month free.

### 2. Tiered Routing with Quality Gates (`quality_gate.py`)

- Execute Tier A first (SearXNG for general/privacy/news).
- Evaluate quality gates: unique results, distinct domains, recency ratio, top-3 score mean.
- If quality sufficient → return results (no paid provider used).
- If quality insufficient → escalate to Tier B, then C/D.

### 3. Budget Enforcement (`quota_state.py`)

- Per-provider daily and monthly credit tracking.
- `QueryBudget` per query: max credits, max tier.
- Reserve mode: preserve expensive providers for high-value intents.

### 4. Reciprocal Rank Fusion (`fusion.py`)

- When multiple providers contribute, apply RRF: `score(d) = Σ 1/(k + rank_i(d))`.
- Parameters: `rank_constant = 60` (industry baseline), `window_size = 40`.
- RRF chosen over score fusion because provider scores are heterogeneous and incomparable.

### 5. Telemetry (`telemetry.py`)

- Structured events: provider, outcome, credits, latency, tier, escalation.
- KPIs: paid_calls_ratio, avg_credit_cost_per_query, quality_pass_rate_first_tier, fallback_success_rate.

### 6. Updated Routing Table (`schema.py`)

INTENT_ROUTING reordered to free-first:
- GENERAL: `searxng → brave → exa → tavily`
- NEWS: `searxng → tavily → brave_news → exa`
- ACADEMIC: `exa → tavily → searxng` (Exa primary for semantic quality)

## Consequences

### Positive

- **Cost reduction**: Target -40% paid_calls_ratio and -35% avg_credit_cost_per_query.
- **Quality maintenance**: Quality gates ensure paid escalation only when free results insufficient.
- **Observability**: Telemetry enables data-driven optimization of thresholds and provider economics.
- **Extensibility**: New providers easily classified into tiers with cost profiles.

### Negative

- **Latency**: Quality gate evaluation adds minimal overhead (~0ms, in-memory computation).
- **Complexity**: 5 new modules increase the search subsystem surface area.
- **Threshold tuning**: Quality gate thresholds may need periodic adjustment based on real query patterns.

### Mitigations

- All new modules have comprehensive unit tests (52 tests).
- Telemetry provides the data needed for threshold auto-tuning (Phase 3 of the plan).
- RRF parameters are configurable without code changes.
