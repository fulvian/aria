# FASE 5 POC: Weather Agency - Proof of Concept

**Data**: 2026-03-29  
**Durata**: 2-3 settimane  
**Obiettivo**: Validare l'architettura delle agencies con un caso d'uso semplice e concreto

---

## Scopo del POC

Prima di implementare tutte le agencies, validiamo l'architettura creando una **Weather Agency** come proof of concept. Il meteo è ideale perché:

1. **API gratuite disponibili** (OpenWeatherMap, Tomorrow.io)
2. **Caso d'uso semplice e chiaro**
3. **Nessuna dipendenza complessa** (calendar, email, etc.)
4. **Risultati verificabili** (confrontando con altri servizi)

---

## Tool Integration Architecture

### 5.1 Criteri di Valutazione

Dalla ricerca sulle best practice:

| Pattern | Token Cost | Latency | Tool Discovery | Best For |
|---------|------------|---------|---------------|----------|
| **Direct API Call** | Basso | Minima | No | Fixed, known tools |
| **Function Calling** | Medio | Bassa | No | Curated small set |
| **MCP** | Alto (~10-15% overhead) | Media-Alta | Yes | Enterprise, dynamic tools |

### 5.2 Decisione Architetturale

**Per ARIA adottiamo questo approccio:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    TOOL INTEGRATION LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│   │  Native Tools   │  │  Direct APIs   │  │  MCP Servers    │   │
│   │  (internal)    │  │  (external)    │  │  (dynamic)     │   │
│   │                │  │                │  │                 │   │
│   │  • bash       │  │  • Weather     │  │  • Filesystem   │   │
│   │  • grep       │  │  • Calendar    │  │  • Slack       │   │
│   │  • edit       │  │  • Web Search │  │  • Jira        │   │
│   │  • glob       │  │  • Database   │  │  • Custom MCP  │   │
│   │                │  │                │  │                 │   │
│   │  Direct LLM   │  │  Skill-Local   │  │  Discovery-     │   │
│   │  Function     │  │  HTTP Client   │  │  Based         │   │
│   │  Calling      │  │                │  │                 │   │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘   │
│                                                                  │
│   LEGEND:                                                         │
│   ──────                                                          │
│   Direct API: Token-efficient, low latency, no discovery           │
│   MCP: Higher overhead, tool discovery, enterprise use cases       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Tool Categories

| Categoria | Integrazione | Token Cost | Use Case |
|----------|--------------|------------|----------|
| **Native Tools** | Direct Function Calling | Basso | bash, grep, edit, glob |
| **External APIs** | Direct HTTP calls from Skills | Basso | Weather, Calendar, Database |
| **MCP Servers** | MCP protocol (last resort) | Alto | Filesystem, Slack, Jira, tools requiring discovery |

### 5.4 Perché Direct API invece di MCP per Meteo

1. **Token efficiency**: MCP aggiunge ~10-15% overhead JSON-RPC
2. **Latency**: Direct API calls sono più veloci
3. **Fixed interface**: Le API meteo non cambiano dinamicamente
4. **No discovery needed**: Sappiamo esattamente quali endpoint chiamare
5. **Cost**: Meno token = meno costo

**MCP rimane per**:
- Tool che richiedono discovery dinamico
- Enterprise integrations (Slack, Jira)
- Filesystem operations (ma abbiamo già tool nativi)

---

## Weather Agency Architecture

### 6.1 Struttura

```
Weather Agency
├── WeatherAgent (meteorologist)
│   ├── Skills:
│   │   ├── current-weather (skill)
│   │   ├── forecast (skill)
│   │   ├── weather-alerts (skill)
│   │   └── historical-weather (skill)
│   └── Tools:
│       └── OpenWeatherMap API (direct HTTP)
```

### 6.2 Skills Definition

```go
// internal/aria/skill/weather.go

type WeatherSkill struct {
    baseSkill
    apiKey   string
    provider string  // "openweathermap" | "tomorrow.io"
}

func (s *WeatherSkill) Name() SkillName {
    return "weather-current"
}

func (s *WeatherSkill) Description() string {
    return "Get current weather conditions for a location"
}

func (s *WeatherSkill) RequiredTools() []ToolName {
    // NO MCP - direct HTTP call internally
    return []ToolName{}  // Uses internal HTTP client
}

func (s *WeatherSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
    // Direct API call to OpenWeatherMap
    // No tool call needed - skill makes HTTP request directly
}
```

### 6.3 Tool Implementation (Direct API)

```go
// internal/llm/tools/weather.go

type WeatherTool struct {
    baseTool
    apiKey   string
}

func (t *WeatherTool) Name() string {
    return "weather"
}

func (t *WeatherTool) Info() ToolInfo {
    return ToolInfo{
        Description: "Get weather information for a location",
        Parameters: map[string]any{
            "location": "string (city name or coordinates)",
            "units":    "metric|imperial|standard",
        },
    }
}

// Execute makes direct HTTP call to OpenWeatherMap API
// NOT through MCP - direct SDK/HTTP call
func (t *WeatherTool) Run(ctx context.Context, call ToolCall) (ToolResponse, error) {
    location := call.Params["location"].(string)
    
    // Direct API call - no MCP overhead
    weather, err := openweathermap.GetCurrent(location, t.apiKey)
    if err != nil {
        return ToolResponse{IsError: true, Content: err.Error()}, nil
    }
    
    return ToolResponse{
        Content: formatWeather(weather),
    }, nil
}
```

### 6.4 Alternative: MCP only for External Discovery

Se in futuro serve discovery dinamico per nuove API:

```yaml
# internal/aria/config/config.go
mcp:
  enabled: true
  servers:
    - name: "weather-discovery"
      type: "http"  
      url: "${WEATHER_MCP_URL}"  # Only if needed
```

Ma per ora: **Direct API calls**.

---

## Implementation Tasks

### 7.1 Phase 1: Weather Agency Structure

- [ ] Creare `internal/aria/agency/weather.go`
- [ ] Definire WeatherAgent con skills
- [ ] Implementare DomainMemory per weather context

### 7.2 Phase 2: Weather Skills

- [ ] Creare `internal/aria/skill/weather_current.go`
- [ ] Creare `internal/aria/skill/weather_forecast.go`
- [ ] Creare `internal/aria/skill/weather_alerts.go`
- [ ] Direct HTTP client per OpenWeatherMap API

### 7.3 Phase 3: Weather Tools (Non-MCP)

- [ ] Creare `internal/llm/tools/weather.go`
- [ ] Implementare direct API calls (NO MCP per ora)
- [ ] Supporto per OpenWeatherMap free tier
- [ ] Supporto fallback a Tomorrow.io

### 7.4 Phase 4: Integration & Testing

- [ ] Wire Weather Agency nel registry
- [ ] Test con query reali
- [ ] Verificare token usage vs MCP approach

---

## Weather API Options

### OpenWeatherMap (Recommended)

| Feature | Free Tier | Paid |
|---------|-----------|------|
| Current Weather | ✅ 1000 calls/day | ✅ |
| 5 Day/3 Hour Forecast | ✅ | ✅ |
| Historical Weather | ❌ | ✅ |
| UV Index | ❌ | ✅ |
| Air Pollution | ✅ | ✅ |

**API Key**: https://openweathermap.org/api

### Tomorrow.io

| Feature | Free Tier | Paid |
|---------|-----------|------|
| Current Weather | ✅ 500 calls/day | ✅ |
| Forecast | ✅ | ✅ |
| Historical | ✅ | ✅ |

**API Key**: https://www.tomorrow.io/

### Confronto

| Criteria | OpenWeatherMap | Tomorrow.io |
|----------|---------------|-------------|
| Free tier size | 1000/day | 500/day |
| Documentation | Good | Excellent |
| SDK availability | Yes | Yes |
| Air quality | Yes | Yes |

---

## Token Cost Analysis

### Direct API vs MCP

| Operation | Direct API | MCP |
|-----------|------------|-----|
| Tool description | ~50 tokens | ~200 tokens |
| Tool call overhead | ~30 tokens | ~100 tokens |
| Response parsing | ~20 tokens | ~50 tokens |
| **Total per call** | ~100 tokens | ~350 tokens |

**Per 1000 weather calls/mese:**
- Direct API: ~100,000 tokens
- MCP: ~350,000 tokens

**MCP ha senso solo se:**
1. Tool discovery dinamico è necessario
2. Enterprise governance richiede centralizzazione
3. Molti tool simili da gestire

---

## Deliverables

- [ ] Weather Agency funzionante
- [ ] 4 Weather skills (current, forecast, alerts, historical)
- [ ] Direct API integration (NO MCP)
- [ ] Test con OpenWeatherMap free tier
- [ ] Documentation su tool integration pattern

---

##验证 (Verification)

1. `go build ./...` - Must pass
2. `go test ./internal/aria/agency/weather/...` - Weather agency tests
3. Manual test: "What's the weather in Rome?"
4. Token usage comparison: Direct API vs MCP

---

## Next Steps (After POC)

Se POC successful, apply same pattern to:

1. **Knowledge Agency**: Direct Tavily/Brave search API calls (NO MCP)
2. **Creative Agency**: Direct document API calls
3. **Productivity Agency**: Direct Calendar API calls

MCP reserved for:
- Enterprise integrations (Slack, Jira)
- Tool discovery scenarios

---

## Files to Create

```
internal/aria/agency/weather.go           # Weather Agency
internal/aria/skill/weather_current.go    # Current weather skill
internal/aria/skill/weather_forecast.go   # Forecast skill
internal/aria/skill/weather_alerts.go    # Alerts skill
internal/llm/tools/weather.go            # Weather tool (direct API)
internal/aria/config/weather.go          # Weather config
```

---

## References

- [MCP vs APIs comparison](https://www.tinybird.co/blog/mcp-vs-apis-when-to-use-which-for-ai-agent-development)
- [Anthropic MCP benchmarks](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Tool calling patterns](https://martinfowler.com/articles/function-call-LLM.html)
