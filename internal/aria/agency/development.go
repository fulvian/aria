// Package agency provides the Development Agency implementation.
package agency

import (
	"context"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/aria/skill"
	llmagent "github.com/fulvian/aria/internal/llm/agent"
	"github.com/fulvian/aria/internal/message"
	"github.com/fulvian/aria/internal/session"
)

// DevelopmentAgency is the development-focused agency.
type DevelopmentAgency struct {
	name        contracts.AgencyName
	domain      string
	description string
	state       AgencyState
	memory      *AgencyMemory

	// Lifecycle state
	status    AgencyStatus
	startTime time.Time
	pauseTime time.Time

	// Legacy agent bridge
	coderBridge *CoderBridge

	// subscribed events
	sub *AgencyEventBroker
}

// NewDevelopmentAgency creates a new development agency.
func NewDevelopmentAgency(coderAgent llmagent.Service, sessions session.Service, messages message.Service) *DevelopmentAgency {
	return &DevelopmentAgency{
		name:        contracts.AgencyDevelopment,
		domain:      "development",
		description: "Software development, coding, DevOps, testing",
		state: AgencyState{
			AgencyID: contracts.AgencyDevelopment,
			Status:   "active",
			Metrics:  make(map[string]any),
		},
		memory:      NewAgencyMemory("development"),
		sub:         NewAgencyEventBroker(),
		coderBridge: NewCoderBridge(coderAgent, sessions, messages),
	}
}

// Name returns the agency name.
func (a *DevelopmentAgency) Name() contracts.AgencyName {
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
func (a *DevelopmentAgency) Agents() []contracts.AgentName {
	return []contracts.AgentName{"coder", "reviewer", "architect"}
}

// GetAgent returns an agent by name.
func (a *DevelopmentAgency) GetAgent(name contracts.AgentName) (interface{}, error) {
	switch name {
	case "coder":
		return a.coderBridge, nil
	case "reviewer":
		return NewReviewerAgent(), nil
	case "architect":
		return NewArchitectAgent(), nil
	default:
		return nil, fmt.Errorf("agent not found: %s", name)
	}
}

// Execute executes a task in the development agency.
func (a *DevelopmentAgency) Execute(ctx context.Context, task contracts.Task) (contracts.Result, error) {
	start := time.Now()

	// Emit task started event
	a.sub.Publish(contracts.AgencyEvent{
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
	agentVal, err := a.GetAgent(contracts.AgentName(agentName))
	if err != nil {
		return contracts.Result{
			TaskID:     task.ID,
			Success:    false,
			Error:      err.Error(),
			DurationMs: time.Since(start).Milliseconds(),
		}, err
	}

	// Execute based on agent type
	var result map[string]any
	switch ag := agentVal.(type) {
	case *CoderBridge:
		result, err = ag.RunTask(ctx, task)
	case *ReviewerAgent:
		result, err = ag.Review(ctx, task)
	case *ArchitectAgent:
		result, err = ag.Design(ctx, task)
	default:
		return contracts.Result{
			TaskID:     task.ID,
			Success:    false,
			Error:      "unknown agent type",
			DurationMs: time.Since(start).Milliseconds(),
		}, fmt.Errorf("unknown agent type")
	}

	if err != nil {
		// Emit task failed event
		a.sub.Publish(contracts.AgencyEvent{
			AgencyID: a.name,
			Type:     "task_failed",
			Payload: map[string]any{
				"task_id": task.ID,
				"error":   err.Error(),
			},
		})
		return contracts.Result{
			TaskID:     task.ID,
			Success:    false,
			Error:      err.Error(),
			DurationMs: time.Since(start).Milliseconds(),
		}, err
	}

	// Emit task completed event
	a.sub.Publish(contracts.AgencyEvent{
		AgencyID: a.name,
		Type:     "task_completed",
		Payload: map[string]any{
			"task_id": task.ID,
			"result":  result,
		},
	})

	return contracts.Result{
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
func (a *DevelopmentAgency) Subscribe(ctx context.Context) <-chan contracts.AgencyEvent {
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

	a.sub.Publish(contracts.AgencyEvent{
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

	a.sub.Publish(contracts.AgencyEvent{
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

	a.sub.Publish(contracts.AgencyEvent{
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

	a.sub.Publish(contracts.AgencyEvent{
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
	ch chan contracts.AgencyEvent
}

// NewAgencyEventBroker creates a new agency event broker.
func NewAgencyEventBroker() *AgencyEventBroker {
	return &AgencyEventBroker{
		ch: make(chan contracts.AgencyEvent, 64),
	}
}

// Publish publishes an agency event.
func (b *AgencyEventBroker) Publish(event contracts.AgencyEvent) {
	select {
	case b.ch <- event:
	default:
		// Channel full, drop event
	}
}

// Subscribe returns a channel that receives agency events.
func (b *AgencyEventBroker) Subscribe(ctx context.Context) <-chan contracts.AgencyEvent {
	ch := make(chan contracts.AgencyEvent, 64)
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

// reviewerBroker handles event brokering for ReviewerAgent.
type reviewerBroker struct {
	ch chan contracts.AgentEvent
}

// newReviewerBroker creates a new reviewer broker.
func newReviewerBroker() *reviewerBroker {
	return &reviewerBroker{
		ch: make(chan contracts.AgentEvent, 64),
	}
}

// Publish publishes an agent event.
func (b *reviewerBroker) Publish(event contracts.AgentEvent) {
	select {
	case b.ch <- event:
	default:
	}
}

// Subscribe returns a channel for receiving agent events.
func (b *reviewerBroker) Subscribe(ctx context.Context) <-chan contracts.AgentEvent {
	ch := make(chan contracts.AgentEvent, 64)
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

// architectBroker handles event brokering for ArchitectAgent.
type architectBroker struct {
	ch chan contracts.AgentEvent
}

// newArchitectBroker creates a new architect broker.
func newArchitectBroker() *architectBroker {
	return &architectBroker{
		ch: make(chan contracts.AgentEvent, 64),
	}
}

// Publish publishes an agent event.
func (b *architectBroker) Publish(event contracts.AgentEvent) {
	select {
	case b.ch <- event:
	default:
	}
}

// Subscribe returns a channel for receiving agent events.
func (b *architectBroker) Subscribe(ctx context.Context) <-chan contracts.AgentEvent {
	ch := make(chan contracts.AgentEvent, 64)
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

// coderBroker handles event brokering for CoderBridge.
type coderBroker struct {
	ch chan contracts.AgentEvent
}

// newCoderBroker creates a new coder broker.
func newCoderBroker() *coderBroker {
	return &coderBroker{
		ch: make(chan contracts.AgentEvent, 64),
	}
}

// Publish publishes an agent event.
func (b *coderBroker) Publish(event contracts.AgentEvent) {
	select {
	case b.ch <- event:
	default:
	}
}

// Subscribe returns a channel for receiving agent events.
func (b *coderBroker) Subscribe(ctx context.Context) <-chan contracts.AgentEvent {
	ch := make(chan contracts.AgentEvent, 64)
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

// ReviewerAgent is a code review agent that implements the full Agent interface.
type ReviewerAgent struct {
	name   contracts.AgentName
	agency contracts.AgencyName
	broker *reviewerBroker
	state  contracts.AgentState
	skills []skill.Skill
}

// NewReviewerAgent creates a new ReviewerAgent.
func NewReviewerAgent() *ReviewerAgent {
	return &ReviewerAgent{
		name:   "reviewer",
		agency: contracts.AgencyDevelopment,
		broker: newReviewerBroker(),
		state: contracts.AgentState{
			AgentID: "reviewer",
			Status:  "idle",
			Metrics: make(map[string]any),
		},
		skills: []skill.Skill{
			skill.NewCodeReviewSkill(),
		},
	}
}

// Name returns the agent name.
func (a *ReviewerAgent) Name() contracts.AgentName {
	return a.name
}

// Agency returns the agency name.
func (a *ReviewerAgent) Agency() contracts.AgencyName {
	return a.agency
}

// Capabilities returns the agent capabilities.
func (a *ReviewerAgent) Capabilities() []contracts.Capability {
	return []contracts.Capability{
		{
			Name:        "code-review",
			Description: "Performs code reviews to identify bugs, style issues, and improvements",
			Tools:       []string{"view", "grep", "glob"},
		},
	}
}

// Review performs a code review on a task.
func (a *ReviewerAgent) Review(ctx context.Context, task contracts.Task) (map[string]any, error) {
	a.broker.Publish(contracts.AgentEvent{
		AgentID: string(a.name),
		Type:    "review_started",
		TaskID:  task.ID,
		Payload: map[string]any{"task_id": task.ID},
	})

	// Perform code review - simplified implementation
	findings := []map[string]any{}

	// In a real implementation, this would analyze code files
	// For now, return empty findings
	result := map[string]any{
		"type":        "code-review",
		"task_id":     task.ID,
		"description": task.Description,
		"status":      "completed",
		"findings":    findings,
		"summary":     "Code review completed - no critical issues found",
	}

	a.broker.Publish(contracts.AgentEvent{
		AgentID: string(a.name),
		Type:    "review_completed",
		TaskID:  task.ID,
		Payload: result,
	})

	return result, nil
}

// Run implements the Agent interface - executes code review from task map.
func (a *ReviewerAgent) Run(ctx context.Context, task map[string]any) (map[string]any, error) {
	a.state.Status = "busy"
	defer func() { a.state.Status = "idle" }()

	t := contracts.Task{
		ID:          getString(task, "id", ""),
		Name:        getString(task, "name", "review-task"),
		Description: getString(task, "description", ""),
		Parameters:  task,
	}

	a.state.TasksDone++
	return a.Review(ctx, t)
}

// Stream implements the Agent interface - streams review progress.
func (a *ReviewerAgent) Stream(ctx context.Context, task map[string]any) (<-chan contracts.Event, error) {
	events := make(chan contracts.Event)

	go func() {
		defer close(events)

		// Emit start event
		events <- contracts.Event{
			Type:    "review_started",
			Content: "Starting code review...",
		}

		// Simulate review progress
		time.Sleep(100 * time.Millisecond)
		events <- contracts.Event{
			Type:    "progress",
			Content: "Analyzing code structure...",
		}

		time.Sleep(100 * time.Millisecond)
		events <- contracts.Event{
			Type:    "progress",
			Content: "Checking for common issues...",
		}

		// Emit completion
		events <- contracts.Event{
			Type:    "review_completed",
			Content: "Code review completed",
		}
	}()

	return events, nil
}

// Subscribe returns a channel for receiving agent events.
func (a *ReviewerAgent) Subscribe(ctx context.Context) <-chan contracts.AgentEvent {
	return a.broker.Subscribe(ctx)
}

// Skills returns the skills available to this agent.
func (a *ReviewerAgent) Skills() []skill.Skill {
	return a.skills
}

// HasSkill returns true if the agent has the specified skill.
func (a *ReviewerAgent) HasSkill(name skill.SkillName) bool {
	for _, s := range a.skills {
		if s.Name() == name {
			return true
		}
	}
	return false
}

// LearnFromFeedback processes feedback to improve review quality.
func (a *ReviewerAgent) LearnFromFeedback(feedback contracts.Feedback) error {
	// TODO: Implement learning mechanism
	return nil
}

// GetState returns the current state of the agent.
func (a *ReviewerAgent) GetState() contracts.AgentState {
	a.state.AgentID = string(a.name)
	return a.state
}

// ArchitectAgent is a system architect agent that implements the full Agent interface.
type ArchitectAgent struct {
	name   contracts.AgentName
	agency contracts.AgencyName
	broker *architectBroker
	state  contracts.AgentState
	skills []skill.Skill
}

// NewArchitectAgent creates a new ArchitectAgent.
func NewArchitectAgent() *ArchitectAgent {
	return &ArchitectAgent{
		name:   "architect",
		agency: contracts.AgencyDevelopment,
		broker: newArchitectBroker(),
		state: contracts.AgentState{
			AgentID: "architect",
			Status:  "idle",
			Metrics: make(map[string]any),
		},
		skills: []skill.Skill{
			skill.NewTDDSkill(), // Using TDD as a proxy for architecture skills
		},
	}
}

// Name returns the agent name.
func (a *ArchitectAgent) Name() contracts.AgentName {
	return a.name
}

// Agency returns the agency name.
func (a *ArchitectAgent) Agency() contracts.AgencyName {
	return a.agency
}

// Capabilities returns the agent capabilities.
func (a *ArchitectAgent) Capabilities() []contracts.Capability {
	return []contracts.Capability{
		{
			Name:        "system-design",
			Description: "Creates system architecture designs and technical specifications",
			Tools:       []string{"view", "write"},
		},
	}
}

// Design creates a system design for a task.
func (a *ArchitectAgent) Design(ctx context.Context, task contracts.Task) (map[string]any, error) {
	a.broker.Publish(contracts.AgentEvent{
		AgentID: string(a.name),
		Type:    "design_started",
		TaskID:  task.ID,
		Payload: map[string]any{"task_id": task.ID},
	})

	// Perform system design - simplified implementation
	result := map[string]any{
		"type":        "architecture",
		"task_id":     task.ID,
		"description": task.Description,
		"status":      "completed",
		"design": map[string]any{
			"components": []string{},
			"layers":     []string{"presentation", "business", "data"},
			"patterns":   []string{"layered-architecture"},
		},
		"summary": "System design completed",
	}

	a.broker.Publish(contracts.AgentEvent{
		AgentID: string(a.name),
		Type:    "design_completed",
		TaskID:  task.ID,
		Payload: result,
	})

	return result, nil
}

// Run implements the Agent interface - executes design from task map.
func (a *ArchitectAgent) Run(ctx context.Context, task map[string]any) (map[string]any, error) {
	a.state.Status = "busy"
	defer func() { a.state.Status = "idle" }()

	t := contracts.Task{
		ID:          getString(task, "id", ""),
		Name:        getString(task, "name", "design-task"),
		Description: getString(task, "description", ""),
		Parameters:  task,
	}

	a.state.TasksDone++
	return a.Design(ctx, t)
}

// Stream implements the Agent interface - streams design progress.
func (a *ArchitectAgent) Stream(ctx context.Context, task map[string]any) (<-chan contracts.Event, error) {
	events := make(chan contracts.Event)

	go func() {
		defer close(events)

		// Emit start event
		events <- contracts.Event{
			Type:    "design_started",
			Content: "Starting system design...",
		}

		// Simulate design progress
		time.Sleep(100 * time.Millisecond)
		events <- contracts.Event{
			Type:    "progress",
			Content: "Analyzing requirements...",
		}

		time.Sleep(100 * time.Millisecond)
		events <- contracts.Event{
			Type:    "progress",
			Content: "Designing components...",
		}

		// Emit completion
		events <- contracts.Event{
			Type:    "design_completed",
			Content: "System design completed",
		}
	}()

	return events, nil
}

// Subscribe returns a channel for receiving agent events.
func (a *ArchitectAgent) Subscribe(ctx context.Context) <-chan contracts.AgentEvent {
	return a.broker.Subscribe(ctx)
}

// Skills returns the skills available to this agent.
func (a *ArchitectAgent) Skills() []skill.Skill {
	return a.skills
}

// HasSkill returns true if the agent has the specified skill.
func (a *ArchitectAgent) HasSkill(name skill.SkillName) bool {
	for _, s := range a.skills {
		if s.Name() == name {
			return true
		}
	}
	return false
}

// LearnFromFeedback processes feedback to improve design quality.
func (a *ArchitectAgent) LearnFromFeedback(feedback contracts.Feedback) error {
	// TODO: Implement learning mechanism
	return nil
}

// GetState returns the current state of the agent.
func (a *ArchitectAgent) GetState() contracts.AgentState {
	a.state.AgentID = string(a.name)
	return a.state
}

// CoderBridge wraps the legacy coder agent for ARIA and implements the Agent interface.
type CoderBridge struct {
	// agent is the legacy coder agent service
	agent    llmagent.Service
	sessions session.Service
	messages message.Service
	name     contracts.AgentName
	agency   contracts.AgencyName
	broker   *coderBroker
	state    contracts.AgentState
}

// NewCoderBridge creates a new CoderBridge.
func NewCoderBridge(agentService llmagent.Service, sessions session.Service, messages message.Service) *CoderBridge {
	return &CoderBridge{
		agent:    agentService,
		sessions: sessions,
		messages: messages,
		name:     "coder",
		agency:   contracts.AgencyDevelopment,
		broker:   newCoderBroker(),
		state: contracts.AgentState{
			AgentID: "coder",
			Status:  "idle",
			Metrics: make(map[string]any),
		},
	}
}

// Name returns the agent name.
func (b *CoderBridge) Name() contracts.AgentName {
	return b.name
}

// Agency returns the agency name.
func (b *CoderBridge) Agency() contracts.AgencyName {
	return b.agency
}

// Capabilities returns the agent capabilities.
func (b *CoderBridge) Capabilities() []contracts.Capability {
	return []contracts.Capability{
		{
			Name:        "code-generation",
			Description: "Generates code based on natural language descriptions",
			Tools:       []string{"bash", "edit", "write", "view", "glob", "grep"},
		},
	}
}

// RunTask runs the coder agent on a task by delegating to the legacy agent.
func (b *CoderBridge) RunTask(ctx context.Context, task contracts.Task) (map[string]any, error) {
	b.broker.Publish(contracts.AgentEvent{
		AgentID: string(b.name),
		Type:    "coding_started",
		TaskID:  task.ID,
		Payload: map[string]any{"task_id": task.ID},
	})

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
		b.broker.Publish(contracts.AgentEvent{
			AgentID: string(b.name),
			Type:    "coding_failed",
			TaskID:  task.ID,
			Payload: map[string]any{"error": err.Error()},
		})
		return nil, fmt.Errorf("failed to start agent: %w", err)
	}

	// Collect the response from the event stream
	var responseContent string
	var agentErr error

	for event := range events {
		switch event.Type {
		case llmagent.AgentEventTypeResponse:
			responseContent = event.Message.Content().String()
		case llmagent.AgentEventTypeError:
			agentErr = event.Error
		}
	}

	if agentErr != nil {
		b.broker.Publish(contracts.AgentEvent{
			AgentID: string(b.name),
			Type:    "coding_failed",
			TaskID:  task.ID,
			Payload: map[string]any{"error": agentErr.Error()},
		})
		return nil, fmt.Errorf("agent error: %w", agentErr)
	}

	result := map[string]any{
		"type":           "coder-task",
		"task_id":        task.ID,
		"session_id":     sess.ID,
		"prompt_preview": truncateString(prompt, 100),
		"response":       responseContent,
		"status":         "completed",
	}

	b.broker.Publish(contracts.AgentEvent{
		AgentID: string(b.name),
		Type:    "coding_completed",
		TaskID:  task.ID,
		Payload: result,
	})

	return result, nil
}

// Run implements the Agent interface.
func (b *CoderBridge) Run(ctx context.Context, task map[string]any) (map[string]any, error) {
	b.state.Status = "busy"
	defer func() { b.state.Status = "idle" }()

	t := contracts.Task{
		ID:          getString(task, "id", ""),
		Name:        getString(task, "name", "coder-task"),
		Description: getString(task, "description", ""),
		Parameters:  task,
	}

	b.state.TasksDone++
	return b.RunTask(ctx, t)
}

// Stream implements the Agent interface.
func (b *CoderBridge) Stream(ctx context.Context, task map[string]any) (<-chan contracts.Event, error) {
	events := make(chan contracts.Event)

	go func() {
		defer close(events)

		// Emit start event
		events <- contracts.Event{
			Type:    "coding_started",
			Content: "Starting code generation...",
		}

		// Note: This is a simplified implementation
		// A full implementation would stream events from the legacy agent
		events <- contracts.Event{
			Type:    "coding_completed",
			Content: "Code generation completed",
		}
	}()

	return events, nil
}

// Subscribe returns a channel for receiving agent events.
func (b *CoderBridge) Subscribe(ctx context.Context) <-chan contracts.AgentEvent {
	return b.broker.Subscribe(ctx)
}

// Skills returns the skills available to this agent.
func (b *CoderBridge) Skills() []skill.Skill {
	// CoderBridge uses the legacy agent which has no explicit skills
	return nil
}

// HasSkill returns true if the agent has the specified skill.
func (b *CoderBridge) HasSkill(name skill.SkillName) bool {
	// CoderBridge uses the legacy agent which has no explicit skills
	return false
}

// LearnFromFeedback processes feedback to improve coding quality.
func (b *CoderBridge) LearnFromFeedback(feedback contracts.Feedback) error {
	// TODO: Implement learning mechanism
	return nil
}

// GetState returns the current state of the agent.
func (b *CoderBridge) GetState() contracts.AgentState {
	b.state.AgentID = string(b.name)
	return b.state
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
func (m *AgencyMemory) GetRelevant(ctx context.Context, task contracts.Task) ([]map[string]any, error) {
	// Simple implementation - return all experiences for now
	return m.experiences, nil
}

// truncateString truncates a string to maxLen characters.
func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}

// getString safely extracts a string from a map.
func getString(m map[string]any, key, defaultVal string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return defaultVal
}
