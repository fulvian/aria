// Package agency provides the Development Agency implementation.
package agency

import (
	"context"
	"encoding/json"
	"fmt"
	"time"
)

// DevelopmentAgency is the development-focused agency.
type DevelopmentAgency struct {
	name        AgencyName
	domain      string
	description string
	state       AgencyState
	memory      *AgencyMemory

	// Legacy agent bridge
	coderBridge AgentBridge

	// subscribed events
	sub *AgencyEventBroker
}

// NewDevelopmentAgency creates a new development agency.
func NewDevelopmentAgency() *DevelopmentAgency {
	return &DevelopmentAgency{
		name:        AgencyDevelopment,
		domain:      "development",
		description: "Software development, coding, DevOps, testing",
		state: AgencyState{
			AgencyID: AgencyDevelopment,
			Status:   "active",
			Metrics:  make(map[string]any),
		},
		memory: NewAgencyMemory("development"),
		sub:    NewAgencyEventBroker(),
	}
}

// Name returns the agency name.
func (a *DevelopmentAgency) Name() AgencyName {
	return a.name
}

// Domain returns the domain.
func (a *DevelopmentAgency) Domain() string {
	return a.domain
}

// Description returns the description.
func (a *DevelopmentAgency) Description() string {
	return a.description
}

// Agents returns the list of agent names.
func (a *DevelopmentAgency) Agents() []string {
	return []string{"coder", "reviewer", "architect"}
}

// GetAgent returns an agent by name.
func (a *DevelopmentAgency) GetAgent(name string) (any, error) {
	switch name {
	case "coder":
		return a.coderBridge, nil
	case "reviewer":
		return &ReviewerAgent{}, nil
	case "architect":
		return &ArchitectAgent{}, nil
	default:
		return nil, fmt.Errorf("agent not found: %s", name)
	}
}

// Execute executes a task in the development agency.
func (a *DevelopmentAgency) Execute(ctx context.Context, task Task) (Result, error) {
	start := time.Now()

	// Emit task started event
	a.sub.Publish(AgencyEvent{
		AgencyID: a.name,
		Type:     "task_started",
		Payload: map[string]any{
			"task_id":   task.ID,
			"task_name": task.Name,
		},
	})

	// Determine which agent to use based on task
	agentName := "coder"
	if len(task.Skills) > 0 {
		switch task.Skills[0] {
		case "code-review":
			agentName = "reviewer"
		case "system-design", "architecture":
			agentName = "architect"
		}
	}

	// Get the agent
	agent, err := a.GetAgent(agentName)
	if err != nil {
		return Result{
			TaskID:     task.ID,
			Success:    false,
			Error:      err.Error(),
			DurationMs: time.Since(start).Milliseconds(),
		}, err
	}

	// Execute based on agent type
	var result map[string]any
	switch ag := agent.(type) {
	case AgentBridge:
		result, err = ag.RunTask(ctx, task)
	case ReviewerAgent:
		result, err = ag.Review(ctx, task)
	case ArchitectAgent:
		result, err = ag.Design(ctx, task)
	default:
		return Result{
			TaskID:     task.ID,
			Success:    false,
			Error:      "unknown agent type",
			DurationMs: time.Since(start).Milliseconds(),
		}, fmt.Errorf("unknown agent type")
	}

	if err != nil {
		// Emit task failed event
		a.sub.Publish(AgencyEvent{
			AgencyID: a.name,
			Type:     "task_failed",
			Payload: map[string]any{
				"task_id": task.ID,
				"error":   err.Error(),
			},
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
		Payload: map[string]any{
			"task_id": task.ID,
			"result":  result,
		},
	})

	return Result{
		TaskID:     task.ID,
		Success:    true,
		Output:     result,
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// GetState returns the current state.
func (a *DevelopmentAgency) GetState() AgencyState {
	return a.state
}

// SaveState saves the agency state.
func (a *DevelopmentAgency) SaveState(state AgencyState) error {
	a.state = state
	return nil
}

// Memory returns the agency memory.
func (a *DevelopmentAgency) Memory() DomainMemory {
	return a.memory
}

// Subscribe returns a channel for receiving agency events.
func (a *DevelopmentAgency) Subscribe(ctx context.Context) <-chan AgencyEvent {
	return a.sub.Subscribe(ctx)
}

// AgencyEventBroker is a simple broker for agency events.
type AgencyEventBroker struct {
	ch chan AgencyEvent
}

// NewAgencyEventBroker creates a new agency event broker.
func NewAgencyEventBroker() *AgencyEventBroker {
	return &AgencyEventBroker{
		ch: make(chan AgencyEvent, 64),
	}
}

// Publish publishes an agency event.
func (b *AgencyEventBroker) Publish(event AgencyEvent) {
	select {
	case b.ch <- event:
	default:
		// Channel full, drop event
	}
}

// Subscribe returns a channel that receives agency events.
func (b *AgencyEventBroker) Subscribe(ctx context.Context) <-chan AgencyEvent {
	ch := make(chan AgencyEvent, 64)
	go func() {
		for {
			select {
			case <-ctx.Done():
				close(ch)
				return
			case event := <-b.ch:
				ch <- event
			}
		}
	}()
	return ch
}

// ReviewerAgent is a code review agent.
type ReviewerAgent struct{}

// Review performs a code review.
func (a *ReviewerAgent) Review(ctx context.Context, task Task) (map[string]any, error) {
	return map[string]any{
		"type":        "code-review",
		"task_id":     task.ID,
		"description": task.Description,
		"status":      "completed",
		"findings":    []map[string]any{},
	}, nil
}

// ArchitectAgent is a system architect agent.
type ArchitectAgent struct{}

// Design creates a system design.
func (a *ArchitectAgent) Design(ctx context.Context, task Task) (map[string]any, error) {
	return map[string]any{
		"type":        "architecture",
		"task_id":     task.ID,
		"description": task.Description,
		"status":      "completed",
		"design": map[string]any{
			"components": []string{},
		},
	}, nil
}

// AgencyMemory implements DomainMemory for the agency.
type AgencyMemory struct {
	domain      string
	experiences []map[string]any
}

// NewAgencyMemory creates a new agency memory.
func NewAgencyMemory(domain string) *AgencyMemory {
	return &AgencyMemory{
		domain:      domain,
		experiences: make([]map[string]any, 0),
	}
}

// GetContext returns relevant context for a query.
func (m *AgencyMemory) GetContext(ctx context.Context, query string) (map[string]any, error) {
	return map[string]any{
		"domain":             m.domain,
		"recent_experiences": m.experiences,
	}, nil
}

// AddExperience records a new experience.
func (m *AgencyMemory) AddExperience(ctx context.Context, exp map[string]any) error {
	m.experiences = append(m.experiences, exp)
	return nil
}

// GetRelevant returns relevant memories for a task.
func (m *AgencyMemory) GetRelevant(ctx context.Context, task Task) ([]map[string]any, error) {
	// Simple implementation - return all experiences for now
	return m.experiences, nil
}

// AgentBridge defines the interface for bridging to legacy agents.
type AgentBridge interface {
	RunTask(ctx context.Context, task Task) (map[string]any, error)
}

// CoderBridge wraps the legacy coder agent.
type CoderBridge struct {
	// TODO: Add reference to legacy internal/llm/agent.Service
	taskAgent any
}

// RunTask runs the coder agent on a task.
func (b *CoderBridge) RunTask(ctx context.Context, task Task) (map[string]any, error) {
	// Serialize task parameters
	params, err := json.Marshal(task.Parameters)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"type":      "coder-task",
		"task_id":   task.ID,
		"task_name": task.Name,
		"params":    string(params),
		"status":    "delegated_to_legacy",
	}, nil
}
