package core

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/fulvian/aria/internal/aria/agency"
	"github.com/fulvian/aria/internal/aria/analysis"
	"github.com/fulvian/aria/internal/aria/memory"
	"github.com/fulvian/aria/internal/aria/routing"
)

// OrchestratorConfig contains configuration for the orchestrator.
type OrchestratorConfig struct {
	// EnableFallback enables fallback to legacy coder agent.
	EnableFallback bool

	// DefaultAgency is the agency to use when no specific routing matches.
	DefaultAgency agency.AgencyName

	// ConfidenceThreshold is the minimum confidence for routing decisions.
	ConfidenceThreshold float64
}

// BasicOrchestrator is a basic implementation of the Orchestrator interface.
type BasicOrchestrator struct {
	mu         sync.RWMutex
	classifier routing.QueryClassifier
	router     routing.Router
	config     OrchestratorConfig

	// agencyRegistry maps agency names to agency instances
	agencyRegistry map[agency.AgencyName]agency.Agency

	// taskQueue stores scheduled tasks
	taskQueue []Task

	// learnings stores experience learnings
	learnings []Experience

	// memoryService provides working memory and episodic/semantic/procedural memory
	memoryService memory.MemoryService

	// analysisService provides self-analysis capabilities
	analysisService analysis.SelfAnalysisService
}

// NewBasicOrchestrator creates a new basic orchestrator.
func NewBasicOrchestrator(config OrchestratorConfig, memorySvc memory.MemoryService, analysisSvc analysis.SelfAnalysisService) *BasicOrchestrator {
	return &BasicOrchestrator{
		classifier:      routing.NewBaselineClassifier(),
		router:          routing.NewDefaultRouter(),
		config:          config,
		agencyRegistry:  make(map[agency.AgencyName]agency.Agency),
		memoryService:   memorySvc,
		analysisService: analysisSvc,
	}
}

// ProcessQuery handles a user query and returns a response.
func (o *BasicOrchestrator) ProcessQuery(ctx context.Context, query Query) (Response, error) {
	// BEFORE execution: Load context from memory service if available
	var workingContext memory.Context
	if o.memoryService != nil && query.SessionID != "" {
		if ctx, err := o.memoryService.GetContext(ctx, query.SessionID); err == nil {
			workingContext = ctx
		}
	}

	// Search for similar episodes if memory service is available
	var similarEpisodes []memory.Episode
	if o.memoryService != nil {
		if episodes, err := o.memoryService.GetSimilarEpisodes(ctx, memory.Situation{
			Description: query.Text,
			Context:     query.Metadata,
		}); err == nil {
			similarEpisodes = episodes
		}
	}

	// Find applicable procedures if memory service is available
	var applicableProcedures []memory.Procedure
	if o.memoryService != nil {
		if procedures, err := o.memoryService.FindApplicableProcedures(ctx, map[string]any{
			"description": query.Text,
			"type":        "query",
		}); err == nil {
			applicableProcedures = procedures
		}
	}

	// Classify the query
	class, err := o.classifier.Classify(ctx, routing.Query{
		Text:      query.Text,
		SessionID: query.SessionID,
		UserID:    query.UserID,
		History:   nil, // TODO: pass history
		Metadata:  query.Metadata,
	})
	if err != nil {
		return Response{}, err
	}

	// Route the query
	decision, err := o.router.Route(ctx, routing.Query{
		Text:      query.Text,
		SessionID: query.SessionID,
		UserID:    query.UserID,
	}, class)
	if err != nil {
		return Response{}, err
	}

	// Check if we should fallback
	if decision.Fallback && decision.Confidence < o.config.ConfidenceThreshold && o.config.EnableFallback {
		return Response{
			Text:       "FALLBACK_TO_LEGACY",
			Confidence: decision.Confidence,
		}, nil
	}

	// Get agency name
	agencyName := agency.AgencyName(o.getAgencyName(decision))

	// Get the agency from registry
	o.mu.RLock()
	ag, ok := o.agencyRegistry[agencyName]
	o.mu.RUnlock()

	if !ok {
		return Response{
			Text:       "FALLBACK_TO_LEGACY",
			Agency:     agencyName,
			Skills:     decision.Skills,
			Confidence: decision.Confidence,
		}, nil
	}

	// Create task from query
	task := agency.Task{
		ID:          uuid.New().String(),
		Name:        "query-task",
		Description: query.Text,
		Skills:      decision.Skills,
		Parameters: map[string]any{
			"prompt":                query.Text,
			"working_context":       workingContext,
			"similar_episodes":      similarEpisodes,
			"applicable_procedures": applicableProcedures,
		},
	}

	// Execute the task
	result, err := ag.Execute(ctx, task)
	if err != nil {
		// AFTER execution: Learn from failure
		if o.memoryService != nil {
			action := memory.Action{
				Type:      "query",
				Tool:      string(agencyName),
				Timestamp: time.Now(),
			}
			_ = o.memoryService.LearnFromFailure(ctx, action, err)
		}

		return Response{
			Text:       fmt.Sprintf("Error executing task: %v", err),
			Agency:     agencyName,
			Skills:     decision.Skills,
			Confidence: decision.Confidence,
		}, err
	}

	// Build response based on routing decision and execution result
	resp := Response{
		Agency:     agencyName,
		Skills:     decision.Skills,
		Confidence: decision.Confidence,
	}

	// Extract content from result
	if result.Success && result.Output != nil {
		if content, ok := result.Output["response"].(string); ok && content != "" {
			resp.Text = content
		} else if summary, ok := result.Output["summary"].(string); ok && summary != "" {
			resp.Text = summary
		}
	}

	if resp.Text == "" {
		resp.Text = fmt.Sprintf("Task completed (status: %s)", result.Error)
	}

	// AFTER execution: Record episode and learn from success
	if o.memoryService != nil {
		episode := memory.Episode{
			SessionID: query.SessionID,
			AgencyID:  string(agencyName),
			Task: map[string]any{
				"text":       query.Text,
				"skills":     decision.Skills,
				"confidence": decision.Confidence,
			},
			Outcome: resp.Text,
		}

		// Record the episode
		if recErr := o.memoryService.RecordEpisode(ctx, episode); recErr != nil {
			// Log but don't fail the request
			fmt.Printf("failed to record episode: %v\n", recErr)
		}

		// Learn from success if the task was successful
		if result.Success {
			action := memory.Action{
				Type:      "query",
				Tool:      string(agencyName),
				Output:    result.Output,
				Timestamp: time.Now(),
			}
			_ = o.memoryService.LearnFromSuccess(ctx, action, resp.Text)
		}
	}

	return resp, nil
}

// RouteToAgency determines which agency should handle the query.
func (o *BasicOrchestrator) RouteToAgency(ctx context.Context, query Query) (agency.Agency, error) {
	class, err := o.classifier.Classify(ctx, routing.Query{
		Text:      query.Text,
		SessionID: query.SessionID,
		UserID:    query.UserID,
	})
	if err != nil {
		return nil, err
	}

	decision, err := o.router.Route(ctx, routing.Query{
		Text:      query.Text,
		SessionID: query.SessionID,
		UserID:    query.UserID,
	}, class)
	if err != nil {
		return nil, err
	}

	agencyName := agency.AgencyName(o.getAgencyName(decision))
	if ag, ok := o.agencyRegistry[agencyName]; ok {
		return ag, nil
	}

	// Return nil if agency not found - caller should handle fallback
	return nil, nil
}

// RouteToAgent determines which agent should handle the query.
func (o *BasicOrchestrator) RouteToAgent(ctx context.Context, query Query) (string, error) {
	class, err := o.classifier.Classify(ctx, routing.Query{
		Text:      query.Text,
		SessionID: query.SessionID,
		UserID:    query.UserID,
	})
	if err != nil {
		return "", err
	}

	decision, err := o.router.Route(ctx, routing.Query{
		Text:      query.Text,
		SessionID: query.SessionID,
		UserID:    query.UserID,
	}, class)
	if err != nil {
		return "", err
	}

	if decision.Agent != nil {
		return *decision.Agent, nil
	}

	return "", nil
}

// ScheduleTask schedules a task for future execution.
func (o *BasicOrchestrator) ScheduleTask(ctx context.Context, task Task) (TaskID, error) {
	o.mu.Lock()
	defer o.mu.Unlock()

	taskID := TaskID(uuid.New().String())
	task.ID = taskID
	task.ScheduledAt = ptrInt64(time.Now().Unix())
	task.Status = "scheduled"

	o.taskQueue = append(o.taskQueue, task)

	return taskID, nil
}

// MonitorTasks returns a channel of task events.
func (o *BasicOrchestrator) MonitorTasks(ctx context.Context) <-chan TaskEvent {
	events := make(chan TaskEvent)

	go func() {
		defer close(events)

		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				o.mu.RLock()
				for _, task := range o.taskQueue {
					events <- TaskEvent{
						TaskID:    task.ID,
						Type:      "task_status",
						Payload:   map[string]any{"status": task.Status},
						Timestamp: time.Now().Unix(),
					}
				}
				o.mu.RUnlock()
			}
		}
	}()

	return events
}

// AnalyzeSelf performs self-analysis and returns insights.
func (o *BasicOrchestrator) AnalyzeSelf(ctx context.Context) (SelfAnalysis, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()

	now := time.Now().Unix()
	insights := []string{}

	// Basic metrics based on current state
	metrics := map[string]any{
		"registered_agencies": len(o.agencyRegistry),
		"scheduled_tasks":     len(o.taskQueue),
		"learnings":           len(o.learnings),
	}

	// Generate insights based on current state
	if len(o.agencyRegistry) == 0 {
		insights = append(insights, "No agencies registered")
	} else {
		insights = append(insights, fmt.Sprintf("%d agencies available", len(o.agencyRegistry)))
	}

	if len(o.taskQueue) > 10 {
		insights = append(insights, "High number of scheduled tasks")
	}

	return SelfAnalysis{
		Timestamp: now,
		Metrics:   metrics,
		Insights:  insights,
	}, nil
}

// Learn processes an experience for learning.
func (o *BasicOrchestrator) Learn(ctx context.Context, experience Experience) error {
	o.mu.Lock()
	defer o.mu.Unlock()

	experience.Timestamp = time.Now().Unix()
	o.learnings = append(o.learnings, experience)

	return nil
}

// GetProactiveSuggestions returns suggestions for proactive behavior.
func (o *BasicOrchestrator) GetProactiveSuggestions(ctx context.Context) ([]Suggestion, error) {
	// TODO: Implement proactive suggestions
	return []Suggestion{}, nil
}

// RegisterAgency registers an agency with the orchestrator.
func (o *BasicOrchestrator) RegisterAgency(ag agency.Agency) {
	o.mu.Lock()
	defer o.mu.Unlock()
	o.agencyRegistry[ag.Name()] = ag
}

// UnregisterAgency removes an agency from the orchestrator.
func (o *BasicOrchestrator) UnregisterAgency(name agency.AgencyName) {
	o.mu.Lock()
	defer o.mu.Unlock()
	delete(o.agencyRegistry, name)
}

// getAgencyName extracts the agency name from a routing decision.
func (o *BasicOrchestrator) getAgencyName(decision routing.RoutingDecision) string {
	if decision.Agency != nil {
		return *decision.Agency
	}
	return string(o.config.DefaultAgency)
}

// ptrInt64 returns a pointer to an int64 value.
func ptrInt64(v int64) *int64 {
	return &v
}
