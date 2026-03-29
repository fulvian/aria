# FASE 5: Specialized Agencies Implementation Plan

**Data**: 2026-03-29 (Updated)  
**Durata**: 8-12 settimane (following POC-based approach)  
**Obiettivo**: Implementare agencies specializzate con architettura tool efficient

---

## Architectural Decision: Tool Integration Pattern

### Problem: MCP Token Overhead

MCP (Model Context Protocol) è dispendioso in termini di token di contesto:
- **Tool descriptions**: ~200 tokens vs ~50 per direct API
- **Call overhead**: ~100 tokens vs ~30 per direct API
- **Total per call**: ~350 tokens vs ~100 tokens

Per 1000 chiamate: **Direct API = 100K tokens, MCP = 350K tokens** (+250% overhead)

### Solution: Hybrid Tool Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                    TOOL INTEGRATION LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│   │  Native Tools   │  │  Direct APIs    │  │   MCP Servers   │   │
│   │  (internal)    │  │  (external)     │  │   (last resort) │   │
│   │                │  │                 │  │                  │   │
│   │  • bash       │  │  • Weather API  │  │  • Enterprise   │   │
│   │  • grep       │  │  • Calendar API │  │    (Slack,     │   │
│   │  • edit       │  │  • Search API   │  │    Jira)        │   │
│   │  • glob       │  │  • Database     │  │  • Dynamic      │   │
│   │                │  │                │  │    discovery    │   │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘   │
│                                                                  │
│   Tool Categories:                                                │
│   ───────────────                                                │
│   1. Native Tools: Direct Function Calling (lowest overhead)    │
│   2. External APIs: Direct HTTP from Skills (efficient)         │
│   3. MCP: Only for enterprise + dynamic discovery               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Decision Matrix

| Scenario | Pattern | Reason |
|----------|---------|--------|
| bash, grep, edit, glob | Native Function Calling | Already in OpenCode, fixed interface |
| Weather, Calendar, Search | Direct API from Skill | Known endpoints, no discovery needed |
| Slack, Jira, Enterprise | MCP | Tool discovery, enterprise governance |
| Filesystem | Native (existing) | Already implemented |

---

## Proof of Concept: Weather Agency

### Why Weather First

1. **API gratuite**: OpenWeatherMap (1000 calls/day free), Tomorrow.io (500/day free)
2. **Caso d'uso semplice**: "What's the weather in Rome?"
3. **Nessuna dipendenza complessa**: No auth OAuth, no calendar sync
4. **Risultati verificabili**: Confronta con altri servizi
5. **Architecture validation**: Test tool integration pattern

### Implementation Order

```
FASE 5.1: Weather Agency POC (2-3 weeks)
    │
    ├─► Create Weather Agency structure
    ├─► Implement Weather Skills (current, forecast, alerts)
    ├─► Direct API integration (NO MCP)
    ├─► Test & validate architecture
    │
    ▼
FASE 5.2: Knowledge Agency (2-3 weeks)
    │
    ├─► Web search skills (Tavily/Brave direct API)
    ├─► Document analysis skills
    ├─► Q&A capabilities
    │
    ▼
FASE 5.3: Creative Agency (2-3 weeks)
    │
    ├─► Writing skills
    ├─► Translation (direct API)
    │
    ▼
FASE 5.4: Productivity Agency (2-3 weeks)
    │
    ├─► Calendar integration (direct API)
    ├─► Planning skills
    │
    ▼
FASE 5.5: Personal & Analytics Agencies (2-3 weeks)
```

---

## 5.1 Weather Agency POC

### Structure

```
Weather Agency
├── WeatherAgent
│   ├── current-weather skill
│   ├── forecast skill
│   ├── alerts skill
│   └── historical-weather skill
└── Direct OpenWeatherMap API integration
```

### Files to Create

| File | Purpose |
|------|---------|
| `internal/aria/agency/weather.go` | Weather Agency |
| `internal/aria/skill/weather_current.go` | Current weather skill |
| `internal/aria/skill/weather_forecast.go` | Forecast skill |
| `internal/aria/skill/weather_alerts.go` | Alerts skill |
| `internal/llm/tools/weather.go` | Weather tool (direct API) |
| `internal/aria/config/weather.go` | Weather config |

### API Options

**OpenWeatherMap** (Recommended)
- Free tier: 1000 calls/day
- Current weather, 5-day forecast, air pollution
- API: https://openweathermap.org/api

**Tomorrow.io** (Fallback)
- Free tier: 500 calls/day
- Good documentation
- API: https://www.tomorrow.io/

---

## 5.2 Knowledge Agency

### Structure

```
Knowledge Agency
├── ResearcherAgent
│   ├── web-research skill (Tavily/Brave direct API)
│   ├── document-analysis skill
│   └── fact-check skill
├── EducatorAgent
│   ├── summarization skill
│   └── teaching skill
└── AnalystAgent
    └── data-analysis skill
```

### Web Search Integration

**Option 1: Tavily Direct API** (Recommended for research)
- Free tier: 1000 requests/month
- AI-optimized search results
- Direct API vs MCP

**Option 2: Brave Search API**
- Free tier: 2000 queries/month
- Web search + news
- Direct API

### Files to Create

| File | Purpose |
|------|---------|
| `internal/aria/agency/knowledge.go` | Knowledge Agency |
| `internal/aria/skill/web_research.go` | Web research skill |
| `internal/aria/skill/document_analysis.go` | Document analysis |
| `internal/llm/tools/tavily.go` | Tavily tool (direct API) |
| `internal/llm/tools/brave_search.go` | Brave Search tool |

---

## 5.3 Creative Agency

### Structure

```
Creative Agency
├── WriterAgent
│   ├── creative-writing skill
│   ├── copywriting skill
│   └── editing skill
├── TranslatorAgent
│   ├── translation skill (direct API)
│   └── localization skill
└── DesignerAgent
    └── design skill
```

### Translation API Options

**LibreTranslate** (Open Source, self-hostable)
- Free, no API key needed (self-hosted)
- Or paid hosted version

**Google Translate API**
- Free tier: 500K chars/month
- Direct API

### Files to Create

| File | Purpose |
|------|---------|
| `internal/aria/agency/creative.go` | Creative Agency |
| `internal/aria/skill/writing.go` | Writing skill |
| `internal/aria/skill/translation.go` | Translation skill |
| `internal/llm/tools/translation.go` | Translation tool |

---

## 5.4 Productivity Agency

### Structure

```
Productivity Agency
├── PlannerAgent
│   ├── planning skill
│   └── task-breakdown skill
├── SchedulerAgent
│   ├── calendar skill (Google Calendar API direct)
│   └── reminders skill
└── OrganizerAgent
    └── file-organization skill
```

### Calendar Integration

**Google Calendar API** (Direct API)
- OAuth 2.0 required
- Free tier: 1M calls/day
- Direct API vs MCP

**Alternative: Cal.com**
- Open source
- Direct API

### Files to Create

| File | Purpose |
|------|---------|
| `internal/aria/agency/productivity.go` | Productivity Agency |
| `internal/aria/skill/planning.go` | Planning skill |
| `internal/aria/skill/calendar.go` | Calendar skill |
| `internal/llm/tools/google_calendar.go` | Calendar tool |

---

## 5.5 Personal Agency

### Structure

```
Personal Agency
├── AssistantAgent
│   ├── recommendations skill
│   └── general-assistance skill
├── WellnessAgent
│   ├── habit-tracking skill
│   └── nutrition skill
└── FinanceAgent
    └── budgeting skill
```

### APIs

- **OpenWeatherMap**: Already used in Weather Agency
- **NewsAPI**: Free tier for news
- **Nutrition API**: Open Food Facts (free)

### Files to Create

| File | Purpose |
|------|---------|
| `internal/aria/agency/personal.go` | Personal Agency |
| `internal/aria/skill/wellness.go` | Wellness skill |
| `internal/aria/skill/finance.go` | Finance skill |

---

## 5.6 Analytics Agency

### Structure

```
Analytics Agency
├── DataAnalystAgent
│   ├── data-analysis skill
│   └── statistics skill
├── VisualizerAgent
│   └── visualization skill (charts)
└── ReporterAgent
    └── reporting skill
```

### Data Tools

- **Data loading**: CSV, JSON, SQL direct
- **Visualization**: Mermaid, Chart.js
- **Export**: PDF, HTML

### Files to Create

| File | Purpose |
|------|---------|
| `internal/aria/agency/analytics.go` | Analytics Agency |
| `internal/aria/skill/data_analysis.go` | Data analysis skill |
| `internal/aria/skill/visualization.go` | Visualization skill |

---

## Agency Registry Updates

### Registration

```go
// internal/aria/agency/registry.go
func init() {
    // Development Agency (already exists)
    registry.RegisterAgency(NewDevelopmentAgency(...))
    
    // NEW: Weather Agency (POC)
    registry.RegisterAgency(NewWeatherAgency(...))
    
    // NEW: Knowledge Agency
    registry.RegisterAgency(NewKnowledgeAgency(...))
    
    // NEW: Creative Agency
    registry.RegisterAgency(NewCreativeAgency(...))
    
    // NEW: Productivity Agency
    registry.RegisterAgency(NewProductivityAgency(...))
    
    // NEW: Personal Agency
    registry.RegisterAgency(NewPersonalAgency(...))
    
    // NEW: Analytics Agency
    registry.RegisterAgency(NewAnalyticsAgency(...))
}
```

---

## When to Use MCP

MCP is appropriate when:

1. **Enterprise governance required**: Centralized tool management
2. **Dynamic tool discovery**: Tools that change or are added frequently
3. **Multi-agent scenarios**: Agent-to-agent communication
4. **Community plugins**: External tool providers

MCP is NOT appropriate for:

1. **Fixed APIs**: Weather, Calendar, Search (known endpoints)
2. **Token-sensitive operations**: High-volume tool calls
3. **Simple integrations**: Direct HTTP is more efficient

---

## Deliverables

- [x] POC Plan (Weather Agency)
- [ ] Weather Agency POC (2-3 weeks)
  - [ ] Weather Agency structure
  - [ ] 4 Weather skills
  - [ ] Direct API integration
  - [ ] Architecture validation
- [ ] Knowledge Agency (2-3 weeks)
- [ ] Creative Agency (2-3 weeks)
- [ ] Productivity Agency (2-3 weeks)
- [ ] Personal Agency (1-2 weeks)
- [ ] Analytics Agency (1-2 weeks)
- [ ] Registry updates
- [ ] Comprehensive testing

---

## Technical Notes

### Token Cost Comparison

| Pattern | Tokens/Call | 1000 Calls | Best For |
|---------|-------------|-----------|----------|
| Native Tool | ~50 | 50K | bash, grep, edit |
| Direct API | ~100 | 100K | Weather, Calendar, Search |
| MCP | ~350 | 350K | Enterprise, dynamic discovery |

### API Keys Needed

| Service | Free Tier | Signup |
|--------|-----------|--------|
| OpenWeatherMap | 1000/day | https://openweathermap.org/api |
| Tomorrow.io | 500/day | https://www.tomorrow.io/ |
| Tavily | 1000/month | https://tavily.com/ |
| Brave Search | 2000/month | https://brave.com/search/api/ |

### Configuration

```yaml
# internal/aria/config/config.go
weather:
  provider: "openweathermap"
  api_key: "${OPENWEATHERMAP_API_KEY}"
  
knowledge:
  tavily_api_key: "${TAVILY_API_KEY}"
  brave_api_key: "${BRAVE_SEARCH_API_KEY}"
```

---

## Verification Plan

1. `go build ./...` - Must pass
2. `go test ./internal/aria/agency/weather/...` - Weather tests
3. Manual test: "What's the weather in Rome?"
4. Token usage verification
5. Cross-agency test: "Research weather in Rome, then write a travel post"

---

## References

- [MCP vs APIs comparison](https://www.tinybird.co/blog/mcp-vs-apis-when-to-use-which-for-ai-agent-development)
- [Anthropic MCP benchmarks](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Tool calling patterns](https://martinfowler.com/articles/function-call-LLM.html)
- [OpenWeatherMap API](https://openweathermap.org/api)
- [Tomorrow.io API](https://www.tomorrow.io/)
