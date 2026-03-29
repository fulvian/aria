// Package agent provides the enhanced Agent interface that extends
// the legacy flat agent system with skills, agency membership,
// and learning capabilities.
//
// This package implements the Agent interface defined in Blueprint Section 2.2.3.
package agent

import (
	"context"
	"fmt"

	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/aria/skill"
	llmagent "github.com/fulvian/aria/internal/llm/agent"
	"github.com/fulvian/aria/internal/logging"
	"github.com/fulvian/aria/internal/pubsub"
)

// LegacyAgentWrapper wraps an existing internal/llm/agent.Service
// to conform to the Agent interface.
type LegacyAgentWrapper struct {
	agent      llmagent.Service
	agencyName contracts.AgencyName
	skills     []skill.Skill
	broker     *pubsub.Broker[contracts.AgentEvent]
	name       contracts.AgentName
	state      contracts.AgentState
}

// NewLegacyAgentWrapper creates a wrapper around a legacy agent.
func NewLegacyAgentWrapper(
	legacyAgent llmagent.Service,
	name contracts.AgentName,
	agencyName contracts.AgencyName,
	skills []skill.Skill,
) *LegacyAgentWrapper {
	wrapper := &LegacyAgentWrapper{
		agent:      legacyAgent,
		agencyName: agencyName,
		skills:     skills,
		broker:     pubsub.NewBroker[contracts.AgentEvent](),
		name:       name,
		state: contracts.AgentState{
			AgentID: string(name),
			Status:  "idle",
			Metrics: make(map[string]any),
		},
	}

	// Subscribe to legacy agent events and forward them
	ctx := context.Background()
	sub := legacyAgent.Subscribe(ctx)
	go wrapper.forwardEvents(sub)

	return wrapper
}

// forwardEvents forwards events from the legacy agent to our broker.
func (w *LegacyAgentWrapper) forwardEvents(sub <-chan pubsub.Event[llmagent.AgentEvent]) {
	for event := range sub {
		legacyEvent := event.Payload
		ariaEvent := contracts.AgentEvent{
			AgentID: string(w.name),
			Type:    string(legacyEvent.Type),
			Payload: map[string]any{
				"sessionID": legacyEvent.SessionID,
				"progress":  legacyEvent.Progress,
				"done":      legacyEvent.Done,
			},
		}
		if legacyEvent.Message.ID != "" {
			ariaEvent.Payload["message"] = legacyEvent.Message.Content().Text
		}
		w.broker.Publish(pubsub.CreatedEvent, ariaEvent)
	}
}

// Name returns the agent name.
func (w *LegacyAgentWrapper) Name() contracts.AgentName {
	return w.name
}

// Agency returns the agency this agent belongs to.
func (w *LegacyAgentWrapper) Agency() contracts.AgencyName {
	return w.agencyName
}

// Capabilities returns the capabilities of this agent.
func (w *LegacyAgentWrapper) Capabilities() []contracts.Capability {
	capabilities := []contracts.Capability{
		{
			Name:        "code-generation",
			Description: "Generates code based on natural language descriptions",
			Tools:       []string{"bash", "edit", "write", "view", "glob", "grep"},
		},
		{
			Name:        "code-editing",
			Description: "Edits existing code files",
			Tools:       []string{"edit", "view", "grep"},
		},
		{
			Name:        "file-operations",
			Description: "Reads and writes files in the workspace",
			Tools:       []string{"view", "write", "glob", "ls"},
		},
	}

	// Add skill capabilities
	for _, s := range w.skills {
		capabilities = append(capabilities, contracts.Capability{
			Name:        string(s.Name()),
			Description: s.Description(),
			Tools:       toolNamesToStrings(s.RequiredTools()),
		})
	}

	return capabilities
}

// toolNamesToStrings converts skill.ToolName slice to string slice.
func toolNamesToStrings(names []skill.ToolName) []string {
	result := make([]string, len(names))
	for i, n := range names {
		result[i] = string(n)
	}
	return result
}

// Run executes the legacy agent with the given task.
func (w *LegacyAgentWrapper) Run(ctx context.Context, task map[string]any) (map[string]any, error) {
	w.state.Status = "busy"
	w.state.AgentID = string(w.name)

	// Extract session_id and content from task map
	sessionID, _ := task["session_id"].(string)
	content, _ := task["content"].(string)

	if sessionID == "" {
		w.state.Status = "idle"
		return nil, fmt.Errorf("session_id is required")
	}
	if content == "" {
		w.state.Status = "idle"
		return nil, fmt.Errorf("content is required")
	}

	// Call the legacy agent
	events, err := w.agent.Run(ctx, sessionID, content)
	if err != nil {
		w.state.Status = "error"
		return nil, fmt.Errorf("legacy agent run failed: %w", err)
	}

	// Collect all events
	var lastEvent llmagent.AgentEvent
	for event := range events {
		lastEvent = event
		if event.Type == llmagent.AgentEventTypeError && event.Error != nil {
			w.state.Status = "error"
			return nil, fmt.Errorf("agent error: %w", event.Error)
		}
	}

	w.state.Status = "idle"
	w.state.TasksDone++

	// Extract content from the final message
	response := map[string]any{
		"session_id": sessionID,
		"success":    true,
	}

	if lastEvent.Message.ID != "" {
		response["content"] = lastEvent.Message.Content().Text
	}

	return response, nil
}

// Stream streams the legacy agent response.
func (w *LegacyAgentWrapper) Stream(ctx context.Context, task map[string]any) (<-chan contracts.Event, error) {
	// Extract session_id and content from task map
	sessionID, _ := task["session_id"].(string)
	content, _ := task["content"].(string)

	if sessionID == "" {
		return nil, fmt.Errorf("session_id is required")
	}
	if content == "" {
		return nil, fmt.Errorf("content is required")
	}

	events := make(chan contracts.Event)

	// Call the legacy agent
	legacyEvents, err := w.agent.Run(ctx, sessionID, content)
	if err != nil {
		return nil, fmt.Errorf("legacy agent stream failed: %w", err)
	}

	go func() {
		defer close(events)
		for legacyEvent := range legacyEvents {
			event := contracts.Event{
				Type: string(legacyEvent.Type),
			}
			if legacyEvent.Message.ID != "" {
				event.Content = legacyEvent.Message.Content().Text
			}
			events <- event
		}
	}()

	return events, nil
}

// Skills returns the skills available to this agent.
func (w *LegacyAgentWrapper) Skills() []skill.Skill {
	return w.skills
}

// HasSkill returns true if the agent has the specified skill.
func (w *LegacyAgentWrapper) HasSkill(name skill.SkillName) bool {
	for _, s := range w.skills {
		if s.Name() == name {
			return true
		}
	}
	return false
}

// LearnFromFeedback processes feedback to improve agent performance.
// Currently a no-op as the legacy agent doesn't support learning.
func (w *LegacyAgentWrapper) LearnFromFeedback(feedback contracts.Feedback) error {
	logging.Debug("LearnFromFeedback called", "agent", w.name, "feedback", feedback.Type)
	// TODO: Implement learning mechanism if needed
	// For now, this is a placeholder as the legacy agent doesn't have learning
	return nil
}

// GetState returns the current state of the agent.
func (w *LegacyAgentWrapper) GetState() contracts.AgentState {
	w.state.AgentID = string(w.name)
	return w.state
}

// Subscribe returns a channel for receiving agent events.
// It wraps the internal broker subscription to provide AgentEvent directly.
func (w *LegacyAgentWrapper) Subscribe(ctx context.Context) <-chan contracts.AgentEvent {
	// Create a channel that will receive unwrapped AgentEvent
	agentEvents := make(chan contracts.AgentEvent)

	// Subscribe to the broker
	sub := w.broker.Subscribe(ctx)

	// Forward events, unwrapping them from pubsub.Event[AgentEvent] to AgentEvent
	go func() {
		defer close(agentEvents)
		for {
			select {
			case <-ctx.Done():
				return
			case event, ok := <-sub:
				if !ok {
					return
				}
				select {
				case agentEvents <- event.Payload:
				case <-ctx.Done():
					return
				}
			}
		}
	}()

	return agentEvents
}

// Cancel cancels the current execution on the legacy agent.
// This is part of the LegacyCoderBridge interface.
func (w *LegacyAgentWrapper) Cancel(taskID string) error {
	// The legacy agent uses sessionID, not taskID
	w.agent.Cancel(taskID)
	return nil
}
