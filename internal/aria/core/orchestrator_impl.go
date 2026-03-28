package core

import (
	"context"
	"sync"

	"github.com/fulvian/aria/internal/aria/agency"
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
}

// NewBasicOrchestrator creates a new basic orchestrator.
func NewBasicOrchestrator(config OrchestratorConfig) *BasicOrchestrator {
	return &BasicOrchestrator{
		classifier:     routing.NewBaselineClassifier(),
		router:         routing.NewDefaultRouter(),
		config:         config,
		agencyRegistry: make(map[agency.AgencyName]agency.Agency),
	}
}

// ProcessQuery handles a user query and returns a response.
func (o *BasicOrchestrator) ProcessQuery(ctx context.Context, query Query) (Response, error) {
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

	// Build response based on routing decision
	resp := Response{
		Agency:     agency.AgencyName(o.getAgencyName(decision)),
		Skills:     decision.Skills,
		Confidence: decision.Confidence,
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
	// TODO: Implement task scheduling
	return "", nil
}

// MonitorTasks returns a channel of task events.
func (o *BasicOrchestrator) MonitorTasks(ctx context.Context) <-chan TaskEvent {
	// TODO: Implement task monitoring
	ch := make(chan TaskEvent)
	close(ch)
	return ch
}

// AnalyzeSelf performs self-analysis and returns insights.
func (o *BasicOrchestrator) AnalyzeSelf(ctx context.Context) (SelfAnalysis, error) {
	// TODO: Implement self-analysis
	return SelfAnalysis{
		Timestamp: 0,
		Metrics:   make(map[string]any),
		Insights:  []string{},
	}, nil
}

// Learn processes an experience for learning.
func (o *BasicOrchestrator) Learn(ctx context.Context, experience Experience) error {
	// TODO: Implement learning
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
