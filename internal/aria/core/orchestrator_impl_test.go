package core

import (
	"context"
	"errors"
	"testing"

	"github.com/fulvian/aria/internal/aria/agency"
	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/aria/core/decision"
	"github.com/fulvian/aria/internal/aria/routing"
	"github.com/stretchr/testify/assert"
)

// mockAgency is a mock implementation of agency.Agency for testing.
type mockAgency struct {
	nameFunc        func() contracts.AgencyName
	domainFunc      func() string
	descriptionFunc func() string
	executeFunc     func(ctx context.Context, task contracts.Task) (contracts.Result, error)
}

func (m *mockAgency) Name() contracts.AgencyName {
	if m.nameFunc != nil {
		return m.nameFunc()
	}
	return "test-agency"
}

func (m *mockAgency) Domain() string {
	if m.domainFunc != nil {
		return m.domainFunc()
	}
	return "test"
}

func (m *mockAgency) Description() string {
	if m.descriptionFunc != nil {
		return m.descriptionFunc()
	}
	return "test agency"
}

func (m *mockAgency) Execute(ctx context.Context, task contracts.Task) (contracts.Result, error) {
	if m.executeFunc != nil {
		return m.executeFunc(ctx, task)
	}
	return contracts.Result{
		Success: true,
		Output:  map[string]any{"response": "mock response"},
	}, nil
}

// Required by AgencyLifecycle interface
func (m *mockAgency) Start(ctx context.Context) error                            { return nil }
func (m *mockAgency) Stop(ctx context.Context) error                             { return nil }
func (m *mockAgency) Pause(ctx context.Context) error                            { return nil }
func (m *mockAgency) Resume(ctx context.Context) error                           { return nil }
func (m *mockAgency) Status() agency.AgencyStatus                                { return agency.AgencyStatusRunning }
func (m *mockAgency) Subscribe(ctx context.Context) <-chan contracts.AgencyEvent { return nil }
func (m *mockAgency) Agents() []contracts.AgentName                              { return nil }
func (m *mockAgency) GetAgent(name contracts.AgentName) (interface{}, error)     { return nil, nil }
func (m *mockAgency) GetState() agency.AgencyState                               { return agency.AgencyState{} }
func (m *mockAgency) SaveState(state agency.AgencyState) error                   { return nil }
func (m *mockAgency) Memory() agency.DomainMemory                                { return nil }

// mockQueryClassifier is a mock implementation of routing.QueryClassifier for testing.
type mockQueryClassifier struct {
	classifyFunc         func(ctx context.Context, query routing.Query) (routing.Classification, error)
	supportedIntentsFunc func() []routing.Intent
	supportedDomainsFunc func() []routing.DomainName
}

func (m *mockQueryClassifier) Classify(ctx context.Context, query routing.Query) (routing.Classification, error) {
	if m.classifyFunc != nil {
		return m.classifyFunc(ctx, query)
	}
	return routing.Classification{
		Intent:     routing.IntentTask,
		Domain:     routing.DomainDevelopment,
		Complexity: routing.ComplexityMedium,
		Confidence: 0.8,
		Reason:     "mock classification",
	}, nil
}

func (m *mockQueryClassifier) GetSupportedIntents() []routing.Intent {
	if m.supportedIntentsFunc != nil {
		return m.supportedIntentsFunc()
	}
	return []routing.Intent{routing.IntentTask}
}

func (m *mockQueryClassifier) GetSupportedDomains() []routing.DomainName {
	if m.supportedDomainsFunc != nil {
		return m.supportedDomainsFunc()
	}
	return []routing.DomainName{routing.DomainDevelopment}
}

// TestDecisionEngine_Analyze tests the decision engine's analysis capabilities.
func TestDecisionEngine_Analyze(t *testing.T) {
	t.Run("Decide_returns_valid_execution_decision", func(t *testing.T) {
		// Setup
		engine := decision.NewDecisionEngineWithDefaults()
		ctx := context.Background()
		query := routing.Query{
			Text:      "debug this code for me",
			SessionID: "test-session",
		}
		class := routing.Classification{
			Intent:     routing.IntentTask,
			Domain:     routing.DomainDevelopment,
			Complexity: routing.ComplexityMedium,
		}

		// Execute
		decision_, err := engine.Decide(ctx, query, class)

		// Verify
		assert.NoError(t, err)
		assert.NotNil(t, decision_)
		assert.NotEmpty(t, decision_.Explanation)
	})

	t.Run("Decide_with_high_complexity_query", func(t *testing.T) {
		// Setup
		engine := decision.NewDecisionEngineWithDefaults()
		ctx := context.Background()
		query := routing.Query{
			Text:      "refactor this entire architecture and also fix all the bugs and add tests",
			SessionID: "test-session",
		}
		class := routing.Classification{
			Intent:     routing.IntentTask,
			Domain:     routing.DomainDevelopment,
			Complexity: routing.ComplexityComplex,
		}

		// Execute
		decision_, err := engine.Decide(ctx, query, class)

		// Verify
		assert.NoError(t, err)
		assert.NotNil(t, decision_)
		// Complex queries should generally get higher complexity scores
		assert.GreaterOrEqual(t, decision_.Complexity.Value, 50)
	})

	t.Run("Decide_with_simple_question", func(t *testing.T) {
		// Setup
		engine := decision.NewDecisionEngineWithDefaults()
		ctx := context.Background()
		query := routing.Query{
			Text:      "what is go?",
			SessionID: "test-session",
		}
		class := routing.Classification{
			Intent:     routing.IntentQuestion,
			Domain:     routing.DomainKnowledge,
			Complexity: routing.ComplexitySimple,
		}

		// Execute
		decision_, err := engine.Decide(ctx, query, class)

		// Verify
		assert.NoError(t, err)
		assert.NotNil(t, decision_)
		assert.NotNil(t, decision_.RoutingHint)
	})

	t.Run("GetConfig_returns_valid_config", func(t *testing.T) {
		// Setup
		engine := decision.NewDecisionEngineWithDefaults()

		// Execute
		config := engine.GetConfig()

		// Verify
		assert.NotNil(t, config)
		assert.NotNil(t, config.ComplexityAnalyzer)
		assert.NotNil(t, config.RiskAnalyzer)
		assert.NotNil(t, config.TriggerPolicy)
		assert.NotNil(t, config.PathSelector)
	})
}

// TestBasicOrchestrator_ProcessQuery tests the ProcessQuery method.
func TestBasicOrchestrator_ProcessQuery(t *testing.T) {
	t.Run("ProcessQuery_with_registered_development_agency", func(t *testing.T) {
		// Setup - use "development" as agency name since DefaultRouter routes dev domain to development
		executeCalled := false
		mockAg := &mockAgency{
			nameFunc: func() contracts.AgencyName {
				return "development"
			},
			domainFunc: func() string {
				return "development"
			},
			descriptionFunc: func() string {
				return "Development Agency"
			},
			executeFunc: func(ctx context.Context, task contracts.Task) (contracts.Result, error) {
				executeCalled = true
				return contracts.Result{
					Success: true,
					Output:  map[string]any{"response": "Hello from mock development agency"},
				}, nil
			},
		}

		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)
		orch.RegisterAgency(mockAg)

		// Execute - use query text that the BaselineClassifier will recognize as Development domain
		resp, err := orch.ProcessQuery(context.Background(), Query{
			Text:      "debug this code",
			SessionID: "test-session",
		})

		// Verify
		assert.NoError(t, err)
		assert.True(t, executeCalled)
		assert.Equal(t, "Hello from mock development agency", resp.Text)
		assert.Equal(t, "development", string(resp.Agency))
	})

	t.Run("ProcessQuery_without_registered_agency_returns_fallback", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      true,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)
		// No agency registered

		// Execute
		resp, err := orch.ProcessQuery(context.Background(), Query{
			Text:      "test query",
			SessionID: "test-session",
		})

		// Verify
		assert.NoError(t, err)
		assert.Equal(t, "FALLBACK_TO_LEGACY", resp.Text)
	})

	t.Run("ProcessQuery_with_agency_execute_error_returns_error", func(t *testing.T) {
		// Setup
		expectedErr := errors.New("agency execution failed")
		mockAg := &mockAgency{
			nameFunc: func() contracts.AgencyName {
				return "development"
			},
			domainFunc: func() string {
				return "development"
			},
			descriptionFunc: func() string {
				return "Development Agency"
			},
			executeFunc: func(ctx context.Context, task contracts.Task) (contracts.Result, error) {
				return contracts.Result{
					Success: false,
					Error:   expectedErr.Error(),
				}, expectedErr
			},
		}

		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)
		orch.RegisterAgency(mockAg)

		// Execute - use dev domain query to route to development agency
		resp, err := orch.ProcessQuery(context.Background(), Query{
			Text:      "debug this code",
			SessionID: "test-session",
		})

		// Verify
		assert.Error(t, err)
		assert.Contains(t, resp.Text, "Error executing task")
	})

	t.Run("ProcessQuery_with_disabled_fallback_respects_config", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.9, // High threshold
		}
		orch := NewBasicOrchestrator(config, nil, nil)
		// No agency registered and fallback disabled

		// Execute
		resp, err := orch.ProcessQuery(context.Background(), Query{
			Text:      "test query",
			SessionID: "test-session",
		})

		// Verify
		assert.NoError(t, err)
		assert.Equal(t, "FALLBACK_TO_LEGACY", resp.Text)
	})
}

// TestBasicOrchestrator_ClassifierAccess tests GetClassifier method.
func TestBasicOrchestrator_ClassifierAccess(t *testing.T) {
	t.Run("GetClassifier_returns_classifier", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)

		// Execute
		classifier := orch.GetClassifier()

		// Verify
		assert.NotNil(t, classifier)
	})

	t.Run("GetClassifier_returns_same_instance", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)

		// Execute
		classifier1 := orch.GetClassifier()
		classifier2 := orch.GetClassifier()

		// Verify
		assert.Same(t, classifier1, classifier2)
	})

	t.Run("GetClassifier_can_be_used_for_classification", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)
		classifier := orch.GetClassifier()

		// Execute - use "fix bug" which should be classified as IntentTask (contains "fix")
		class, err := classifier.Classify(context.Background(), routing.Query{
			Text: "fix bug in code",
		})

		// Verify
		assert.NoError(t, err)
		assert.NotNil(t, class)
		// "fix" is in taskWords, so should be IntentTask
		assert.Equal(t, routing.IntentTask, class.Intent)
	})
}

// TestBasicOrchestrator_ComponentAccess tests accessor methods for internal components.
func TestBasicOrchestrator_ComponentAccess(t *testing.T) {
	t.Run("GetDecisionEngine_returns_decision_engine", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)

		// Execute
		de := orch.GetDecisionEngine()

		// Verify
		assert.NotNil(t, de)
		assert.Implements(t, (*decision.DecisionEngine)(nil), de)
	})

	t.Run("GetPlanner_returns_planner", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)

		// Execute
		planner := orch.GetPlanner()

		// Verify
		assert.NotNil(t, planner)
	})

	t.Run("GetReviewer_returns_reviewer", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)

		// Execute
		reviewer := orch.GetReviewer()

		// Verify
		assert.NotNil(t, reviewer)
	})
}

// TestBasicOrchestrator_AgencyRegistry tests agency registration methods.
func TestBasicOrchestrator_AgencyRegistry(t *testing.T) {
	t.Run("RegisterAgency_makes_agency_available", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)
		mockAg := &mockAgency{
			nameFunc: func() contracts.AgencyName {
				return "development"
			},
			domainFunc: func() string {
				return "development"
			},
			descriptionFunc: func() string {
				return "Development Agency"
			},
		}
		orch.RegisterAgency(mockAg)

		// Execute - use a query that will be routed to development agency
		resp, err := orch.ProcessQuery(context.Background(), Query{
			Text:      "debug code error",
			SessionID: "session",
		})

		// Verify
		assert.NoError(t, err)
		assert.Equal(t, "development", string(resp.Agency))
		assert.NotEqual(t, "FALLBACK_TO_LEGACY", resp.Text)
	})

	t.Run("UnregisterAgency_removes_agency", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      true,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)
		mockAg := &mockAgency{
			nameFunc: func() contracts.AgencyName {
				return "development"
			},
		}
		orch.RegisterAgency(mockAg)

		// Execute
		orch.UnregisterAgency("development")

		// Verify
		resp, err := orch.ProcessQuery(context.Background(), Query{
			Text:      "test",
			SessionID: "session",
		})

		assert.NoError(t, err)
		assert.Equal(t, "FALLBACK_TO_LEGACY", resp.Text)
	})
}

// TestBasicOrchestrator_RouteToAgency tests the RouteToAgency method.
func TestBasicOrchestrator_RouteToAgency(t *testing.T) {
	t.Run("RouteToAgency_with_registered_agency", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "development",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)
		mockAg := &mockAgency{
			nameFunc: func() contracts.AgencyName {
				return "development"
			},
			domainFunc: func() string {
				return "development"
			},
		}
		orch.RegisterAgency(mockAg)

		// Execute - query that routes to development domain
		ag, err := orch.RouteToAgency(context.Background(), Query{
			Text: "debug this code error",
		})

		// Verify
		assert.NoError(t, err)
		assert.NotNil(t, ag)
		assert.Equal(t, contracts.AgencyName("development"), ag.Name())
	})

	t.Run("RouteToAgency_without_agency_returns_nil", func(t *testing.T) {
		// Setup
		config := OrchestratorConfig{
			EnableFallback:      false,
			DefaultAgency:       "nonexistent",
			ConfidenceThreshold: 0.5,
		}
		orch := NewBasicOrchestrator(config, nil, nil)

		// Execute - query that would route to nonexistent agency
		ag, err := orch.RouteToAgency(context.Background(), Query{
			Text: "test query",
		})

		// Verify - router returns nil when no matching agency is registered
		assert.NoError(t, err)
		assert.Nil(t, ag)
	})
}
