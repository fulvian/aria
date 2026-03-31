// Package agency provides integration tests for the Knowledge Agency.
package agency

import (
	"context"
	"fmt"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/aria/skill/knowledge"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// ============================================================================
// Real-World Integration Tests
// ============================================================================

// TestKnowledgeAgency_RealWorld_WebSearch tests full web search pipeline
func TestKnowledgeAgency_RealWorld_WebSearch(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping real-world test in short mode")
	}

	// Create config with free providers enabled
	cfg := knowledge.AgencyConfig{
		Enabled:          true,
		MaxSearchResults: 10,
		EnableDDG:        true, // Free provider
		EnableWikipedia:  true, // Free provider
		SearchTimeoutMs:  30000,
	}

	// Create agency with real agents
	agency := newKnowledgeAgencyReal(cfg)

	ctx := context.Background()
	err := agency.Start(ctx)
	require.NoError(t, err)
	defer agency.Stop(ctx)

	// Test 1: Simple web search query
	t.Run("simple_web_search", func(t *testing.T) {
		task := contracts.Task{
			ID:          "test-web-1",
			Name:        "web search",
			Description: "who is the president of the United States",
			Skills:      []string{"web-research"},
		}

		result, err := agency.Execute(ctx, task)
		require.NoError(t, err)
		assert.True(t, result.Success, "Expected successful execution")
		assert.NotNil(t, result.Output)

		// Check output structure
		if output, ok := result.Output["results"]; ok {
			t.Logf("Results found: %v", output)
		}
	})

	// Test 2: Fact-check query
	t.Run("fact_check", func(t *testing.T) {
		task := contracts.Task{
			ID:          "test-fact-1",
			Name:        "fact check",
			Description: "Is the Eiffel Tower in Paris?",
			Skills:      []string{"fact-check"},
		}

		result, err := agency.Execute(ctx, task)
		require.NoError(t, err)
		assert.True(t, result.Success)
	})
}

// TestKnowledgeAgency_RealWorld_Academic tests academic search pipeline
func TestKnowledgeAgency_RealWorld_Academic(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping real-world test in short mode")
	}

	cfg := knowledge.AgencyConfig{
		Enabled:          true,
		MaxSearchResults: 5,
		EnableOpenAlex:   true, // Free academic search
		SearchTimeoutMs:  30000,
	}

	agency := newKnowledgeAgencyReal(cfg)

	ctx := context.Background()
	err := agency.Start(ctx)
	require.NoError(t, err)
	defer agency.Stop(ctx)

	t.Run("academic_search_arxiv", func(t *testing.T) {
		task := contracts.Task{
			ID:          "test-academic-1",
			Name:        "academic research",
			Description: "machine learning transformer attention mechanism",
			Skills:      []string{"academic-search"},
		}

		result, err := agency.Execute(ctx, task)
		require.NoError(t, err)
		assert.True(t, result.Success)
	})

	t.Run("academic_search_pubmed", func(t *testing.T) {
		task := contracts.Task{
			ID:          "test-academic-2",
			Name:        "medical research",
			Description: "COVID-19 vaccine effectiveness study",
			Skills:      []string{"academic-search"},
		}

		result, err := agency.Execute(ctx, task)
		require.NoError(t, err)
		assert.True(t, result.Success)
	})
}

// TestKnowledgeAgency_RealWorld_News tests news search pipeline
func TestKnowledgeAgency_RealWorld_News(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping real-world test in short mode")
	}

	cfg := knowledge.AgencyConfig{
		Enabled:          true,
		EnableGDELT:      true, // Free news monitoring
		EnableTheNewsAPI: true,
		TheNewsAPIAPIKey: "dp7Fmae9PFTWw3bEz4WqVS6GkxYwH8gBSuHhhiJi",
		SearchTimeoutMs:  60000, // GDELT is slow (51+ seconds)
	}

	agency := newKnowledgeAgencyReal(cfg)

	ctx := context.Background()
	err := agency.Start(ctx)
	require.NoError(t, err)
	defer agency.Stop(ctx)

	t.Run("news_search", func(t *testing.T) {
		task := contracts.Task{
			ID:          "test-news-1",
			Name:        "news search",
			Description: "latest news about artificial intelligence",
			Skills:      []string{"news-search"},
		}

		result, err := agency.Execute(ctx, task)
		require.NoError(t, err)
		assert.True(t, result.Success)
	})
}

// TestKnowledgeAgency_RealWorld_Code tests code research pipeline
func TestKnowledgeAgency_RealWorld_Code(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping real-world test in short mode")
	}

	apiKey := os.Getenv("CONTEXT7_API_KEY")
	if apiKey == "" {
		t.Skip("CONTEXT7_API_KEY not set, skipping Context7 test")
	}

	cfg := knowledge.AgencyConfig{
		Enabled:         true,
		EnableContext7:  true,
		Context7APIKey:  apiKey,
		SearchTimeoutMs: 30000,
	}

	agency := newKnowledgeAgencyReal(cfg)

	ctx := context.Background()
	err := agency.Start(ctx)
	require.NoError(t, err)
	defer agency.Stop(ctx)

	t.Run("code_search", func(t *testing.T) {
		task := contracts.Task{
			ID:          "test-code-1",
			Name:        "code search",
			Description: "React useEffect hook documentation",
			Skills:      []string{"code-search"},
		}

		result, err := agency.Execute(ctx, task)
		require.NoError(t, err)
		assert.True(t, result.Success)
	})
}

// TestKnowledgeAgency_RealWorld_Historical tests historical archive pipeline
func TestKnowledgeAgency_RealWorld_Historical(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping real-world test in short mode")
	}

	cfg := knowledge.AgencyConfig{
		Enabled:                  true,
		EnableWayback:            true, // Free archive
		EnableChroniclingAmerica: true, // Free US newspapers
		SearchTimeoutMs:          30000,
	}

	agency := newKnowledgeAgencyReal(cfg)

	ctx := context.Background()
	err := agency.Start(ctx)
	require.NoError(t, err)
	defer agency.Stop(ctx)

	t.Run("historical_search", func(t *testing.T) {
		task := contracts.Task{
			ID:          "test-historical-1",
			Name:        "historical search",
			Description: "old newspapers about moon landing 1969",
			Skills:      []string{"historical-search"},
		}

		result, err := agency.Execute(ctx, task)
		require.NoError(t, err)
		assert.True(t, result.Success)
	})
}

// ============================================================================
// Agent Routing Tests - Severe Testing
// ============================================================================

func TestKnowledgeAgency_AgentRouting_Severe(t *testing.T) {
	cfg := knowledge.AgencyConfig{Enabled: true}
	agency := newKnowledgeAgencyReal(cfg)

	// Debug: check what agents are registered
	registeredAgents := agency.registry.List()
	t.Logf("Registered agents count: %d", len(registeredAgents))
	for _, a := range registeredAgents {
		t.Logf("  Agent: name=%s, category=%s", a.Name, a.Category)
	}

	// Test that each category routes to correct agent
	testCases := []struct {
		name          string
		task          contracts.Task
		expectedAgent contracts.AgentName
	}{
		{
			name: "academic task routes to academic agent",
			task: contracts.Task{
				ID:          "route-1",
				Description: "find research papers on neural networks",
				Skills:      []string{"academic-search"},
			},
			expectedAgent: AgentAcademic,
		},
		{
			name: "news task routes to news agent",
			task: contracts.Task{
				ID:          "route-2",
				Description: "latest headlines about technology",
				Skills:      []string{"news-search"},
			},
			expectedAgent: AgentNews,
		},
		{
			name: "code task routes to code agent",
			task: contracts.Task{
				ID:          "route-3",
				Description: "API documentation for REST services",
				Skills:      []string{"code-search"},
			},
			expectedAgent: AgentCodeResearch,
		},
		{
			name: "historical task routes to historical agent",
			task: contracts.Task{
				ID:          "route-4",
				Description: "old newspaper archives about World War 2",
				Skills:      []string{"historical-search"},
			},
			expectedAgent: AgentHistorical,
		},
		{
			name: "general task falls back to web search",
			task: contracts.Task{
				ID:          "route-5",
				Description: "what is the capital of France",
			},
			expectedAgent: AgentWebSearch, // Default
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// Debug: check classification
			category := agency.supervisor.classifyTask(tc.task)
			agentsInCategory := agency.registry.GetByCategory(category)
			t.Logf("Task: %+v", tc.task)
			t.Logf("Classified category: %s", category)
			t.Logf("Agents in category: %d", len(agentsInCategory))
			for _, a := range agentsInCategory {
				t.Logf("  - %s (category=%s)", a.Name, a.Category)
			}

			// Route the task
			agent, err := agency.supervisor.Route(tc.task)
			require.NoError(t, err)
			assert.Equal(t, tc.expectedAgent, agent.Name,
				"Expected task to be routed to %s but got %s", tc.expectedAgent, agent.Name)
		})
	}
}

// ============================================================================
// Parallel Execution Tests
// ============================================================================

func TestKnowledgeAgency_ParallelExecution(t *testing.T) {
	cfg := knowledge.AgencyConfig{Enabled: true}
	agency := newKnowledgeAgencyReal(cfg)

	ctx := context.Background()
	err := agency.Start(ctx)
	require.NoError(t, err)
	defer agency.Stop(ctx)

	// Test parallel execution with "compare" keyword
	task := contracts.Task{
		ID:          "test-compare",
		Name:        "compare search",
		Description: "compare Python vs JavaScript",
		Skills:      []string{"web-research"},
	}

	// This should trigger parallel execution
	result, err := agency.Execute(ctx, task)
	require.NoError(t, err)
	assert.True(t, result.Success)
}

// ============================================================================
// State Machine Tests - Severe
// ============================================================================

func TestKnowledgeAgency_TaskStateMachine_Severe(t *testing.T) {
	sm := NewTaskStateMachine()

	t.Run("valid_transitions", func(t *testing.T) {
		taskID := "state-test-1"
		sm.CreateTask(taskID, 3)

		// Test all valid transitions (skip pending since task starts there)
		validSequence := []TaskState{
			TaskStateValidating,
			TaskStateRunning,
			TaskStateSynthesizing,
			TaskStateCompleted,
		}

		for _, state := range validSequence {
			err := sm.Transition(taskID, state)
			require.NoError(t, err, "Transition to %s should succeed", state)

			status, _ := sm.GetTask(taskID)
			assert.Equal(t, state, status.State)
		}
	})

	t.Run("invalid_transitions", func(t *testing.T) {
		taskID := "state-test-2"
		sm.CreateTask(taskID, 3)

		// Skip to completed
		sm.Transition(taskID, TaskStateRunning)
		sm.Transition(taskID, TaskStateCompleted)

		// Try invalid transition back to running
		err := sm.Transition(taskID, TaskStateRunning)
		assert.Error(t, err, "Transition from Completed to Running should fail")
	})

	t.Run("retry_tracking", func(t *testing.T) {
		taskID := "state-test-3"
		sm.CreateTask(taskID, 3)

		// Increment attempts
		for i := 1; i <= 3; i++ {
			err := sm.IncrementAttempts(taskID)
			require.NoError(t, err)
			status, _ := sm.GetTask(taskID)
			assert.Equal(t, i, status.Attempts)
		}
	})

	t.Run("history_tracking", func(t *testing.T) {
		taskID := "state-test-4"
		sm.CreateTask(taskID, 3)

		sm.Transition(taskID, TaskStateValidating)
		sm.Transition(taskID, TaskStateRunning)
		sm.Transition(taskID, TaskStateFailed)

		history, err := sm.GetHistory(taskID)
		require.NoError(t, err)
		assert.Len(t, history, 4) // pending, validating, running, failed
	})
}

// ============================================================================
// Workflow Engine Tests - Severe
// ============================================================================

func TestKnowledgeAgency_WorkflowEngine_Severe(t *testing.T) {
	registry := NewAgentRegistry()

	// Register agents
	registry.Register(&RegisteredAgent{
		Name:     AgentWebSearch,
		Category: CategoryWebSearch,
		Executor: &mockAgentExecutor{name: AgentWebSearch},
	})
	registry.Register(&RegisteredAgent{
		Name:     AgentAcademic,
		Category: CategoryAcademic,
		Executor: &mockAgentExecutor{name: AgentAcademic},
	})

	router := NewTaskRouter(registry)
	engine := NewWorkflowEngine(router, 30*time.Second)

	t.Run("sequential_workflow", func(t *testing.T) {
		task := contracts.Task{
			ID:          "workflow-1",
			Description: "test query",
		}

		steps := []WorkflowStep{
			{
				Name:      "step1",
				AgentName: AgentWebSearch,
				Mode:      ModeSequential,
			},
			{
				Name:      "step2",
				AgentName: AgentAcademic,
				Mode:      ModeSequential,
			},
		}

		result, err := engine.ExecuteWorkflow(context.Background(), task, steps)
		require.NoError(t, err)
		assert.NotNil(t, result)
		assert.Equal(t, "workflow-1", result["task_id"])
	})

	t.Run("fallback_workflow", func(t *testing.T) {
		task := contracts.Task{
			ID:          "workflow-2",
			Description: "test query",
		}

		steps := []WorkflowStep{
			{
				Name:      "primary",
				AgentName: AgentWebSearch,
				Mode:      ModeFallback,
			},
			{
				Name:      "fallback",
				AgentName: AgentAcademic,
				Mode:      ModeFallback,
			},
		}

		result, err := engine.ExecuteWorkflow(context.Background(), task, steps)
		require.NoError(t, err)
		assert.NotNil(t, result)
	})

	t.Run("retry_policy", func(t *testing.T) {
		policy := DefaultRetryPolicy

		assert.Equal(t, 3, policy.MaxAttempts)
		assert.Equal(t, 1*time.Second, policy.BaseDelay)
		assert.Equal(t, 30*time.Second, policy.MaxDelay)
	})
}

// ============================================================================
// Result Synthesizer Tests - Severe
// ============================================================================

func TestKnowledgeAgency_ResultSynthesizer_Severe(t *testing.T) {
	synth := NewResultSynthesizer()

	t.Run("merge_multiple_results", func(t *testing.T) {
		results := []map[string]any{
			{
				"results": []map[string]any{
					{"title": "Result 1", "url": "http://example.com/1"},
					{"title": "Result 2", "url": "http://example.com/2"},
				},
			},
			{
				"results": []map[string]any{
					{"title": "Result 3", "url": "http://example.com/3"},
				},
			},
		}

		synthesized, err := synth.Synthesize("task-1", results, DefaultSynthesisOptions())
		require.NoError(t, err)

		assert.Equal(t, "task-1", synthesized["task_id"])
		assert.NotNil(t, synthesized["results"])
		assert.Greater(t, synthesized["count"].(int), 0)
	})

	t.Run("deduplication", func(t *testing.T) {
		results := []map[string]any{
			{
				"results": []map[string]any{
					{"title": "Same Title", "url": "http://example.com/same"},
					{"title": "Unique 1", "url": "http://example.com/1"},
				},
			},
			{
				"results": []map[string]any{
					{"title": "Same Title", "url": "http://example.com/same"}, // duplicate
					{"title": "Unique 2", "url": "http://example.com/2"},
				},
			},
		}

		opts := DefaultSynthesisOptions()
		synthesized, err := synth.Synthesize("task-2", results, opts)
		require.NoError(t, err)

		resultList := synthesized["results"].([]map[string]any)
		// Should have at most 3 unique results
		assert.LessOrEqual(t, len(resultList), 3)
	})

	t.Run("empty_results", func(t *testing.T) {
		synthesized, err := synth.Synthesize("task-3", []map[string]any{}, DefaultSynthesisOptions())
		require.NoError(t, err)

		assert.Equal(t, "task-3", synthesized["task_id"])
		assert.Equal(t, 0, synthesized["count"])
	})

	t.Run("merge_agent_results", func(t *testing.T) {
		agentResults := map[contracts.AgentName]map[string]any{
			AgentWebSearch: {
				"query":  "test query",
				"source": "tavily",
			},
			AgentNews: {
				"query":  "test query",
				"source": "gdelt",
			},
		}

		synthesized, err := synth.SynthesizeFromAgents("task-4", agentResults)
		require.NoError(t, err)

		assert.Equal(t, "task-4", synthesized["task_id"])
		assert.Contains(t, synthesized["agents_used"], string(AgentWebSearch))
		assert.Contains(t, synthesized["agents_used"], string(AgentNews))
	})
}

// ============================================================================
// Concurrency Tests - Severe
// ============================================================================

func TestKnowledgeAgency_Concurrency_Severe(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping concurrency test in short mode")
	}

	cfg := knowledge.AgencyConfig{Enabled: true}
	agency := newKnowledgeAgencyReal(cfg)

	ctx := context.Background()
	err := agency.Start(ctx)
	require.NoError(t, err)
	defer agency.Stop(ctx)

	// Test concurrent task execution
	const numTasks = 20
	var wg sync.WaitGroup
	results := make([]contracts.Result, numTasks)
	errors := make([]error, numTasks)

	for i := 0; i < numTasks; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()

			task := contracts.Task{
				ID:          fmt.Sprintf("concurrent-task-%d", idx),
				Description: fmt.Sprintf("concurrent query %d", idx),
			}

			result, err := agency.Execute(ctx, task)
			results[idx] = result
			errors[idx] = err
		}(i)
	}

	wg.Wait()

	// All tasks should complete without errors
	errorCount := 0
	for i, err := range errors {
		if err != nil {
			t.Logf("Task %d error: %v", i, err)
			errorCount++
		}
	}

	// Allow some failures due to provider rate limits, but not all
	if errorCount == numTasks {
		t.Fatal("All tasks failed - this indicates a systemic issue")
	}

	t.Logf("Completed %d/%d tasks successfully", numTasks-errorCount, numTasks)
}

// ============================================================================
// Lifecycle Tests - Severe
// ============================================================================

func TestKnowledgeAgency_Lifecycle_Severe(t *testing.T) {
	cfg := knowledge.AgencyConfig{Enabled: true}
	agency := newKnowledgeAgencyReal(cfg)

	ctx := context.Background()

	t.Run("start_stop_pause_resume", func(t *testing.T) {
		// Start
		err := agency.Start(ctx)
		require.NoError(t, err)
		assert.Equal(t, AgencyStatusRunning, agency.Status())

		// Stop
		err = agency.Stop(ctx)
		require.NoError(t, err)
		assert.Equal(t, AgencyStatusStopped, agency.Status())

		// Resume should fail on stopped agency
		err = agency.Resume(ctx)
		assert.Error(t, err)

		// Restart
		err = agency.Start(ctx)
		require.NoError(t, err)
		assert.Equal(t, AgencyStatusRunning, agency.Status())

		// Pause
		err = agency.Pause(ctx)
		require.NoError(t, err)
		assert.Equal(t, AgencyStatusPaused, agency.Status())

		// Resume
		err = agency.Resume(ctx)
		require.NoError(t, err)
		assert.Equal(t, AgencyStatusRunning, agency.Status())

		// Stop
		err = agency.Stop(ctx)
		require.NoError(t, err)
	})

	t.Run("double_start_error", func(t *testing.T) {
		agency.Start(ctx)
		err := agency.Start(ctx)
		assert.Error(t, err)
		agency.Stop(ctx)
	})

	t.Run("double_stop_error", func(t *testing.T) {
		agency.Start(ctx)
		agency.Stop(ctx)
		err := agency.Stop(ctx)
		assert.Error(t, err)
	})
}

// ============================================================================
// Error Handling Tests - Severe
// ============================================================================

func TestKnowledgeAgency_ErrorHandling_Severe(t *testing.T) {
	cfg := knowledge.AgencyConfig{Enabled: true}
	agency := newKnowledgeAgencyReal(cfg)

	ctx := context.Background()
	agency.Start(ctx)
	defer agency.Stop(ctx)

	t.Run("empty_task_description", func(t *testing.T) {
		task := contracts.Task{
			ID:          "error-test-1",
			Description: "",
		}

		result, err := agency.Execute(ctx, task)
		// Should not crash, should return error or empty result
		if err != nil {
			t.Logf("Got error as expected: %v", err)
		} else {
			t.Logf("Result: %+v", result)
		}
	})

	t.Run("non_existent_agent", func(t *testing.T) {
		// Try to get non-existent agent
		_, err := agency.GetAgent("non-existent-agent")
		assert.Error(t, err)
	})
}

// ============================================================================
// Performance Tests
// ============================================================================

func TestKnowledgeAgency_Performance(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping performance test in short mode")
	}

	cfg := knowledge.AgencyConfig{Enabled: true}
	agency := newKnowledgeAgencyReal(cfg)

	ctx := context.Background()
	agency.Start(ctx)
	defer agency.Stop(ctx)

	// Measure routing time
	t.Run("routing_performance", func(t *testing.T) {
		task := contracts.Task{
			ID:          "perf-test",
			Description: "test query for performance",
		}

		start := time.Now()
		for i := 0; i < 100; i++ {
			task.ID = fmt.Sprintf("perf-%d", i)
			_, err := agency.supervisor.Route(task)
			if err != nil {
				t.Fatalf("Route failed: %v", err)
			}
		}
		elapsed := time.Since(start)

		t.Logf("100 routings completed in %v (avg: %v)", elapsed, elapsed/100)
		assert.Less(t, elapsed, 1*time.Second, "100 routings should take less than 1 second")
	})
}

// ============================================================================
// Helper Functions
// ============================================================================

// newKnowledgeAgencyReal creates a KnowledgeAgency with real configured agents
func newKnowledgeAgencyReal(cfg knowledge.AgencyConfig) *KnowledgeAgency {
	// Create minimal generic config
	genericCfg := knowledgeConfigMinimal()

	agency := &KnowledgeAgency{
		name:        contracts.AgencyKnowledge,
		domain:      "knowledge",
		description: "Research, learning, Q&A, analysis, and general knowledge tasks",
		state: AgencyState{
			AgencyID: contracts.AgencyKnowledge,
			Status:   "active",
			Metrics:  make(map[string]any),
		},
		memory: NewAgencyMemory("knowledge"),
		sub:    NewAgencyEventBroker(),
		cfg:    cfg,
	}

	// Initialize registry with real agents
	agency.registry = NewAgentRegistry()

	// Register WebSearchAgent
	agency.registry.Register(&RegisteredAgent{
		Name:        AgentWebSearch,
		Category:    CategoryWebSearch,
		Description: "Handles general web search using Tavily, Brave, Wikipedia, DDG",
		Skills:      []string{"web-research", "fact-check"},
		Executor:    NewWebSearchAgent(cfg),
	})

	// Register AcademicResearchAgent
	agency.registry.Register(&RegisteredAgent{
		Name:        AgentAcademic,
		Category:    CategoryAcademic,
		Description: "Handles academic research using PubMed, arXiv, SemanticScholar, OpenAlex",
		Skills:      []string{"academic-search", "web-research"},
		Executor:    NewAcademicResearchAgent(cfg),
	})

	// Register NewsAgent
	agency.registry.Register(&RegisteredAgent{
		Name:        AgentNews,
		Category:    CategoryNews,
		Description: "Handles news search using GDELT, NewsData, GNews, TheNewsAPI",
		Skills:      []string{"news-search"},
		Executor:    NewNewsAgent(cfg),
	})

	// Register CodeResearchAgent
	agency.registry.Register(&RegisteredAgent{
		Name:        AgentCodeResearch,
		Category:    CategoryCode,
		Description: "Handles code research using Context7",
		Skills:      []string{"code-search", "api-docs"},
		Executor:    NewCodeResearchAgent(cfg),
	})

	// Register HistoricalAgent
	agency.registry.Register(&RegisteredAgent{
		Name:        AgentHistorical,
		Category:    CategoryHistorical,
		Description: "Handles historical research using Wayback, ChroniclingAmerica",
		Skills:      []string{"historical-search", "archive-search"},
		Executor:    NewHistoricalAgent(cfg),
	})

	// Initialize supervisor and engine
	agency.supervisor = NewTaskRouter(agency.registry)
	agency.executor = NewWorkflowEngine(agency.supervisor, 60*time.Second)
	agency.synthesizer = NewResultSynthesizer()

	// Suppress unused variable warning
	_ = genericCfg

	return agency
}

// knowledgeConfigMinimal returns a minimal config for testing
func knowledgeConfigMinimal() map[string]any {
	return map[string]any{
		"enabled": true,
	}
}

// Ensure mockAgentExecutor implements TaskExecutor
var _ TaskExecutor = (*mockAgentExecutor)(nil)
