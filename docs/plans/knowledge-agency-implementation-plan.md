# Knowledge Agency Implementation Plan

**Date**: 2026-03-30  
**Status**: Proposed (Ready for implementation)  
**Blueprint Reference**: `docs/foundation/BLUEPRINT.md` §7.1 (Knowledge Agency), §2.2.2 (Agency), §2.2.4 (Skill), §3.x (Memory)

---

## 1) Executive Summary

The Knowledge Agency will provide ARIA with robust research, learning, and general analysis capabilities through three specialized agents (`researcher`, `educator`, `analyst`) implemented with the same architecture used by Weather/Nutrition agencies:

- **Agency-centric execution** (`internal/aria/agency/knowledge.go`)
- **Bridge pattern per agent capability** (task → skill parameters → skill execution)
- **Skill modules in `internal/aria/skill/`**
- **Provider abstraction with fallback chain** (Tavily primary, Brave secondary, Wikipedia direct for encyclopedic grounding)
- **Observability via per-provider + per-skill metrics**
- **Memory embedding integration** for semantic retrieval and knowledge continuity

Implementation is phased (K1→K4) to minimize risk and allow progressive value delivery.

---

## 2) Architecture Design

### 2.1 Agency Structure

> Pattern aligned with `internal/aria/agency/nutrition.go` and `internal/aria/agency/weather.go`

```text
internal/aria/
├── agency/
│   ├── knowledge.go
│   └── knowledge/
│       ├── metrics/
│       │   └── metrics.go
│       └── providers/
│           ├── search_provider.go
│           ├── tavily.go
│           ├── brave.go
│           └── wikipedia.go
├── config/
│   └── knowledge.go
└── skill/
    ├── web_research.go
    ├── document_analysis.go
    ├── fact_check.go
    ├── summarization.go
    ├── simplification.go
    ├── examples.go
    ├── data_analysis.go
    ├── comparison.go
    └── synthesis.go

internal/app/
└── aria_integration.go (wire agency)
```

### 2.2 Agents Detail

#### A) `researcher`
- **Responsibilities**:
  - deep topic research
  - source collection and extraction
  - fact verification against multiple sources
- **Skills**: `web-research`, `document-analysis`, `fact-check`
- **Bridge interface**:

```go
type ResearchBridge interface {
    ConductResearch(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}
```

- **Routing logic**:
  - explicit skill in `task.Skills[0]` wins
  - fallback by task name/pattern: `research`, `find`, `investigate`, `verify`
  - if no clear skill: default `web-research`

#### B) `educator`
- **Responsibilities**:
  - explain concepts with variable depth
  - generate simplified explanations and examples
  - produce didactic summaries
- **Skills**: `summarization`, `simplification`, `examples`
- **Bridge interface**:

```go
type EducationBridge interface {
    Teach(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}
```

- **Routing logic**:
  - intents `IntentQuestion`, `IntentLearning`
  - keywords: `explain`, `teach`, `simple`, `example`, `learn`
  - default `summarization` when input is long content, `simplification` for conceptual prompts

#### C) `analyst`
- **Responsibilities**:
  - compare options/entities
  - synthesize multi-source findings
  - identify patterns/relationships in text datasets
- **Skills**: `data-analysis`, `comparison`, `synthesis`
- **Bridge interface**:

```go
type AnalysisBridge interface {
    Analyze(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}
```

- **Routing logic**:
  - intents `IntentAnalysis`, `IntentTask`
  - keywords: `compare`, `analyze`, `tradeoff`, `pros and cons`, `synthesize`
  - default `synthesis` when multiple sources are present

### 2.3 Skills Detail

> All skills implement `skill.Skill` interface and follow existing `Execute(ctx, SkillParams)` contract.

| Skill | Input Parameters | Output Format | Tool Dependencies | Memory Integration |
|---|---|---|---|---|
| web-research | `query`, `max_results`, `provider`, `time_range` | `sources[]`, `summary`, `citations[]` | new search providers + existing `fetch` | retrieve similar episodes first; save final research episode |
| document-analysis | `document_path` or `content`, `mode` (`extract`, `summarize`, `qa`) | `key_points[]`, `entities[]`, `summary` | file read/view tools, optional PDF parser | store extracted facts |
| fact-check | `claim`, optional `sources[]` | `verdict`, `confidence`, `evidence[]`, `conflicts[]` | web-research + comparison | save fact-check episode + fact entry |
| summarization | `content`, `style`, `length` | `summary`, `bullet_points[]` | text processing (LLM output) | save explanation episode (optional) |
| simplification | `content`, `audience`, `level` | `simple_explanation`, `glossary[]` | text processing | cache by content hash in memory facts |
| examples | `concept`, `domain`, `count` | `examples[]`, `anti_examples[]` | text processing | save high-quality examples as facts |
| data-analysis | `dataset` (text/table), `question` | `findings[]`, `patterns[]`, `confidence` | grep-style text analysis + comparison | link to related episodes |
| comparison | `items[]`, `criteria[]` | `comparison_table`, `recommendation` | text processing | store comparison result as episode |
| synthesis | `sources[]`, `objective` | `synthesis`, `agreements[]`, `disagreements[]`, `gaps[]` | web-research + document-analysis | episodic record + reusable fact nuggets |

### 2.4 Tools & Providers

#### Provider API layer

```go
type SearchProvider interface {
    Name() string
    Search(ctx context.Context, req SearchRequest) (SearchResponse, error)
    IsConfigured() bool
}

type SearchRequest struct {
    Query      string
    MaxResults int
    Timeout    time.Duration
    Language   string
    Region     string
}
```

#### Provider Plan

1. **Tavily (Primary)**
   - Best fit for research-style queries and relevance ranking
   - Config: API key, timeout, max results
   - Rate limit handling: bounded retries + jitter backoff

2. **Brave (Secondary/Fallback)**
   - Reliable general web search fallback
   - Config: API key, timeout
   - Used when Tavily fails, throttles, or returns insufficient results

3. **Wikipedia (Specialized Knowledge Provider)**
   - Direct API for encyclopedic grounding and disambiguation
   - No API key needed, very useful for canonical definitions
   - Invoked explicitly for “what is”, historical context, biographies

#### Existing Tools Reuse
- `internal/llm/tools/fetch.go` for page retrieval and markdown conversion
- File tools already available for local document analysis (`view`, `file`, etc.)
- Optional future extension: dedicated `tavily.go` / `brave_search.go` tools only if needed by non-agency flows

#### Fallback behavior

```text
Primary chain for web-research/fact-check:
Tavily -> Brave -> Wikipedia (if conceptual) -> graceful partial result
```

If all fail:
- return structured error payload with attempted providers, errors, and suggested retry
- emit task_failed event and metrics increments

#### Error handling
- classify errors: `auth`, `rate_limit`, `network`, `timeout`, `invalid_response`
- retry only transient classes (`network`, `timeout`, `rate_limit`)
- never retry `auth`/`invalid_response` blindly

---

## 3) Memory Integration

Knowledge Agency will **use existing memory service** (no new vector DB implementation).

### 3.1 Storage strategy

- Store each significant research execution as an **Episode**:
  - task/query
  - sources used
  - synthesis output
  - outcome quality metadata (success/confidence)
- Store stable, reusable statements as **Facts**:
  - canonical concept summaries
  - fact-check verdicts with source and confidence
  - reusable definitions/examples

### 3.2 Retrieval strategy

Before execution of `web-research`, `fact-check`, `synthesis`:
1. Build `memory.Situation{Description: query, Context: {...}}`
2. Call `GetSimilarEpisodes` (hybrid retrieval already implemented)
3. Inject top-k prior findings into skill context
4. Continue with providers only for missing/updated knowledge

### 3.3 Cross-agency knowledge sharing

- Facts stored with domain tags (e.g., `knowledge`, `development`, `nutrition`)
- Knowledge agency can read facts from other domains through `GetFacts(domain)` for synthesis tasks
- Ensure provenance in output: source agency + source provider

### 3.4 Embedding/cache leverage

- rely on existing embedding cache and LM Studio/local provider config
- add deterministic query normalization for better cache reuse

---

## 4) Configuration Design

### 4.1 `KnowledgeConfig` struct

```go
package config

type KnowledgeConfig struct {
    Enabled               bool
    DefaultProvider       string // "tavily", "brave", "wikipedia"

    TavilyAPIKey          string
    BraveAPIKey           string

    MaxSearchResults      int
    SearchTimeoutMs       int
    MaxRetries            int
    RetryBaseDelayMs      int

    EnableMemory          bool
    MemoryTopK            int
    SaveEpisodes          bool
    SaveFacts             bool

    EnableWikipedia       bool
    EnableDocumentPDF     bool

    DefaultLanguage       string
    DefaultRegion         string
}

func (c KnowledgeConfig) IsConfigured() bool {
    if !c.Enabled {
        return false
    }
    switch c.DefaultProvider {
    case "tavily":
        return c.TavilyAPIKey != ""
    case "brave":
        return c.BraveAPIKey != ""
    case "wikipedia":
        return true
    default:
        return false
    }
}
```

### 4.2 Environment Variables

```bash
ARIA_AGENCIES_KNOWLEDGE_ENABLED=false

ARIA_KNOWLEDGE_DEFAULT_PROVIDER=tavily
ARIA_KNOWLEDGE_TAVILY_API_KEY=
ARIA_KNOWLEDGE_BRAVE_API_KEY=

ARIA_KNOWLEDGE_MAX_SEARCH_RESULTS=10
ARIA_KNOWLEDGE_SEARCH_TIMEOUT_MS=30000
ARIA_KNOWLEDGE_MAX_RETRIES=2
ARIA_KNOWLEDGE_RETRY_BASE_DELAY_MS=300

ARIA_KNOWLEDGE_ENABLE_MEMORY=true
ARIA_KNOWLEDGE_MEMORY_TOP_K=5
ARIA_KNOWLEDGE_SAVE_EPISODES=true
ARIA_KNOWLEDGE_SAVE_FACTS=true

ARIA_KNOWLEDGE_ENABLE_WIKIPEDIA=true
ARIA_KNOWLEDGE_ENABLE_DOCUMENT_PDF=false
ARIA_KNOWLEDGE_DEFAULT_LANGUAGE=en
ARIA_KNOWLEDGE_DEFAULT_REGION=US
```

### 4.3 ARIA global config integration

- Extend `AgenciesConfig` in `internal/aria/config/config.go` with:

```go
type KnowledgeAgencyConfig struct { Enabled bool }
```

- Load env var `ARIA_AGENCIES_KNOWLEDGE_ENABLED`

---

## 5) Metrics & Observability

### 5.1 `KnowledgeMetrics` structure

```go
type ProviderMetrics struct {
    TotalRequests   int64
    SuccessCount    int64
    ErrorCount      int64
    FallbackCount   int64
    CacheHitCount   int64
    CacheMissCount  int64
    TotalLatencyMs  int64
    MinLatencyMs    int64
    MaxLatencyMs    int64
    LastRequestTime time.Time
    LastError       string
}

type KnowledgeMetrics struct {
    Tavily    ProviderMetrics
    Brave     ProviderMetrics
    Wikipedia ProviderMetrics

    TotalTasks         int64
    SuccessfulTasks    int64
    FailedTasks        int64
    TotalTaskLatencyMs int64

    WebResearchCount      int64
    DocumentAnalysisCount int64
    FactCheckCount        int64
    SummarizationCount    int64
    SimplificationCount   int64
    ExamplesCount         int64
    DataAnalysisCount     int64
    ComparisonCount       int64
    SynthesisCount        int64
}
```

### 5.2 Instrumentation points

- At provider call boundary: record request, latency, cache hit/miss, fallback usage
- At agency execution boundary: record task success/failure and skill bucket
- At error exits: record `LastError` and typed error category

### 5.3 Logging

Use structured logs already used in app:
- `agency=knowledge`
- `agent=researcher|educator|analyst`
- `skill=...`
- `provider=...`
- `fallback=true|false`
- `memory_hits=n`

---

## 6) Implementation Phases

## Phase K1: Foundation

**Goals**
- Add `knowledge.go` implementing `agency.Agency`
- Add `KnowledgeConfig` and env wiring
- Implement `ResearchBridge` + `WebResearchSkill`
- Integrate one provider (Tavily)
- Add unit tests for routing and bridge execution

**Deliverables**
- `internal/aria/agency/knowledge.go`
- `internal/aria/config/knowledge.go`
- `internal/aria/skill/web_research.go`
- `internal/aria/agency/knowledge/providers/tavily.go`
- tests for skill + bridge + agency lifecycle

**Dependencies**
- existing `fetch` tool
- existing contracts/task model

## Phase K2: Multi-provider & Skills

**Goals**
- Add Brave provider and fallback chain
- Add `fact_check.go`, `summarization.go`, `simplification.go`, `examples.go`
- Implement `Educator` bridge
- Add provider error classification and retry strategy

**Deliverables**
- provider abstraction + fallback orchestrator
- additional skills + unit/integration tests
- metrics package skeleton

**Dependencies**
- K1 completed

## Phase K3: Memory & Analytics

**Goals**
- Wire knowledge agency to memory service integration points
- Add episodic storage + fact storage policies
- Implement `analyst` bridge (`data-analysis`, `comparison`, `synthesis`)
- Add semantic retrieval pre-step for researcher/analyst skills

**Deliverables**
- memory-aware skill execution path
- `document_analysis.go`, `data_analysis.go`, `comparison.go`, `synthesis.go`
- memory integration tests

**Dependencies**
- K1/K2 completed
- memory embedding system already available

## Phase K4: Polish & Documentation

**Goals**
- Harden error handling and partial-result behavior
- finalize metrics and add operational runbook
- optimize query normalization and caching
- add E2E tests with real provider keys (optional CI-gated)

**Deliverables**
- docs: runbook + troubleshooting + env reference
- performance benchmarks and target SLO notes

**Dependencies**
- K1-K3 complete

---

## 7) Integration Points

### 7.1 App Integration (`internal/app/aria_integration.go`)

```go
knowledgeCfg := ariaConfig.DefaultKnowledgeConfig()
var knowledgeAgency *agency.KnowledgeAgency
if ariaCfg.Agencies.Knowledge.Enabled && knowledgeCfg.IsConfigured() {
    knowledgeAgency = agency.NewKnowledgeAgency(knowledgeCfg, memorySvc)
    orchestrator.RegisterAgency(knowledgeAgency)
    if err := agencyService.RegisterAgency(ctx, knowledgeAgency); err != nil {
        logging.Warn("Failed to persist knowledge agency", "error", err)
    }
}
```

Also extend `ARIAComponents`:

```go
KnowledgeAgency *agency.KnowledgeAgency
```

### 7.2 Routing Integration

Update baseline routing rules (`internal/aria/routing/router_impl.go`) with intent+pattern rules:
- `IntentQuestion` + `IntentLearning` -> agency `knowledge`, skills `summarization|fact-check`
- `IntentAnalysis` -> agency `knowledge`, skills `comparison|synthesis`
- patterns: `explain`, `research`, `compare`, `verify`, `learn`, `summarize`

Expected intents to document:
- `IntentQuestion`
- `IntentLearning`
- `IntentAnalysis`

### 7.3 Skill Registry

Register knowledge skills in default setup (`SetupDefaultSkills`) with feature flags and `CanExecute` checks based on provider config.

---

## 8) Error Handling Strategy

1. **Provider failures** -> provider fallback chain with structured reason
2. **Rate limits** -> exponential backoff + jitter + max retries
3. **Network failures** -> retry with context timeout and cancellation compliance
4. **Invalid responses** -> schema validation + fallback provider
5. **All providers failed** -> partial response using memory + explicit uncertainty markers

Error payload standard:

```json
{
  "error_type": "rate_limit|network|auth|invalid_response",
  "provider_attempts": ["tavily", "brave"],
  "recoverable": true,
  "message": "..."
}
```

---

## 9) Testing Strategy

### 9.1 Unit tests
- `knowledge.go` lifecycle and task routing
- each bridge implementation
- each skill input validation/output contracts
- provider adapters with mocked HTTP
- metrics recording correctness

### 9.2 Integration tests
- fallback chain Tavily -> Brave -> Wikipedia
- routing to correct skill based on task/intents
- memory pre-retrieval and post-storage behavior

### 9.3 E2E tests (conditional)
- real APIs when env keys available
- verify result quality and response structure

### 9.4 Verification gates

```bash
go vet ./...
go test ./internal/aria/agency/... -v
go test ./internal/aria/skill/... -v
go test ./internal/aria/routing/... -v
go build -o /tmp/aria-test ./main.go
```

---

## 10) Rollback Plan

- keep feature flag `ARIA_AGENCIES_KNOWLEDGE_ENABLED=false` as hard disable
- if providers unavailable, agency returns degraded output from memory only
- agency supports `Pause()` without impacting other agencies
- preserve backward compatibility in orchestrator startup even if knowledge config invalid

---

## 11) Dependencies Between Phases

```text
K1 -> K2 -> K3 -> K4

K2 depends on K1 base agency + config.
K3 depends on K2 multi-skill/provider maturity.
K4 depends on K3 memory and analyst completion.
```

Critical external dependencies:
- Tavily API key
- Brave API key
- optional PDF parser library selection (if enabled in K3/K4)

---

## 12) Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Provider API instability | Medium/High | multi-provider fallback + retries + cached/memory answers |
| Rate-limit bursts | Medium | per-provider backoff + request budgeting + max results cap |
| Hallucinated synthesis | High | enforce citation-first synthesis, fact-check for critical claims |
| Memory bloat | Medium | retention policy + confidence thresholds for fact storage |
| Scope creep in educator capabilities | Medium | keep educator text-only initially; no new model infra in K1-K3 |
| PDF parsing complexity | Medium | optional flag, defer heavy parsing to K4 |

---

## 13) Decision Log (Answers to Required Questions)

1. **Primary web search provider?**  
   **Tavily primary**, Brave secondary. Tavily is better aligned with research relevance and structured extraction.

2. **Wikipedia direct API or via web search?**  
   **Direct Wikipedia integration** as specialized provider, plus web fallback for non-encyclopedic content.

3. **Educator agent LLM capabilities?**  
   Reuse existing ARIA LLM response path; require prompt templates for depth control (`novice`, `intermediate`, `expert`) and deterministic structured outputs (summary, glossary, examples).

4. **Should document analysis include PDF parsing?**  
   **Yes, but feature-gated** (`ARIA_KNOWLEDGE_ENABLE_DOCUMENT_PDF`) and introduced in K3/K4 to limit early complexity.

5. **Memory integration: Facts or Episodes?**  
   **Both**: Episodes for workflow/history; Facts for reusable validated knowledge.

6. **Fallback chain when primary fails?**  
   `Tavily -> Brave -> Wikipedia (if conceptual) -> memory-only partial response`.

7. **Local knowledge base (new vector store) vs semantic memory?**  
   **Rely on existing semantic memory system**; no new vector store in this implementation.

8. **Rate limit handling?**  
   Bounded exponential backoff with jitter, provider-specific retry policy, and graceful degradation with explicit quality/confidence metadata.

---

## 14) Suggested Implementation Sequence (Granular)

1. Config scaffolding (`knowledge.go` config + envs + global agencies config)
2. Agency skeleton + lifecycle + event broker integration
3. Research bridge + Tavily provider + web-research skill
4. App wiring in `aria_integration.go`
5. Brave + Wikipedia provider adapters + fallback manager
6. Educator skills + bridge
7. Analyst skills + bridge
8. Metrics package + instrumentation
9. Memory integration (retrieve/store)
10. Routing rules update and full test sweep

---

## 15) Done Criteria

Knowledge Agency is considered complete when:
- Agency can be enabled and registered at runtime
- 3 agents and required skills are callable through task routing
- provider fallback works and is tested
- memory integration stores/retrieves useful research context
- observability exposes per-provider and per-skill metrics
- all verification gates pass (`vet`, tests, build)
