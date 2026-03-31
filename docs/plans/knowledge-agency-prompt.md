# Prompt for GPT-5.3 Codex: Knowledge Agency Implementation

## Context

You are designing a complete implementation plan for the **Knowledge Agency** in the ARIA project (Autonomous Reasoning & Intelligent Assistant). ARIA is a terminal-based AI coding assistant built in Go, with a TUI built with Bubble Tea, supporting multiple LLM providers (Anthropic, OpenAI, Gemini, Copilot, Bedrock, Azure, VertexAI, OpenRouter, Groq, XAI), and uses SQLite for persistence via sqlc-generated query code.

The Knowledge Agency is one of the core agencies planned in the ARIA blueprint (docs/foundation/BLUEPRINT.md). It handles research, learning, and general Q&A capabilities.

**Current Status**: The Knowledge Agency is NOT STARTED (scheduled for FASE 5). All foundation work is complete (FASE 0-4 done), and the Weather Agency (POC) and Nutrition Agency (full) are already implemented. The Memory Embedding system with hybrid semantic retrieval was just completed (Phase 0-5).

---

## Objective

Design and elaborate a complete implementation plan for the Knowledge Agency, following the existing patterns in the codebase (Nutrition Agency as reference). The plan should cover:

1. **Agency Structure** — agents, skills, bridges
2. **Tools & Providers** — web search, document processing, knowledge APIs
3. **Memory Integration** — leveraging the newly implemented memory embedding system
4. **Config & Environment** — configuration pattern
5. **Metrics & Observability** — metrics pattern
6. **Implementation Phases** — phased rollout approach
7. **Integration Points** — wiring into ARIA runtime

---

## Reference Implementation: Nutrition Agency

The Nutrition Agency (docs/foundation/BLUEPRINT.md, Section 7.2) is the most complete agency implementation. Use it as the primary reference for structure and patterns.

### Key Files to Reference

| File | Purpose |
|------|---------|
| `internal/aria/agency/nutrition.go` | Full agency implementation with bridges |
| `internal/aria/agency/nutrition/metrics/metrics.go` | Metrics implementation |
| `internal/aria/config/nutrition.go` | Config with env var wiring |
| `internal/llm/tools/fetch.go` | Web fetch tool (generic, can be extended) |
| `internal/llm/tools/websearch.go` | Web search tool |
| `internal/aria/agency/agency.go` | Core Agency interface |
| `internal/aria/skill/skill.go` | Skill interface |
| `internal/app/aria_integration.go` | How agencies are wired into app |

### Agency Interface Contract

```go
type Agency interface {
    // Lifecycle
    Start(ctx context.Context) error
    Stop(ctx context.Context) error
    Pause(ctx context.Context) error
    Resume(ctx context.Context) error
    Status() AgencyStatus

    // Events
    Subscribe(ctx context.Context) <-chan contracts.AgencyEvent

    // Identity
    Name() contracts.AgencyName
    Domain() string
    Description() string

    // Agents
    Agents() []contracts.AgentName
    GetAgent(name contracts.AgentName) (interface{}, error)

    // Task execution
    Execute(ctx context.Context, task contracts.Task) (contracts.Result, error)

    // State
    GetState() AgencyState
    SaveState(state AgencyState) error

    // Domain memory
    Memory() DomainMemory
}
```

### Bridge Pattern

Each skill has a bridge interface and implementation:

```go
// Bridge interface
type ResearchBridge interface {
    ConductResearch(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}

// Implementation
type ResearchBridgeImpl struct {
    skill *skill.WebResearchSkill
    tools []tools.BaseTool
}

func NewResearchBridge(s *skill.WebResearchSkill, t []tools.BaseTool) *ResearchBridgeImpl {
    return &ResearchBridgeImpl{skill: s, tools: t}
}

func (b *ResearchBridgeImpl) ConductResearch(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error) {
    // Extract params from task
    // Execute skill
    // Return result
}
```

---

## Knowledge Agency Specification (from BLUEPRINT.md)

### Domain
Ricerca, apprendimento, Q&A generale

### Agents (3)

1. **researcher**
   - Description: Deep research on any topic
   - Skills: web-research, document-analysis, fact-check

2. **educator**
   - Description: Explain concepts, teach
   - Skills: summarization, simplification, examples

3. **analyst**
   - Description: Analyze information, find connections
   - Skills: data-analysis, comparison, synthesis

### Skills Required

| Skill | Purpose | Tools Needed |
|-------|---------|--------------|
| web-research | Search web, extract info | web-search, fetch |
| document-analysis | Analyze documents, extract key info | file-read, parse |
| fact-check | Verify facts against sources | web-search, comparison |
| summarization | Summarize content | text-processing |
| simplification | Simplify complex concepts | text-processing, examples |
| examples | Generate examples | text-processing |
| data-analysis | Analyze data, find patterns | grep, comparison |
| comparison | Compare entities, options | text-processing |
| synthesis | Synthesize multiple sources | web-search, synthesis |

### Knowledge Sources / Providers

Consider integrating:
- **Web Search**: Tavily API, Brave Search, DuckDuckGo
- **Web Fetch**: Firecrawl, direct fetch
- **Knowledge Bases**: Wikipedia API, Wolfram Alpha
- **Document Processing**: PDF parsing, markdown processing
- **Code Search**: GitHub API, Sourcegraph

---

## Memory Embedding Integration

The recently implemented memory embedding system should be leveraged:

- **Hybrid Semantic Retrieval**: `GetSimilarEpisodes` uses vector (40%) + keyword (30%) + recency (20%) + outcome (10%)
- **Local Embedding**: LM Studio at localhost:1234 with `text-embedding-mxbai-embed-large-v1`
- **Embedding Config**: Via `memory.Enabled`, `memory.Provider`, `memory.Model`, `memory.Mode`

Knowledge Agency should:
1. Store research findings as `Episode` or `Fact` in memory
2. Use semantic retrieval to find relevant past research
3. Leverage embedding cache for repeated queries

---

## What to Deliver

Create a comprehensive implementation plan saved as `docs/plans/knowledge-agency-implementation-plan.md` with:

### 1. Executive Summary
Brief overview of the Knowledge Agency scope and approach.

### 2. Architecture Design

#### 2.1 Agency Structure
```
knowledge.go           # Main agency with all bridges
knowledge/
├── metrics/
│   └── metrics.go     # KnowledgeMetrics (per provider: requests, latency, errors, cache)
├── skills/
│   ├── web_research.go
│   ├── document_analysis.go
│   ├── fact_check.go
│   └── synthesis.go
└── providers/
    ├── tavily.go       # Tavily search provider
    ├── brave.go        # Brave Search provider
    └── wikipedia.go    # Wikipedia API provider
```

#### 2.2 Agents Detail
For each agent (researcher, educator, analyst):
- Responsibilities
- Skills used
- Bridge interface
- Task routing logic

#### 2.3 Skills Detail
For each skill:
- Input parameters
- Output format
- Tool dependencies
- Integration with memory

#### 2.4 Tools & Providers
For each tool/provider:
- API/interface
- Configuration required
- Rate limits
- Fallback behavior
- Error handling

### 3. Memory Integration
How Knowledge Agency leverages the memory embedding system:
- Storing research as Episodes
- Semantic retrieval of past research
- Fact storage in semantic memory
- Cross-agency knowledge sharing

### 4. Configuration Design

#### 4.1 KnowledgeConfig struct
```go
type KnowledgeConfig struct {
    Enabled          bool
    DefaultProvider  string  // "tavily", "brave", "wikipedia"
    Tavily_APIKey    string
    Brave_APIKey     string
    MaxSearchResults int
    SearchTimeoutMs  int
    EnableMemory     bool    // Store research in memory
    // ... other settings
}
```

#### 4.2 Environment Variables
```
ARIA_AGENCIES_KNOWLEDGE_ENABLED=
ARIA_KNOWLEDGE_DEFAULT_PROVIDER=tavily
ARIA_KNOWLEDGE_TAVILY_API_KEY=
ARIA_KNOWLEDGE_BRAVE_API_KEY=
ARIA_KNOWLEDGE_MAX_SEARCH_RESULTS=10
ARIA_KNOWLEDGE_SEARCH_TIMEOUT_MS=30000
ARIA_KNOWLEDGE_ENABLE_MEMORY=true
```

### 5. Metrics & Observability

#### 5.1 KnowledgeMetrics Structure
Per-provider metrics:
- TotalRequests, SuccessCount, ErrorCount
- CacheHitCount, CacheMissCount
- TotalLatencyMs, AvgLatencyMs, MinLatencyMs, MaxLatencyMs
- LastRequestTime, LastError

Agency-level metrics:
- TotalTasks, SuccessfulTasks, FailedTasks
- Per-skill task counts

### 6. Implementation Phases

#### Phase K1: Foundation
- Create `knowledge.go` with basic agency structure
- Implement ResearcherAgent with WebResearchSkill
- Basic web search integration (one provider)
- Agency lifecycle methods
- Unit tests

#### Phase K2: Multi-Provider & Skills
- Add Brave Search provider as fallback
- Implement EducatorAgent with SummarizationSkill
- Implement FactCheckSkill
- Provider fallback logic
- Integration tests

#### Phase K3: Memory & Analytics
- Integrate with memory embedding system
- Store research as Episodes
- Semantic retrieval of past research
- Implement AnalystAgent
- E2E tests

#### Phase K4: Polish & Documentation
- Performance optimization
- Error handling hardening
- Documentation (runbook, API docs)
- Metrics dashboard

### 7. Integration Points

#### 7.1 App Integration (aria_integration.go)
```go
// Wire Knowledge Agency
knowledgeCfg := config.DefaultKnowledgeConfig()
if ariaCfg.Agencies.Knowledge.Enabled && knowledgeCfg.IsConfigured() {
    knowledgeAgency = agency.NewKnowledgeAgency(knowledgeCfg)
    orchestrator.RegisterAgency(knowledgeAgency)
    if err := agencyService.RegisterAgency(ctx, knowledgeAgency); err != nil {
        logging.Warn("Failed to persist knowledge agency", "error", err)
    }
}
```

#### 7.2 Routing Integration
The orchestrator routes queries to Knowledge Agency based on intent classification. Document the expected intents: `IntentQuestion`, `IntentLearning`, `IntentAnalysis`.

### 8. Error Handling

- Provider failures → fallback to alternate provider
- API rate limits → exponential backoff with queue
- Network failures → retry with timeout
- Invalid responses → validation with fallback

### 9. Testing Strategy

- Unit tests for each skill and bridge
- Integration tests with mocked providers
- E2E tests with real API calls (if keys available)
- Memory integration tests

### 10. Rollback Plan

- Feature flag to disable agency without removing code
- Graceful degradation if provider fails
- Agency can be paused without affecting other agencies

---

## Constraints

1. **Follow existing patterns**: Use Nutrition Agency as reference, don't reinvent patterns
2. **Use existing tools where possible**: `fetch.go`, `websearch.go` if they exist
3. **Leverage memory embedding**: The system just implemented should be used, not re-implemented
4. **Multi-provider fallback**: At least 2 providers for resilience
5. **Config via env vars**: Follow ARIA_AGENCIES_* pattern
6. **Metrics per provider**: Follow NutritionMetrics pattern
7. **Go tested code**: All new code must pass `go vet` and existing tests

---

## Verification Gates

After implementation, all must pass:
```bash
go vet ./...
go test ./internal/aria/agency/... -v
go build -o /tmp/aria-test ./main.go
```

---

## Output Format

Save the complete plan as: `docs/plans/knowledge-agency-implementation-plan.md`

The plan should be:
- Detailed enough for a developer to implement
- Organized by phase for incremental delivery
- Include code snippets where helpful
- Clearly mark dependencies between phases
- Identify risks and mitigations

---

## Questions to Answer in the Plan

1. Which web search provider should be primary (Tavily vs Brave vs DuckDuckGo)?
2. Should we integrate with Wikipedia API directly or via web search?
3. How to handle the "educator" agent - what LLM capabilities does it need?
4. Should document analysis include PDF parsing?
5. How should memory integration work - store as Facts or Episodes?
6. What's the fallback chain when primary provider fails?
7. Should we implement a local knowledge base (vector store) or rely on semantic memory?
8. How to handle rate limits gracefully?
