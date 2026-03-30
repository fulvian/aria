// Package routing provides the query classification and routing system
// that determines how user queries are handled by ARIA.
//
// This package implements the routing interfaces defined in Blueprint Section 2.3.
package routing

import (
	"context"
)

// Intent represents what the user wants to do.
type Intent string

// Intent constants
const (
	IntentQuestion     Intent = "question"     // Simple question
	IntentTask         Intent = "task"         // Task to execute
	IntentCreation     Intent = "creation"     // Create something
	IntentAnalysis     Intent = "analysis"     // Analyze data
	IntentLearning     Intent = "learning"     // Learn/explain
	IntentPlanning     Intent = "planning"     // Plan something
	IntentConversation Intent = "conversation" // Casual chat
)

// DomainName represents a domain of expertise.
type DomainName string

// Domain constants
const (
	DomainGeneral      DomainName = "general"
	DomainDevelopment  DomainName = "development"
	DomainKnowledge    DomainName = "knowledge"
	DomainCreative     DomainName = "creative"
	DomainProductivity DomainName = "productivity"
	DomainPersonal     DomainName = "personal"
	DomainAnalytics    DomainName = "analytics"
	DomainNutrition    DomainName = "nutrition"
)

// ComplexityLevel indicates query complexity.
type ComplexityLevel string

// Complexity constants
const (
	ComplexitySimple  ComplexityLevel = "simple"  // Single turn, direct answer
	ComplexityMedium  ComplexityLevel = "medium"  // Multi-step, some context
	ComplexityComplex ComplexityLevel = "complex" // Long-running, multiple agents
)

// UrgencyLevel indicates how soon the user wants a response.
type UrgencyLevel string

// Urgency constants
const (
	UrgencyNow        UrgencyLevel = "now"        // Immediate response
	UrgencySoon       UrgencyLevel = "soon"       // Within minutes
	UrgencyEventually UrgencyLevel = "eventually" // Can wait
)

// RoutingTarget indicates where a query should be routed.
type RoutingTarget string

// Routing target constants
const (
	TargetOrchestrator RoutingTarget = "orchestrator"
	TargetAgency       RoutingTarget = "agency"
	TargetAgent        RoutingTarget = "agent"
	TargetSkill        RoutingTarget = "skill"
)

// Classification contains the result of query classification.
type Classification struct {
	Intent        Intent
	Domain        DomainName
	Complexity    ComplexityLevel
	RequiresState bool
	Urgency       UrgencyLevel

	// Routing suggestion
	SuggestedTarget RoutingTarget
	Confidence      float64
	Reason          string
}

// Query represents a user query for classification.
type Query struct {
	Text      string
	SessionID string
	UserID    string
	History   []string // Previous messages in conversation
	Metadata  map[string]any
}

// QueryClassifier classifies user queries into Intent, Domain, Complexity, etc.
//
// Reference: Blueprint Section 2.3.1
type QueryClassifier interface {
	// Classify determines the characteristics of a query.
	Classify(ctx context.Context, query Query) (Classification, error)

	// GetSupportedIntents returns all supported intents.
	GetSupportedIntents() []Intent

	// GetSupportedDomains returns all supported domains.
	GetSupportedDomains() []DomainName
}
