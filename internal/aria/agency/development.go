// Package agency provides the Development Agency implementation.
package agency

import (
	"context"
	"fmt"
	"strings"
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

	// Extract files/pattern from task parameters
	var files []string
	var pattern string

	if task.Parameters != nil {
		if f, ok := task.Parameters["files"].([]string); ok {
			files = f
		}
		if p, ok := task.Parameters["pattern"].(string); ok {
			pattern = p
		}
	}

	// Execute code review skill
	codeReviewSkill := a.skills[0].(*skill.CodeReviewSkill)
	skillResult, err := codeReviewSkill.Execute(ctx, skill.SkillParams{
		TaskID: task.ID,
		Input: map[string]any{
			"files":       files,
			"pattern":     pattern,
			"description": task.Description,
		},
		Context: map[string]any{
			"task_id": task.ID,
		},
	})

	if err != nil {
		// Return error result but still publish event
		result := map[string]any{
			"type":        "code-review",
			"task_id":     task.ID,
			"description": task.Description,
			"status":      "failed",
			"error":       err.Error(),
			"findings":    []map[string]any{},
			"summary":     "Code review failed: " + err.Error(),
		}
		a.broker.Publish(contracts.AgentEvent{
			AgentID: string(a.name),
			Type:    "review_completed",
			TaskID:  task.ID,
			Payload: result,
		})
		return result, err
	}

	// Convert skill result to review result
	findings := []map[string]any{}
	if output, ok := skillResult.Output["findings"].([]map[string]any); ok {
		findings = output
	}

	stats := map[string]int{}
	if s, ok := skillResult.Output["stats"].(map[string]int); ok {
		stats = s
	}

	result := map[string]any{
		"type":           "code-review",
		"task_id":        task.ID,
		"description":    task.Description,
		"status":         "completed",
		"findings":       findings,
		"summary":        skillResult.Output["summary"],
		"files_reviewed": skillResult.Output["files_reviewed"],
		"stats":          stats,
		"duration_ms":    skillResult.DurationMs,
		"steps":          skillResult.Steps,
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
	// Update metrics based on feedback type
	if a.state.Metrics == nil {
		a.state.Metrics = make(map[string]any)
	}

	switch feedback.Type {
	case "positive":
		a.state.Metrics["positive_feedback_count"] =
			int64Value(a.state.Metrics["positive_feedback_count"]) + 1
		// Increase confidence for similar tasks
		a.state.Metrics["review_confidence"] =
			minFloat64(100, float64Value(a.state.Metrics["review_confidence"], 80)+5)
	case "negative":
		a.state.Metrics["negative_feedback_count"] =
			int64Value(a.state.Metrics["negative_feedback_count"]) + 1
		// Decrease confidence
		a.state.Metrics["review_confidence"] =
			maxFloat64(0, float64Value(a.state.Metrics["review_confidence"], 80)-10)
	case "suggestion":
		a.state.Metrics["suggestion_count"] =
			int64Value(a.state.Metrics["suggestion_count"]) + 1
	}

	// Store feedback for pattern learning
	if a.state.Metrics["recent_feedback"] == nil {
		a.state.Metrics["recent_feedback"] = []contracts.Feedback{}
	}
	recentFeedback := a.state.Metrics["recent_feedback"].([]contracts.Feedback)
	recentFeedback = append(recentFeedback, feedback)
	// Keep only last 10 feedbacks
	if len(recentFeedback) > 10 {
		recentFeedback = recentFeedback[len(recentFeedback)-10:]
	}
	a.state.Metrics["recent_feedback"] = recentFeedback

	// Analyze feedback content for patterns
	if strings.Contains(strings.ToLower(feedback.Content), "missed") {
		a.state.Metrics["missed_issue_types"] =
			appendStringSlice(a.state.Metrics["missed_issue_types"], extractIssueType(feedback.Content))
	}

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

	// Analyze task description to determine architecture
	desc := strings.ToLower(task.Description)

	// Detect application type
	appType := detectApplicationType(desc)

	// Determine architectural pattern and components
	patterns := detectArchitecturalPatterns(desc)
	components := detectComponents(desc, appType)
	layers := determineLayers(appType, patterns)

	result := map[string]any{
		"type":        "architecture",
		"task_id":     task.ID,
		"description": task.Description,
		"status":      "completed",
		"design": map[string]any{
			"application_type": appType,
			"components":       components,
			"layers":           layers,
			"patterns":         patterns,
			"technology_hints": getTechnologyHints(appType, patterns),
		},
		"summary": fmt.Sprintf("System design completed using %s architecture with %d components",
			getPrimaryPattern(patterns), len(components)),
	}

	a.broker.Publish(contracts.AgentEvent{
		AgentID: string(a.name),
		Type:    "design_completed",
		TaskID:  task.ID,
		Payload: result,
	})

	return result, nil
}

// detectApplicationType determines the type of application from description.
func detectApplicationType(desc string) string {
	typeIndicators := map[string][]string{
		"web":           {"web", "website", "frontend", "ui", "dashboard", "portal"},
		"api":           {"api", "rest", "graphql", "grpc", "endpoint", "service"},
		"cli":           {"cli", "command-line", "terminal", "console", "tool", "script"},
		"data-pipeline": {"pipeline", "etl", "batch", "stream", "kafka", "data processing"},
		"mobile":        {"mobile", "ios", "android", "app"},
		"microservice":  {"microservice", "distributed", "container", "docker", "kubernetes"},
	}

	for appType, indicators := range typeIndicators {
		for _, indicator := range indicators {
			if strings.Contains(desc, indicator) {
				return appType
			}
		}
	}
	return "general"
}

// detectArchitecturalPatterns identifies architectural patterns from description.
func detectArchitecturalPatterns(desc string) []string {
	patterns := []string{}
	patternIndicators := map[string][]string{
		"layered-architecture":   {"layered", "layers", "tier", "3-tier", "n-tier"},
		"hexagonal-architecture": {"hexagonal", "ports-and-adapters", "adapter", "port"},
		"event-driven":           {"event", "event-driven", "pub/sub", "mq", "message queue"},
		"microservices":          {"microservice", "service-mesh", "api-gateway"},
		"cqrs":                   {"cqrs", "command-query-responsibility-segregation"},
		"event-sourcing":         {"event-sourcing", "event-store"},
		"clean-architecture":     {"clean-architecture", "use-case", "interactor"},
		"serverless":             {"serverless", "lambda", "function", "faas"},
	}

	for pattern, indicators := range patternIndicators {
		for _, indicator := range indicators {
			if strings.Contains(desc, indicator) {
				if !contains(patterns, pattern) {
					patterns = append(patterns, pattern)
				}
			}
		}
	}

	if len(patterns) == 0 {
		patterns = append(patterns, "layered-architecture") // Default
	}
	return patterns
}

// detectComponents identifies required components based on app type.
func detectComponents(desc string, appType string) []string {
	var components []string

	// Base components common to most applications
	baseComponents := []string{"config", "logging", "error-handling"}

	// Type-specific components
	typeComponents := map[string][]string{
		"web":           {"router", "handler", "template", "static-assets", "session", "middleware"},
		"api":           {"router", "handler", "middleware", "validator", "auth", "rate-limiter"},
		"cli":           {"parser", "command", "formatter", "interactive"},
		"data-pipeline": {"source", "transformer", "sink", "scheduler", "monitoring"},
		"mobile":        {"screen", "navigation", "storage", "network", "offline"},
		"microservice":  {"client", "api-gateway", "service-discovery", "load-balancer", "circuit-breaker"},
	}

	if tc, ok := typeComponents[appType]; ok {
		components = append(components, tc...)
	} else {
		components = append(components, baseComponents...)
	}

	// Add specific feature components based on keywords
	featureComponents := map[string][]string{
		"auth":         {"auth", "session", "token", "jwt", "oauth"},
		"database":     {"repository", "migration", "connection-pool"},
		"cache":        {"cache", "redis", "memcached"},
		"queue":        {"queue", "worker", "job"},
		"search":       {"search", "index", "query"},
		"file":         {"upload", "storage", "cdn"},
		"notification": {"notification", "email", "push", "sms"},
		"analytics":    {"analytics", "metrics", "dashboard", "reporting"},
		"realtime":     {"websocket", "sse", "realtime"},
		"security":     {"auth", "encryption", "sanitization", "cors"},
		"api-docs":     {"swagger", "openapi", "docs"},
	}

	for feature, keywords := range featureComponents {
		for _, keyword := range keywords {
			if strings.Contains(desc, keyword) {
				componentName := feature
				if !contains(components, componentName) {
					components = append(components, componentName)
				}
				break
			}
		}
	}

	return components
}

// determineLayers determines the layer structure based on app type and patterns.
func determineLayers(appType string, patterns []string) []string {
	if contains(patterns, "hexagonal-architecture") {
		return []string{"adapters", "ports", "domain"}
	}
	if contains(patterns, "clean-architecture") {
		return []string{"controllers", "use-cases", "entities", "gateways"}
	}
	if contains(patterns, "layered-architecture") || contains(patterns, "microservices") {
		return []string{"presentation", "application", "domain", "infrastructure"}
	}

	// Default layered architecture
	return []string{"presentation", "business", "data"}
}

// getTechnologyHints provides technology recommendations.
func getTechnologyHints(appType string, patterns []string) []string {
	hints := []string{}

	if appType == "web" {
		hints = append(hints, "Frontend: React/Vue/Angular", "HTTP Server: Standard library or Gin/Echo")
	}
	if appType == "api" {
		hints = append(hints, "HTTP Framework: Gin/Echo/Fiber", "API Documentation: Swagger/OpenAPI")
	}
	if appType == "data-pipeline" {
		hints = append(hints, "Stream Processing: Kafka/Flink", "Batch: Cron or scheduler library")
	}
	if contains(patterns, "microservices") {
		hints = append(hints, "Service Mesh: Istio/Linkerd", "Container: Docker", "Orchestration: Kubernetes")
	}
	if contains(patterns, "event-driven") {
		hints = append(hints, "Message Broker: Kafka/RabbitMQ/NATS", "Event Store: EventStoreDB")
	}

	return hints
}

// getPrimaryPattern returns the main architectural pattern.
func getPrimaryPattern(patterns []string) string {
	if len(patterns) > 0 {
		return patterns[0]
	}
	return "layered-architecture"
}

// contains checks if a string slice contains a value.
func contains(slice []string, value string) bool {
	for _, v := range slice {
		if v == value {
			return true
		}
	}
	return false
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
	// Update metrics based on feedback type
	if a.state.Metrics == nil {
		a.state.Metrics = make(map[string]any)
	}

	switch feedback.Type {
	case "positive":
		a.state.Metrics["positive_feedback_count"] =
			int64Value(a.state.Metrics["positive_feedback_count"]) + 1
		a.state.Metrics["design_confidence"] =
			minFloat64(100, float64Value(a.state.Metrics["design_confidence"], 80)+5)
	case "negative":
		a.state.Metrics["negative_feedback_count"] =
			int64Value(a.state.Metrics["negative_feedback_count"]) + 1
		a.state.Metrics["design_confidence"] =
			maxFloat64(0, float64Value(a.state.Metrics["design_confidence"], 80)-10)
	case "suggestion":
		a.state.Metrics["suggestion_count"] =
			int64Value(a.state.Metrics["suggestion_count"]) + 1
	}

	// Store feedback for pattern learning
	if a.state.Metrics["recent_feedback"] == nil {
		a.state.Metrics["recent_feedback"] = []contracts.Feedback{}
	}
	recentFeedback := a.state.Metrics["recent_feedback"].([]contracts.Feedback)
	recentFeedback = append(recentFeedback, feedback)
	if len(recentFeedback) > 10 {
		recentFeedback = recentFeedback[len(recentFeedback)-10:]
	}
	a.state.Metrics["recent_feedback"] = recentFeedback

	// Learn from design suggestions
	if strings.Contains(strings.ToLower(feedback.Content), "component") {
		a.state.Metrics["component_suggestions"] =
			int64Value(a.state.Metrics["component_suggestions"]) + 1
	}
	if strings.Contains(strings.ToLower(feedback.Content), "pattern") {
		a.state.Metrics["pattern_suggestions"] =
			int64Value(a.state.Metrics["pattern_suggestions"]) + 1
	}

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

	// Extract the query from task parameters - check "query" first (new orchestrator key),
	// then fall back to "prompt" (legacy key), then to task description/name
	query, _ := task.Parameters["query"].(string)
	if query == "" {
		query, _ = task.Parameters["prompt"].(string)
	}
	if query == "" {
		query = task.Description
	}
	if query == "" {
		query = task.Name
	}

	if query == "" {
		return nil, fmt.Errorf("no query provided for task %s", task.ID)
	}

	// Build enriched prompt with memory context
	enrichedQuery := buildContextPrompt(task)

	// Create a session for this task (use short query for title)
	sess, err := b.sessions.Create(ctx, "ARIA: "+truncateString(query, 50))
	if err != nil {
		return nil, fmt.Errorf("failed to create session: %w", err)
	}

	// Run the agent and collect the response (use enriched query with memory context)
	events, err := b.agent.Run(ctx, sess.ID, enrichedQuery)
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
		"prompt_preview": truncateString(query, 100),
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
	// Update metrics based on feedback type
	if b.state.Metrics == nil {
		b.state.Metrics = make(map[string]any)
	}

	switch feedback.Type {
	case "positive":
		b.state.Metrics["positive_feedback_count"] =
			int64Value(b.state.Metrics["positive_feedback_count"]) + 1
		b.state.Metrics["coding_confidence"] =
			minFloat64(100, float64Value(b.state.Metrics["coding_confidence"], 80)+5)
	case "negative":
		b.state.Metrics["negative_feedback_count"] =
			int64Value(b.state.Metrics["negative_feedback_count"]) + 1
		b.state.Metrics["coding_confidence"] =
			maxFloat64(0, float64Value(b.state.Metrics["coding_confidence"], 80)-10)
	case "suggestion":
		b.state.Metrics["suggestion_count"] =
			int64Value(b.state.Metrics["suggestion_count"]) + 1
	}

	// Store feedback for pattern learning
	if b.state.Metrics["recent_feedback"] == nil {
		b.state.Metrics["recent_feedback"] = []contracts.Feedback{}
	}
	recentFeedback := b.state.Metrics["recent_feedback"].([]contracts.Feedback)
	recentFeedback = append(recentFeedback, feedback)
	if len(recentFeedback) > 10 {
		recentFeedback = recentFeedback[len(recentFeedback)-10:]
	}
	b.state.Metrics["recent_feedback"] = recentFeedback

	// Learn coding patterns from feedback
	content := strings.ToLower(feedback.Content)
	if strings.Contains(content, "bug") || strings.Contains(content, "error") {
		b.state.Metrics["bug_reports"] = int64Value(b.state.Metrics["bug_reports"]) + 1
	}
	if strings.Contains(content, "performance") || strings.Contains(content, "slow") {
		b.state.Metrics["performance_issues"] = int64Value(b.state.Metrics["performance_issues"]) + 1
	}
	if strings.Contains(content, "security") || strings.Contains(content, "vulnerability") {
		b.state.Metrics["security_issues"] = int64Value(b.state.Metrics["security_issues"]) + 1
	}

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

// int64Value safely extracts int64 from map.
func int64Value(v any) int64 {
	if n, ok := v.(int64); ok {
		return n
	}
	if n, ok := v.(int); ok {
		return int64(n)
	}
	if n, ok := v.(float64); ok {
		return int64(n)
	}
	return 0
}

// float64Value safely extracts float64 from map.
func float64Value(v any, defaultVal float64) float64 {
	if n, ok := v.(float64); ok {
		return n
	}
	return defaultVal
}

// minFloat64 returns the minimum of two float64 values.
func minFloat64(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}

// maxFloat64 returns the maximum of two float64 values.
func maxFloat64(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}

// appendStringSlice appends a string to a slice stored in a map.
func appendStringSlice(v any, s string) []string {
	if slice, ok := v.([]string); ok {
		return append(slice, s)
	}
	return []string{s}
}

// extractIssueType attempts to extract the type of issue from feedback content.
func extractIssueType(content string) string {
	content = strings.ToLower(content)
	issueTypes := []string{"bug", "security", "performance", "style", "logic", "error"}
	for _, t := range issueTypes {
		if strings.Contains(content, t) {
			return t
		}
	}
	return "unknown"
}
