# ARIA Entity Creation Guide

**Data**: 2026-03-29  
**Version**: 1.0.0  
**Scopo**: Guida pratica per creare agencies, agents, skills e tools in ARIA

---

## Panoramica Architetturale

```
┌─────────────────────────────────────────────────────────────────┐
│                         ARIA LAYERS                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   Agency    │───▶│   Agent     │───▶│   Skill      │         │
│  │  (Domain)   │    │  (Task)     │    │  (Action)    │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                                      │                │
│         │              ┌─────────────┐         │                │
│         └─────────────▶│    Tool      │◀────────┘                │
│                        │ (Execution)  │                          │
│                        └─────────────┘                          │
│                              │                                  │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   Native    │    │ Direct API  │    │    MCP      │         │
│  │   Tool      │    │   Tool      │    │   Server    │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Tool Creation

I tool sono il livello più basso - eseguono chiamate concrete.

### 1.1 Tool Types

| Type | Token Cost | Use Case | Example |
|------|------------|----------|---------|
| **Native** | ~50/call | Core tools (bash, grep, edit) | `internal/llm/tools/bash.go` |
| **Direct API** | ~100/call | External services (weather, calendar) | `internal/llm/tools/weather.go` |
| **MCP** | ~350/call | Enterprise, dynamic discovery | External MCP servers |

### 1.2 Direct API Tool Template

```go
package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// TypeToolParams defines parameters for this tool.
type TypeToolParams struct {
	Param1 string `json:"param1"`
	Param2 int    `json:"param2,omitempty"`
}

type typeTool struct {
	client *http.Client
	apiKey string
}

const (
	TypeToolName        = "type-tool"
	typeToolDescription = `Description of what this tool does...`
)

func NewTypeTool(apiKey string) BaseTool {
	return &typeTool{
		client: &http.Client{Timeout: 30 * time.Second},
		apiKey: apiKey,
	}
}

func (t *typeTool) Info() ToolInfo {
	return ToolInfo{
		Name:        TypeToolName,
		Description: typeToolDescription,
		Parameters: map[string]any{
			"param1": map[string]any{
				"type":        "string",
				"description": "Description of param1",
			},
			"param2": map[string]any{
				"type":        "number",
				"description": "Optional parameter",
			},
		},
		Required: []string{"param1"},
	}
}

func (t *typeTool) Run(ctx context.Context, call ToolCall) (ToolResponse, error) {
	var params TypeToolParams
	if err := json.Unmarshal([]byte(call.Input), &params); err != nil {
		return NewTextErrorResponse("invalid parameters: " + err.Error()), nil
	}

	if params.Param1 == "" {
		return NewTextErrorResponse("param1 is required"), nil
	}

	// Build API request
	url := fmt.Sprintf("https://api.example.com/v1/resource?param=%s", params.Param1)
	
	data, err := t.doRequest(ctx, url)
	if err != nil {
		return NewTextErrorResponse("API error: " + err.Error()), nil
	}

	// Parse and format response
	var result map[string]any
	if err := json.Unmarshal(data, &result); err != nil {
		return NewTextErrorResponse("parse error: " + err.Error()), nil
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *typeTool) doRequest(ctx context.Context, url string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+t.apiKey)
	req.Header.Set("User-Agent", "aria-tool/1.0")

	resp, err := t.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	return io.ReadAll(resp.Body)
}
```

### 1.3 Native Tool Template

I native tool usano il codebase interno direttamente (no HTTP):

```go
package tools

import (
	"context"
	"encoding/json"
	"fmt"
)

type NativeToolParams struct {
	Input string `json:"input"`
}

type nativeTool struct{}

const (
	NativeToolName        = "native-tool"
	nativeToolDescription = `Native tool description...`
)

func NewNativeTool() BaseTool {
	return &nativeTool{}
}

func (t *nativeTool) Info() ToolInfo {
	return ToolInfo{
		Name:        NativeToolName,
		Description: nativeToolDescription,
		Parameters: map[string]any{
			"input": map[string]any{
				"type":        "string",
				"description": "Input description",
			},
		},
		Required: []string{"input"},
	}
}

func (t *nativeTool) Run(ctx context.Context, call ToolCall) (ToolResponse, error) {
	var params NativeToolParams
	if err := json.Unmarshal([]byte(call.Input), &params); err != nil {
		return NewTextErrorResponse("invalid parameters"), nil
	}

	if params.Input == "" {
		return NewTextErrorResponse("input is required"), nil
	}

	// Native implementation - direct code execution
	result := doSomething(params.Input)

	return NewTextResponse(result), nil
}
```

### 1.4 MCP Server Integration

Per MCP, non crei un tool locale - configuri una connessione MCP:

```go
// MCP servers are configured via environment variables
// No local tool file needed - MCP handles tool discovery automatically
```

**Configurazione MCP**:
```bash
# MCP server URL
ARIA_MCP_SERVER_URL="https://mcp.example.com"
ARIA_MCP_API_KEY="your-api-key"
```

---

## 2. Skill Creation

Le skills orchestrano i tool per compiere azioni specifiche.

### 2.1 Skill Structure

```
Skill
├── Name()          → SkillName (unique identifier)
├── Description()  → Human-readable description
├── RequiredTools() → []ToolName (tools needed)
├── RequiredMCPs() → []MCPName (MCPs needed)
├── Execute()      → SkillResult (main logic)
└── CanExecute()   → (bool, string) (readiness check)
```

### 2.2 Skill Template

```go
package skill

import (
	"context"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/llm/tools"
)

// MySkillName is the skill identifier.
const MySkillName SkillName = "my-skill"

// MySkill implements a skill that does X.
type MySkill struct {
	tool1 tools.BaseTool
	tool2 tools.BaseTool
}

// NewMySkill creates a new MySkill.
func NewMySkill(tool1APIKey, tool2APIKey string) *MySkill {
	return &MySkill{
		tool1: tools.NewTool1(tool1APIKey),
		tool2: tools.NewTool2(tool2APIKey),
	}
}

// Name returns the skill name.
func (s *MySkill) Name() SkillName {
	return MySkillName
}

// Description returns the skill description.
func (s *MySkill) Description() string {
	return "Description of what this skill does"
}

// RequiredTools returns the tools required by this skill.
func (s *MySkill) RequiredTools() []ToolName {
	return []ToolName{"tool1", "tool2"}
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *MySkill) RequiredMCPs() []MCPName {
	return []MCPName{} // No MCP needed for direct API tools
}

// Execute performs the skill action.
func (s *MySkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	steps := []SkillStep{
		{Name: "validate", Description: "Validating parameters", Status: "in_progress"},
	}

	// Extract inputs
	input1, ok := params.Input["input1"].(string)
	if !ok || input1 == "" {
		steps[0].Status = "failed"
		return SkillResult{
			Success: false,
			Error:   "input1 is required",
			Steps:   steps,
		}, fmt.Errorf("input1 is required")
	}
	steps[0].Status = "completed"

	// Step 1: Call first tool
	steps = append(steps, SkillStep{
		Name:        "step1",
		Description: "Calling first tool",
		Status:      "in_progress",
	})

	result1, err := s.tool1.Run(ctx, tools.ToolCall{
		ID:   params.TaskID,
		Name: "tool1",
		Input: toJSON(map[string]any{
			"input": input1,
		}),
	})
	steps[1].DurationMs = time.Since(start).Milliseconds()

	if err != nil {
		steps[1].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      err.Error(),
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, err
	}

	if result1.IsError {
		steps[1].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      result1.Content,
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, fmt.Errorf("tool1 error: %s", result1.Content)
	}
	steps[1].Status = "completed"

	// Step 2: Call second tool with result from first
	steps = append(steps, SkillStep{
		Name:        "step2",
		Description: "Processing result",
		Status:      "in_progress",
	})

	result2, err := s.tool2.Run(ctx, tools.ToolCall{
		ID:   params.TaskID,
		Name: "tool2",
		Input: toJSON(map[string]any{
			"data": result1.Content,
		}),
	})
	steps[2].DurationMs = time.Since(start).Milliseconds()

	if err != nil {
		steps[2].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      err.Error(),
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, err
	}

	steps[2].Status = "completed"

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"task_id":   params.TaskID,
			"result1":   result1.Content,
			"result2":   result2.Content,
			"summary":   "Operation completed successfully",
		},
		DurationMs: time.Since(start).Milliseconds(),
		Steps:      steps,
	}, nil
}

// CanExecute checks if the skill can execute.
func (s *MySkill) CanExecute(ctx context.Context) (bool, string) {
	return true, "MySkill is ready"
}

// toJSON converts a map to JSON string.
func toJSON(m map[string]any) string {
	b, _ := json.Marshal(m)
	return string(b)
}
```

### 2.3 Skill Constants (skill.go)

Aggiungi le costanti in `internal/aria/skill/skill.go`:

```go
// My skill constant
const (
	// ...
	SkillMySkill SkillName = "my-skill"
)
```

---

## 3. Agent Creation

Gli agenti sono bridge tra agency e skills/logica specifica.

### 3.1 Agent Pattern

```go
// MyAgentBridge implements agent logic for a specific task type.
type MyAgentBridge struct {
	skill1 *Skill1
	skill2 *Skill2
}

// NewMyAgentBridge creates a new MyAgentBridge.
func NewMyAgentBridge(skill1 *Skill1, skill2 *Skill2) *MyAgentBridge {
	return &MyAgentBridge{
		skill1: skill1,
		skill2: skill2,
	}
}

// DoTask executes a task using appropriate skills.
func (b *MyAgentBridge) DoTask(ctx context.Context, task Task) (map[string]any, error) {
	// Determine which skill to use
	skillName := task.Skills[0]

	// Execute based on skill
	switch skillName {
	case "skill1":
		result, err := b.skill1.Execute(ctx, SkillParams{
			TaskID: task.ID,
			Input:  task.Parameters,
		})
		if err != nil {
			return nil, err
		}
		return result.Output, nil

	case "skill2":
		result, err := b.skill2.Execute(ctx, SkillParams{
			TaskID: task.ID,
			Input:  task.Parameters,
		})
		if err != nil {
			return nil, err
		}
		return result.Output, nil

	default:
		return nil, fmt.Errorf("unsupported skill: %s", skillName)
	}
}
```

---

## 4. Agency Creation

Le agencies coordinano agenti per un dominio specifico.

### 4.1 Agency Structure

```
Agency
├── Name()          → AgencyName (unique identifier)
├── Domain()       → string (domain: "weather", "knowledge", etc.)
├── Description()   → string (human-readable)
├── Agents()       → []string (agent names)
├── GetAgent()     → any (get agent by name)
├── Execute()      → Result (main execution)
├── Lifecycle      → Start/Stop/Pause/Resume/Status
├── Subscribe()    → chan AgencyEvent (event subscription)
├── GetState()     → AgencyState (persistent state)
├── Memory()       → DomainMemory (agency-specific memory)
└── EventBroker   → internal pub/sub for events
```

### 4.2 Agency Template

```go
package agency

import (
	"context"
	"fmt"
	"time"
)

// MyAgencyName is the agency name constant.
const MyAgencyName AgencyName = "my-agency"

// MyAgency is the agency for my-domain tasks.
type MyAgency struct {
	name        AgencyName
	domain      string
	description string
	state       AgencyState
	memory      *AgencyMemory

	// Lifecycle state
	status    AgencyStatus
	startTime time.Time
	pauseTime time.Time

	// Agent bridge
	myBridge MyAgentBridge

	// Event subscription
	sub *AgencyEventBroker
}

// NewMyAgency creates a new MyAgency.
func NewMyAgency(someConfig Config) *MyAgency {
	return &MyAgency{
		name:        MyAgencyName,
		domain:      "my-domain",
		description: "My domain description",
		state: AgencyState{
			AgencyID: MyAgencyName,
			Status:   "active",
			Metrics:  make(map[string]any),
		},
		memory:   NewAgencyMemory("my-domain"),
		sub:      NewAgencyEventBroker(),
		myBridge: NewMyAgentBridge(someConfig),
	}
}

// Name returns the agency name.
func (a *MyAgency) Name() AgencyName { return a.name }

// Domain returns the domain.
func (a *MyAgency) Domain() string { return a.domain }

// Description returns the description.
func (a *MyAgency) Description() string { return a.description }

// Agents returns the list of agent names.
func (a *MyAgency) Agents() []string {
	return []string{"my-agent"}
}

// GetAgent returns an agent by name.
func (a *MyAgency) GetAgent(name string) (any, error) {
	switch name {
	case "my-agent":
		return a.myBridge, nil
	default:
		return nil, fmt.Errorf("agent not found: %s", name)
	}
}

// Execute executes a task in the agency.
func (a *MyAgency) Execute(ctx context.Context, task Task) (Result, error) {
	start := time.Now()

	// Emit task started event
	a.sub.Publish(AgencyEvent{
		AgencyID: a.name,
		Type:     "task_started",
		Payload:  map[string]any{"task_id": task.ID},
	})

	// Determine which skill/agent to use
	skillName := "default-skill"
	if len(task.Skills) > 0 {
		skillName = string(task.Skills[0])
	}

	// Execute via bridge
	result, err := a.myBridge.DoTask(ctx, task, skillName)
	if err != nil {
		a.sub.Publish(AgencyEvent{
			AgencyID: a.name,
			Type:     "task_failed",
			Payload:  map[string]any{"task_id": task.ID, "error": err.Error()},
		})
		return Result{
			TaskID:     task.ID,
			Success:    false,
			Error:      err.Error(),
			DurationMs: time.Since(start).Milliseconds(),
		}, err
	}

	// Emit task completed event
	a.sub.Publish(AgencyEvent{
		AgencyID: a.name,
		Type:     "task_completed",
		Payload:  map[string]any{"task_id": task.ID, "result": result},
	})

	return Result{
		TaskID:     task.ID,
		Success:    true,
		Output:     result,
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// GetState returns the current state.
func (a *MyAgency) GetState() AgencyState { return a.state }

// SaveState saves the agency state.
func (a *MyAgency) SaveState(state AgencyState) error {
	a.state = state
	return nil
}

// Memory returns the agency memory.
func (a *MyAgency) Memory() DomainMemory { return a.memory }

// Subscribe returns a channel for receiving agency events.
func (a *MyAgency) Subscribe(ctx context.Context) <-chan AgencyEvent {
	return a.sub.Subscribe(ctx)
}

// Start starts the agency.
func (a *MyAgency) Start(ctx context.Context) error {
	if a.status == AgencyStatusRunning {
		return fmt.Errorf("agency already running")
	}
	a.status = AgencyStatusRunning
	a.startTime = time.Now()
	a.sub.Publish(AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_started",
		Payload:   map[string]any{"start_time": a.startTime},
		Timestamp: time.Now(),
	})
	return nil
}

// Stop stops the agency.
func (a *MyAgency) Stop(ctx context.Context) error {
	if a.status == AgencyStatusStopped {
		return fmt.Errorf("agency already stopped")
	}
	a.status = AgencyStatusStopped
	a.pauseTime = time.Time{}
	a.sub.Publish(AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_stopped",
		Payload:   map[string]any{},
		Timestamp: time.Now(),
	})
	return nil
}

// Pause pauses the agency.
func (a *MyAgency) Pause(ctx context.Context) error {
	if a.status != AgencyStatusRunning {
		return fmt.Errorf("cannot pause: not running")
	}
	a.status = AgencyStatusPaused
	a.pauseTime = time.Now()
	return nil
}

// Resume resumes the agency.
func (a *MyAgency) Resume(ctx context.Context) error {
	if a.status != AgencyStatusPaused {
		return fmt.Errorf("cannot resume: not paused")
	}
	a.status = AgencyStatusRunning
	a.pauseTime = time.Time{}
	return nil
}

// Status returns the current agency status.
func (a *MyAgency) Status() AgencyStatus { return a.status }
```

### 4.3 Agency Name Constant (agency.go)

Aggiungi in `internal/aria/agency/agency.go`:

```go
const (
	// ... existing constants
	AgencyMyDomain AgencyName = "my-agency"
)
```

---

## 5. Configuration

### 5.1 Config Structure

```go
// Config in internal/aria/config/config.go

type Config struct {
	Enabled bool
	Agencies AgenciesConfig
	// ...
}

type AgenciesConfig struct {
	MyAgency MyAgencyConfig
}

type MyAgencyConfig struct {
	Enabled bool
	// Add agency-specific config fields
}
```

### 5.2 Dedicated Config File (optional)

Per config complesse, crea `internal/aria/config/myagency.go`:

```go
package config

import "os"

type MyAgencyConfig struct {
	Enabled   bool
	APIKey    string
	Endpoint  string
}

func DefaultMyAgencyConfig() MyAgencyConfig {
	return MyAgencyConfig{
		Enabled:  getEnvBool("ARIA_MYAGENCY_ENABLED", true),
		APIKey:   os.Getenv("ARIA_MYAGENCY_API_KEY"),
		Endpoint: getEnv("ARIA_MYAGENCY_ENDPOINT", "https://api.example.com"),
	}
}

func (c MyAgencyConfig) IsConfigured() bool {
	return c.APIKey != ""
}
```

---

## 6. Integration

### 6.1 App Integration (internal/app/aria_integration.go)

```go
// 1. Add to ARIAComponents struct
type ARIAComponents struct {
	// ... existing fields
	MyAgency *agency.MyAgency
}

// 2. Initialize in initARIA()
func (app *App) initARIA(ctx context.Context) error {
	// ... existing initialization ...

	// Initialize my agency
	myCfg := myConfig.DefaultMyAgencyConfig()
	var myAgency *agency.MyAgency
	if ariaCfg.Agencies.MyAgency.Enabled && myCfg.IsConfigured() {
		myAgency = agency.NewMyAgency(myCfg)
		logging.Info("Initialized my agency", "name", myAgency.Name())
	}

	// Register with orchestrator
	if myAgency != nil {
		orchestrator.RegisterAgency(myAgency)
	}

	// Store in components
	app.ARIA = &ARIAComponents{
		// ... existing fields
		MyAgency: myAgency,
	}

	return nil
}
```

---

## 7. Environment Variables

### 7.1 Standard Pattern

```bash
# Global enable
ARIA_ENABLED=true

# Agency enable
ARIA_AGENCIES_MYAGENCY_ENABLED=true

# Agency-specific config
ARIA_MYAGENCY_API_KEY="your-api-key"
ARIA_MYAGENCY_ENDPOINT="https://api.example.com"
```

---

## 8. Tool Selection Decision Matrix

| Scenario | Tool Type | Reason |
|----------|-----------|--------|
| bash, grep, edit, glob | Native | Fixed interface, already implemented |
| Weather, Calendar, Search | Direct API | Known endpoints, no discovery needed |
| Slack, Jira, Enterprise tools | MCP | Tool discovery, enterprise governance |
| High-volume calls | Direct API | MCP overhead too expensive |

### 8.1 Token Cost Comparison

| Pattern | Tokens/Call | 1000 Calls | Best For |
|---------|-------------|------------|----------|
| Native Tool | ~50 | 50K | Core tools |
| Direct API | ~100 | 100K | External services |
| MCP | ~350 | 350K | Enterprise, dynamic |

### 8.2 When to Use MCP

**MCP IS appropriate when:**
- Enterprise governance required
- Dynamic tool discovery needed
- Multi-agent communication
- Community plugins

**MCP is NOT appropriate when:**
- Fixed APIs (weather, calendar)
- High-volume tool calls
- Simple integrations

---

## 9. Testing Checklist

```bash
# Build verification
go build ./...

# Vet check
go vet ./...

# Unit tests
go test ./internal/aria/...

# Manual test
# 1. Set env vars
export ARIA_ENABLED=true
export ARIA_AGENCIES_MYAGENCY_ENABLED=true
export ARIA_MYAGENCY_API_KEY="test-key"

# 2. Run app
go run ./main.go -p "My test prompt"
```

---

## 10. File Checklist

Per ogni nuova entity, assicurati di:

### Tool
- [ ] `internal/llm/tools/mytool.go` - Tool implementation
- [ ] Test file `mytool_test.go` - Unit tests

### Skill
- [ ] `internal/aria/skill/my_skill.go` - Skill implementation
- [ ] `internal/aria/skill/skill.go` - Add SkillName constant

### Agent
- [ ] Bridge implementation in agency file or separate
- [ ] `RunTask()` or similar method

### Agency
- [ ] `internal/aria/agency/myagency.go` - Agency implementation
- [ ] `internal/aria/agency/agency.go` - Add AgencyName constant
- [ ] `internal/aria/config/config.go` - Add config struct

### Config
- [ ] `internal/aria/config/myagency.go` - Dedicated config (if complex)
- [ ] Update `Load()` in config.go

### Integration
- [ ] `internal/app/aria_integration.go` - Wire up initialization
- [ ] Add to ARIAComponents struct
- [ ] Register with orchestrator

---

## 11. Multi-Agent Architecture Patterns (2026)

Le agenzie moderne seguono pattern architetturali definiti per orchestrare agenti specializzati.

### 11.1 Hierarchical Agency Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           KNOWLEDGE AGENCY                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        SUPERVISOR                                 │    │
│  │  - Task classification    - Agent routing                       │    │
│  │  - Capability matching    - Load balancing                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                      │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │                     AGENT REGISTRY                                 │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │  │
│  │  │WebSearch │ │Academic  │ │  News    │ │  Code    │ │Historical│ │  │
│  │  │  Agent   │ │  Agent   │ │  Agent   │ │Research  │ │  Agent │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │                    WORKFLOW ENGINE                                │  │
│  │  • Sequential execution     • Parallel execution                  │  │
│  │  • Fallback chains           • Retry with backoff                   │  │
│  │  • Result synthesis          • State machine                      │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Component Responsibilities

| Componente | Responsabilità |
|------------|----------------|
| **Supervisor** | Classifica task, seleziona agenti basandosi su capabilities |
| **Agent Registry** | Mantiene registro agenti con categorie, skills, descrizioni |
| **Workflow Engine** | Orchestra execution con retry, fallback, parallelismo |
| **Task State Machine** | Gestisce lifecycle task (pending→running→completed/failed) |
| **Result Synthesizer** | Aggrega risultati da più agenti, deduplica, rank |
| **Event Broker** | Pub/sub per eventi agency (task_started, task_completed) |

### 11.3 Task State Machine

```
                    ┌─────────────┐
                    │   PENDING   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
            ┌───────│ VALIDATING  │───────┐
            │       └─────────────┘       │
            │ (validation failed)         │ (validation passed)
            ▼                             ▼
    ┌───────────────┐           ┌──────┴────────┐
    │    FAILED     │           │    RUNNING    │
    └───────────────┘           └───────┬───────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
            ┌───────▼───────┐   ┌───────▼───────┐   ┌────────▼────────┐
            │WAITING_FALLBACK│   │ SYNTHESIZING  │   │    COMPLETED     │
            └───────────────┘   └───────────────┘   └─────────────────┘
```

### 11.4 Execution Modes

```go
// Modalità di esecuzione workflow
const (
    ModeSequential ExecutionMode = "sequential" // Uno dopo l'altro
    ModeParallel   ExecutionMode = "parallel"   // Concurrently
    ModeFallback   ExecutionMode = "fallback"  // Try until success
    ModeFanOut     ExecutionMode = "fan_out"   // All agents, synthesize
)
```

### 11.5 Agent Registration Pattern

```go
// Registrazione agenti con capabilities
registry.Register(&RegisteredAgent{
    Name:        AgentWebSearch,
    Category:    CategoryWebSearch,
    Description: "Handles general web search using Tavily, Brave, Wikipedia",
    Skills:      []string{"web-research", "fact-check"},
    Executor:    NewWebSearchAgent(cfg),
})
```

### 11.6 Routing Logic

```go
// Il Supervisor classifica il task e seleziona l'agente appropriato
func (r *TaskRouter) classifyTask(task contracts.Task) TaskCategory {
    // 1. Check task skills first
    // 2. Check keywords in description
    // 3. Fallback to general category
    
    switch {
    case containsAny(desc, "arxiv", "pubmed", "academic"):
        return CategoryAcademic
    case containsAny(desc, "news", "headlines"):
        return CategoryNews
    case containsAny(desc, "code", "github", "api docs"):
        return CategoryCode
    // ... etc
    }
}
```

### 11.7 Files Created for KnowledgeAgency

```
internal/aria/agency/
├── knowledge.go              # Main agency with full integration
├── knowledge_supervisor.go    # Task routing and classification
├── knowledge_execution.go     # Workflow engine
├── knowledge_task_state.go   # Task state machine
├── knowledge_synthesis.go     # Result aggregation
├── knowledge_agents.go       # 5 specialized agents
└── knowledge_test.go         # Comprehensive tests
```

---

## 12. Testing Checklist

### 12.1 Unit Tests

```bash
# Test individual components
go test ./internal/aria/agency/... -v -run TestTaskStateMachine
go test ./internal/aria/agency/... -v -run TestAgentRegistry
go test ./internal/aria/agency/... -v -run TestResultSynthesizer

# Test integration
go test ./internal/aria/agency/... -v -run TestKnowledgeAgency

# Full test suite
go test ./internal/aria/agency/...
```

### 12.2 Test Coverage Areas

| Area | What to Test |
|------|--------------|
| **TaskRouter** | Classification logic, fallback routing |
| **AgentRegistry** | Registration, retrieval, category filtering |
| **TaskStateMachine** | Valid transitions, history tracking |
| **WorkflowEngine** | Sequential, parallel, fallback execution |
| **ResultSynthesizer** | Deduplication, ranking, merging |
| **KnowledgeAgency** | Full execution pipeline, lifecycle |

---

## 13. Example: Weather Agency (Reference)

La Weather Agency è un esempio completo di implementazione:

```
internal/
├── llm/tools/
│   └── weather.go          # Direct API tool
├── aria/
│   ├── config/
│   │   ├── config.go      # WeatherAgencyConfig
│   │   └── weather.go     # WeatherConfig
│   ├── skill/
│   │   ├── weather_current.go
│   │   ├── weather_forecast.go
│   │   └── weather_alerts.go
│   └── agency/
│       └── weather.go     # WeatherAgency + WeatherBridge
```

Vedi i file reali per implementazione di riferimento.
