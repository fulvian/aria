// Package agency provides the Development Agency implementation.
package agency

import (
	"context"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/llm/agent"
	"github.com/fulvian/aria/internal/message"
	"github.com/fulvian/aria/internal/session"
)

// DevelopmentAgency is the development-focused agency.
type DevelopmentAgency struct {
	name        AgencyName
	domain      string
	description string
	state       AgencyState
	memory      *AgencyMemory

	// Lifecycle state
	status    AgencyStatus
	startTime time.Time
	pauseTime time.Time

	// Legacy agent bridge
	coderBridge AgentBridge

	// subscribed events
	sub *AgencyEventBroker
}

// NewDevelopmentAgency creates a new development agency.
func NewDevelopmentAgency(coderAgent agent.Service, sessions session.Service, messages message.Service) *DevelopmentAgency {
	return &DevelopmentAgency{
		name:        AgencyDevelopment,
		domain:      "development",
		description: "Software development, coding, DevOps, testing",
		state: AgencyState{
			AgencyID: AgencyDevelopment,
			Status:   "active",
			Metrics:  make(map[string]any),
		},
		memory:      NewAgencyMemory("development"),
		sub:         NewAgencyEventBroker(),
		coderBridge: NewCoderBridge(coderAgent, sessions, messages),
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

// Start starts the development agency.
func (a *DevelopmentAgency) Start(ctx context.Context) error {
	switch a.status {
	case AgencyStatusRunning:
		return fmt.Errorf("agency already running")
	case AgencyStatusPaused:
		return fmt.Errorf("agency is paused, use Resume instead")
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

// Stop stops the development agency.
func (a *DevelopmentAgency) Stop(ctx context.Context) error {
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

// Pause pauses the development agency.
func (a *DevelopmentAgency) Pause(ctx context.Context) error {
	if a.status == AgencyStatusStopped {
		return fmt.Errorf("cannot pause stopped agency")
	}
	if a.status == AgencyStatusPaused {
		return fmt.Errorf("agency already paused")
	}

	a.status = AgencyStatusPaused
	a.pauseTime = time.Now()

	a.sub.Publish(AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_paused",
		Payload:   map[string]any{"pause_time": a.pauseTime},
		Timestamp: time.Now(),
	})

	return nil
}

// Resume resumes the development agency.
func (a *DevelopmentAgency) Resume(ctx context.Context) error {
	if a.status == AgencyStatusStopped {
		return fmt.Errorf("cannot resume stopped agency, use Start instead")
	}
	if a.status == AgencyStatusRunning {
		return fmt.Errorf("agency already running")
	}

	a.status = AgencyStatusRunning
	a.pauseTime = time.Time{}

	a.sub.Publish(AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_resumed",
		Payload:   map[string]any{},
		Timestamp: time.Now(),
	})

	return nil
}

// Status returns the current agency status.
func (a *DevelopmentAgency) Status() AgencyStatus {
	return a.status
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

// CoderBridge wraps the legacy coder agent for ARIA.
type CoderBridge struct {
	// agent is the legacy coder agent service
	agent    agent.Service
	sessions session.Service
	messages message.Service
}

// NewCoderBridge creates a new CoderBridge.
func NewCoderBridge(agentService agent.Service, sessions session.Service, messages message.Service) *CoderBridge {
	return &CoderBridge{
		agent:    agentService,
		sessions: sessions,
		messages: messages,
	}
}

// RunTask runs the coder agent on a task by delegating to the legacy agent.
func (b *CoderBridge) RunTask(ctx context.Context, task Task) (map[string]any, error) {
	// Extract the prompt from task parameters
	prompt, _ := task.Parameters["prompt"].(string)
	if prompt == "" {
		prompt = task.Description
	}
	if prompt == "" {
		prompt = task.Name
	}

	if prompt == "" {
		return nil, fmt.Errorf("no prompt provided for task %s", task.ID)
	}

	// Create a session for this task
	sess, err := b.sessions.Create(ctx, "ARIA: "+truncateString(prompt, 50))
	if err != nil {
		return nil, fmt.Errorf("failed to create session: %w", err)
	}

	// Run the agent and collect the response
	events, err := b.agent.Run(ctx, sess.ID, prompt)
	if err != nil {
		return nil, fmt.Errorf("failed to start agent: %w", err)
	}

	// Collect the response from the event stream
	var responseContent string
	var agentErr error

	for event := range events {
		switch event.Type {
		case agent.AgentEventTypeResponse:
			responseContent = event.Message.Content().String()
		case agent.AgentEventTypeError:
			agentErr = event.Error
		}
	}

	if agentErr != nil {
		return nil, fmt.Errorf("agent error: %w", agentErr)
	}

	return map[string]any{
		"type":           "coder-task",
		"task_id":        task.ID,
		"session_id":     sess.ID,
		"prompt_preview": truncateString(prompt, 100),
		"response":       responseContent,
		"status":         "completed",
	}, nil
}

// truncateString truncates a string to maxLen characters.
func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}
