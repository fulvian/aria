// Package agency provides the Knowledge Agency implementation.
package agency

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"

	ariaConfig "github.com/fulvian/aria/internal/aria/config"
	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/aria/skill"
	"github.com/fulvian/aria/internal/aria/skill/knowledge"
)

// KnowledgeAgency is the knowledge-focused agency for research, education, and analysis tasks.
// It implements a proper hierarchical multi-agent architecture with:
//
//   - Supervisor: Routes tasks to appropriate agents based on capabilities
//   - Agent Registry: Maintains registered agents with their specializations
//   - Workflow Engine: Executes tasks following defined procedures
//   - Task State Machine: Manages task lifecycle and state transitions
//   - Result Synthesizer: Combines results from multiple agents
//
// Reference: Blueprint Section 2.2.2 - Agency System
type KnowledgeAgency struct {
	name        contracts.AgencyName
	domain      string
	description string
	state       AgencyState
	memory      *AgencyMemory

	// Lifecycle state
	status    AgencyStatus
	startTime time.Time
	pauseTime time.Time

	// Core components - hierarchical architecture
	supervisor  *TaskRouter        // Routes tasks to agents
	registry    *AgentRegistry     // Agent registry with capabilities
	executor    *WorkflowEngine    // Workflow execution engine
	synthesizer *ResultSynthesizer // Result synthesis

	// Legacy bridges for compatibility
	researcherBridge ResearchBridge
	educatorBridge   EducationBridge
	analystBridge    AnalysisBridge

	// Configuration
	cfg knowledge.AgencyConfig

	// subscribed events
	sub *AgencyEventBroker
}

// NewKnowledgeAgency creates a new Knowledge Agency with full hierarchical architecture.
func NewKnowledgeAgency(cfg ariaConfig.KnowledgeConfig) *KnowledgeAgency {
	// Convert config to knowledge agency config
	knowledgeCfg := knowledgeAgencyConfigFromGeneric(cfg)

	// Initialize the agent registry with specialized agents
	registry := NewAgentRegistry()
	registerKnowledgeAgents(registry, knowledgeCfg)

	// Initialize supervisor with semantic routing capabilities
	// The TaskRouter uses embeddings for intelligent routing with keyword fallback
	embedder := NewSimpleEmbedder()
	supervisor := NewTaskRouter(registry)
	supervisor.semanticRouter = NewSemanticTaskRouter(registry, embedder)

	// Initialize workflow engine
	executor := NewWorkflowEngine(supervisor, 60*time.Second)

	// Initialize result synthesizer
	synthesizer := NewResultSynthesizer()

	// Initialize providers for legacy bridges
	providerChain := knowledge.NewProviderChain(knowledgeCfg)
	webResearchSkill := skill.NewWebResearchSkill(providerChain)

	agency := &KnowledgeAgency{
		name:        contracts.AgencyKnowledge,
		domain:      "knowledge",
		description: "Research, learning, Q&A, analysis, and general knowledge tasks",
		state: AgencyState{
			AgencyID: contracts.AgencyKnowledge,
			Status:   "active",
			Metrics:  make(map[string]any),
		},
		memory:           NewAgencyMemory("knowledge"),
		sub:              NewAgencyEventBroker(),
		cfg:              knowledgeCfg,
		supervisor:       supervisor,
		registry:         registry,
		executor:         executor,
		synthesizer:      synthesizer,
		researcherBridge: NewResearchBridge(webResearchSkill, cfg),
		educatorBridge:   NewEducationBridge(cfg),
		analystBridge:    NewAnalysisBridge(cfg),
	}

	return agency
}

// registerKnowledgeAgents registers all specialized knowledge agents.
func registerKnowledgeAgents(registry *AgentRegistry, cfg knowledge.AgencyConfig) {
	// WebSearchAgent - General web search
	registry.Register(&RegisteredAgent{
		Name:        AgentWebSearch,
		Category:    CategoryWebSearch,
		Description: "Handles general web search tasks using Tavily, Brave, Wikipedia, DDG",
		Skills:      []string{"web-research", "fact-check"},
		Executor:    NewWebSearchAgent(cfg),
	})

	// AcademicResearchAgent - Scientific/academic research
	registry.Register(&RegisteredAgent{
		Name:        AgentAcademic,
		Category:    CategoryAcademic,
		Description: "Handles academic research using PubMed, arXiv, SemanticScholar, OpenAlex",
		Skills:      []string{"academic-search", "web-research"},
		Executor:    NewAcademicResearchAgent(cfg),
	})

	// NewsAgent - News and current events
	registry.Register(&RegisteredAgent{
		Name:        AgentNews,
		Category:    CategoryNews,
		Description: "Handles news search using GDELT, NewsData, GNews, TheNewsAPI",
		Skills:      []string{"news-search"},
		Executor:    NewNewsAgent(cfg),
	})

	// CodeResearchAgent - Code and API documentation
	registry.Register(&RegisteredAgent{
		Name:        AgentCodeResearch,
		Category:    CategoryCode,
		Description: "Handles code research using Context7",
		Skills:      []string{"code-search", "api-docs"},
		Executor:    NewCodeResearchAgent(cfg),
	})

	// HistoricalAgent - Historical archives
	registry.Register(&RegisteredAgent{
		Name:        AgentHistorical,
		Category:    CategoryHistorical,
		Description: "Handles historical research using Wayback, ChroniclingAmerica",
		Skills:      []string{"historical-search", "archive-search"},
		Executor:    NewHistoricalAgent(cfg),
	})
}

// Name returns the agency name.
func (a *KnowledgeAgency) Name() contracts.AgencyName {
	return a.name
}

// Domain returns the domain.
func (a *KnowledgeAgency) Domain() string {
	return a.domain
}

// Description returns the description.
func (a *KnowledgeAgency) Description() string {
	return a.description
}

// Agents returns the list of registered agent names.
func (a *KnowledgeAgency) Agents() []contracts.AgentName {
	agents := a.registry.List()
	names := make([]contracts.AgentName, len(agents))
	for i, agent := range agents {
		names[i] = agent.Name
	}
	return names
}

// GetAgent returns an agent by name.
func (a *KnowledgeAgency) GetAgent(name contracts.AgentName) (interface{}, error) {
	// Try registry first
	if agent, err := a.registry.Get(name); err == nil {
		return agent, nil
	}

	// Fallback to legacy bridges
	switch name {
	case "researcher":
		return a.researcherBridge, nil
	case "educator":
		return a.educatorBridge, nil
	case "analyst":
		return a.analystBridge, nil
	default:
		return nil, fmt.Errorf("agent not found: %s", name)
	}
}

// Execute executes a task using the hierarchical multi-agent architecture.
func (a *KnowledgeAgency) Execute(ctx context.Context, task contracts.Task) (contracts.Result, error) {
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

	// Route task to appropriate agent(s) using supervisor
	agent, err := a.supervisor.Route(task)
	if err != nil {
		return a.handleExecutionError(ctx, task, start, err)
	}

	// Determine execution mode based on task complexity
	executionMode := a.determineExecutionMode(task)

	var result map[string]any

	switch executionMode {
	case "single":
		// Single agent execution with fallback
		result, err = a.executeWithFallback(ctx, task, agent)
	case "workflow":
		// Multi-step workflow execution
		result, err = a.executeWorkflow(ctx, task, agent)
	case "parallel":
		// Parallel execution with synthesis
		result, err = a.executeParallel(ctx, task, agent)
	default:
		// Default to single with fallback
		result, err = a.executeWithFallback(ctx, task, agent)
	}

	if err != nil {
		return a.handleExecutionError(ctx, task, start, err)
	}

	// Synthesize results if needed
	if result != nil {
		synthesized, err := a.synthesizer.Synthesize(task.ID, []map[string]any{result}, DefaultSynthesisOptions())
		if err == nil {
			result = synthesized
		}
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

// executeWithFallback executes task with primary agent and fallback chain.
func (a *KnowledgeAgency) executeWithFallback(ctx context.Context, task contracts.Task, primary *RegisteredAgent) (map[string]any, error) {
	// Execute with primary agent
	result, err := a.executeAgentTask(ctx, task, primary)
	if err == nil {
		return result, nil
	}

	// Try fallback agents
	fallbackAgents, _ := a.supervisor.RouteWithFallback(task)
	for _, fallback := range fallbackAgents {
		if fallback.Name == primary.Name {
			continue // Skip primary
		}

		result, err = a.executeAgentTask(ctx, task, fallback)
		if err == nil {
			return result, nil
		}
	}

	return nil, fmt.Errorf("all agents failed: %w", err)
}

// executeAgentTask executes a task using a specific agent.
func (a *KnowledgeAgency) executeAgentTask(ctx context.Context, task contracts.Task, agent *RegisteredAgent) (map[string]any, error) {
	if executor, ok := agent.Executor.(TaskExecutor); ok {
		return executor.Execute(ctx, task)
	}
	return nil, fmt.Errorf("agent %s does not implement TaskExecutor", agent.Name)
}

// determineExecutionMode determines how to execute a task based on its characteristics.
func (a *KnowledgeAgency) determineExecutionMode(task contracts.Task) string {
	// Check if task requires multiple skills or complex workflow
	if len(task.Skills) > 1 {
		return "workflow"
	}

	// Check for parallel execution hints
	if strings.Contains(strings.ToLower(task.Description), "compare") ||
		strings.Contains(strings.ToLower(task.Description), "all sources") {
		return "parallel"
	}

	return "single"
}

// executeWorkflow executes a multi-step workflow.
func (a *KnowledgeAgency) executeWorkflow(ctx context.Context, task contracts.Task, agent *RegisteredAgent) (map[string]any, error) {
	// Determine workflow steps based on task
	var steps []WorkflowStep

	skillName := "web-research"
	if len(task.Skills) > 0 {
		skillName = task.Skills[0]
	}

	steps = []WorkflowStep{
		{
			Name:      "validate",
			AgentName: agent.Name,
			Skill:     "validation",
			Mode:      ModeSequential,
			Timeout:   10 * time.Second,
		},
		{
			Name:        "research",
			AgentName:   agent.Name,
			Skill:       skillName,
			Mode:        ModeSequential,
			RetryPolicy: DefaultRetryPolicy,
			Timeout:     60 * time.Second,
		},
	}

	return a.executor.ExecuteWorkflow(ctx, task, steps)
}

// executeParallel executes task across multiple agents and synthesizes.
func (a *KnowledgeAgency) executeParallel(ctx context.Context, task contracts.Task, primary *RegisteredAgent) (map[string]any, error) {
	agents := a.registry.GetByCategory(primary.Category)
	if len(agents) == 0 {
		return a.executeAgentTask(ctx, task, primary)
	}

	// Limit concurrent executions
	maxConcurrent := 3
	if maxConcurrent > len(agents) {
		maxConcurrent = len(agents)
	}
	sem := make(chan struct{}, maxConcurrent)

	var wg sync.WaitGroup
	mu := sync.Mutex{}
	results := []map[string]any{}
	var lastErr error

	for _, agent := range agents {
		wg.Add(1)
		go func(ag *RegisteredAgent) {
			defer wg.Done()

			// Acquire semaphore
			select {
			case sem <- struct{}{}:
				defer func() { <-sem }()
			case <-ctx.Done():
				return
			}

			result, err := a.executeAgentTask(ctx, task, ag)
			mu.Lock()
			if err != nil {
				lastErr = err
			} else {
				results = append(results, result)
			}
			mu.Unlock()
		}(agent)
	}

	wg.Wait()

	if len(results) == 0 && lastErr != nil {
		return nil, lastErr
	}

	// Synthesize results
	return a.synthesizer.Synthesize(task.ID, results, DefaultSynthesisOptions())
}

// handleExecutionError handles execution errors consistently.
func (a *KnowledgeAgency) handleExecutionError(ctx context.Context, task contracts.Task, start time.Time, err error) (contracts.Result, error) {
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

// GetState returns the current state.
func (a *KnowledgeAgency) GetState() AgencyState {
	return a.state
}

// SaveState saves the agency state.
func (a *KnowledgeAgency) SaveState(state AgencyState) error {
	a.state = state
	return nil
}

// Memory returns the agency memory.
func (a *KnowledgeAgency) Memory() DomainMemory {
	return a.memory
}

// Subscribe returns a channel for receiving agency events.
func (a *KnowledgeAgency) Subscribe(ctx context.Context) <-chan contracts.AgencyEvent {
	return a.sub.Subscribe(ctx)
}

// Start starts the knowledge agency.
func (a *KnowledgeAgency) Start(ctx context.Context) error {
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

	// Log registered agents
	agents := a.registry.List()
	agentNames := make([]string, len(agents))
	for i, ag := range agents {
		agentNames[i] = string(ag.Name)
	}
	a.state.Metrics["registered_agents"] = agentNames

	return nil
}

// Stop stops the knowledge agency.
func (a *KnowledgeAgency) Stop(ctx context.Context) error {
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

// Pause pauses the knowledge agency.
func (a *KnowledgeAgency) Pause(ctx context.Context) error {
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

// Resume resumes the knowledge agency.
func (a *KnowledgeAgency) Resume(ctx context.Context) error {
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
func (a *KnowledgeAgency) Status() AgencyStatus {
	return a.status
}

// ============================================================================
// Bridge Interfaces (for legacy compatibility)
// ============================================================================

// ResearchBridge defines the interface for research operations.
type ResearchBridge interface {
	ConductResearch(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}

// EducationBridge defines the interface for education operations.
type EducationBridge interface {
	Teach(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}

// AnalysisBridge defines the interface for analysis operations.
type AnalysisBridge interface {
	Analyze(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}

// ============================================================================
// Bridge Implementations
// ============================================================================

// ResearchBridgeImpl implements ResearchBridge using WebResearchSkill.
type ResearchBridgeImpl struct {
	skill *skill.WebResearchSkill
	cfg   ariaConfig.KnowledgeConfig
}

// NewResearchBridge creates a new ResearchBridge.
func NewResearchBridge(s *skill.WebResearchSkill, cfg ariaConfig.KnowledgeConfig) *ResearchBridgeImpl {
	return &ResearchBridgeImpl{skill: s, cfg: cfg}
}

// ConductResearch handles research tasks.
func (b *ResearchBridgeImpl) ConductResearch(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error) {
	// Extract parameters from task
	input := make(map[string]any)
	if task.Parameters != nil {
		for k, v := range task.Parameters {
			input[k] = v
		}
	}
	// Also include description as potential query
	if task.Description != "" && input["query"] == nil {
		input["query"] = task.Description
	}

	// Set max results from config
	if input["max_results"] == nil {
		input["max_results"] = b.cfg.MaxSearchResults
	}

	// Execute the skill
	result, err := b.skill.Execute(ctx, skill.SkillParams{
		TaskID: task.ID,
		Input:  input,
		Context: map[string]any{
			"task_name": task.Name,
			"skill":     skillName,
		},
	})

	if err != nil {
		return nil, fmt.Errorf("research error: %w", err)
	}

	if !result.Success {
		return nil, fmt.Errorf("research failed: %s", result.Error)
	}

	return result.Output, nil
}

// EducationBridgeImpl implements EducationBridge.
type EducationBridgeImpl struct {
	cfg ariaConfig.KnowledgeConfig
}

// NewEducationBridge creates a new EducationBridge.
func NewEducationBridge(cfg ariaConfig.KnowledgeConfig) *EducationBridgeImpl {
	return &EducationBridgeImpl{cfg: cfg}
}

// Teach handles education/teaching tasks.
func (b *EducationBridgeImpl) Teach(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error) {
	// Extract parameters from task
	input := make(map[string]any)
	if task.Parameters != nil {
		for k, v := range task.Parameters {
			input[k] = v
		}
	}
	if task.Description != "" {
		input["content"] = task.Description
	}

	// Default skill based on input
	effectiveSkill := skillName
	if effectiveSkill == "" {
		if input["audience"] != nil || input["level"] != nil {
			effectiveSkill = "simplification"
		} else {
			effectiveSkill = "summarization"
		}
	}

	// Generate education response based on skill
	return b.generateEducation(ctx, task, input, effectiveSkill)
}

// generateEducation generates educational content based on the skill type.
func (b *EducationBridgeImpl) generateEducation(ctx context.Context, task contracts.Task, input map[string]any, skillName string) (map[string]any, error) {
	content, _ := input["content"].(string)
	query := task.Description
	if content == "" {
		content = query
	}

	var summary, bulletPoints string
	var glossary []map[string]any
	var examples []map[string]any

	// Extract topic for examples
	topic := content
	if len(topic) > 100 {
		topic = topic[:100]
	}

	switch skillName {
	case "simplification":
		// Generate simplified explanation
		summary = fmt.Sprintf("Simplified explanation of: %s", topic)
		glossary = []map[string]any{
			{"term": topic, "definition": "A simplified overview is provided above."},
		}
	case "examples":
		// Generate examples
		summary = fmt.Sprintf("Examples related to: %s", topic)
		examples = []map[string]any{
			{"example": fmt.Sprintf("Example 1 related to %s", topic)},
			{"example": fmt.Sprintf("Example 2 related to %s", topic)},
		}
	default: // summarization
		summary = fmt.Sprintf("Summary of: %s", topic)
		// Generate bullet points from content
		bulletPoints = fmt.Sprintf("- Key point about: %s", topic)
	}

	return map[string]any{
		"task_id":       task.ID,
		"content":       content,
		"summary":       summary,
		"bullet_points": bulletPoints,
		"glossary":      glossary,
		"examples":      examples,
		"skill":         skillName,
		"api_source":    "knowledge-agency",
		"integration":   "skill-based",
	}, nil
}

// AnalysisBridgeImpl implements AnalysisBridge.
type AnalysisBridgeImpl struct {
	cfg ariaConfig.KnowledgeConfig
}

// NewAnalysisBridge creates a new AnalysisBridge.
func NewAnalysisBridge(cfg ariaConfig.KnowledgeConfig) *AnalysisBridgeImpl {
	return &AnalysisBridgeImpl{cfg: cfg}
}

// Analyze handles analysis tasks.
func (b *AnalysisBridgeImpl) Analyze(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error) {
	// Extract parameters from task
	input := make(map[string]any)
	if task.Parameters != nil {
		for k, v := range task.Parameters {
			input[k] = v
		}
	}
	if task.Description != "" {
		input["content"] = task.Description
	}

	// Default skill
	effectiveSkill := skillName
	if effectiveSkill == "" {
		effectiveSkill = "synthesis"
	}

	// Generate analysis response
	return b.generateAnalysis(ctx, task, input, effectiveSkill)
}

// generateAnalysis generates analytical content based on the skill type.
func (b *AnalysisBridgeImpl) generateAnalysis(ctx context.Context, task contracts.Task, input map[string]any, skillName string) (map[string]any, error) {
	content := task.Description
	if content == "" {
		content = "No content provided for analysis"
	}

	// Extract items if this is a comparison
	items := []string{}
	if itemsRaw, ok := input["items"].([]any); ok {
		for _, item := range itemsRaw {
			if s, ok := item.(string); ok {
				items = append(items, s)
			}
		}
	}

	var synthesis, agreements, disagreements, gaps string
	var comparisonTable []map[string]any

	switch skillName {
	case "comparison":
		// Generate comparison
		comparisonTable = []map[string]any{
			{"item": "Item 1", "comparison": "Aspect 1"},
			{"item": "Item 2", "comparison": "Aspect 2"},
		}
	case "data-analysis":
		// Generate data analysis findings
		synthesis = "Key findings from data analysis"
	case "synthesis":
		// Synthesize information
		synthesis = "Synthesized information from multiple sources"
		agreements = "Areas of agreement identified"
		disagreements = "Areas of disagreement identified"
		gaps = "Information gaps discovered"
	default:
		synthesis = "Analysis complete"
	}

	return map[string]any{
		"task_id":          task.ID,
		"content":          content,
		"items":            items,
		"synthesis":        synthesis,
		"agreements":       agreements,
		"disagreements":    disagreements,
		"gaps":             gaps,
		"comparison_table": comparisonTable,
		"skill":            skillName,
		"api_source":       "knowledge-agency",
		"integration":      "skill-based",
	}, nil
}

// knowledgeAgencyConfigFromGeneric converts generic KnowledgeConfig to AgencyConfig.
func knowledgeAgencyConfigFromGeneric(cfg ariaConfig.KnowledgeConfig) knowledge.AgencyConfig {
	return knowledge.AgencyConfig{
		Enabled:               cfg.Enabled,
		DefaultProvider:       cfg.DefaultProvider,
		TavilyAPIKey:          cfg.TavilyAPIKey,
		BraveAPIKey:           cfg.BraveAPIKey,
		BingAPIKey:            cfg.BingAPIKey,
		MaxSearchResults:      cfg.MaxSearchResults,
		SearchTimeoutMs:       cfg.SearchTimeoutMs,
		MaxRetries:            cfg.MaxRetries,
		RetryBaseDelayMs:      cfg.RetryBaseDelayMs,
		EnableMemory:          cfg.EnableMemory,
		MemoryTopK:            cfg.MemoryTopK,
		SaveEpisodes:          cfg.SaveEpisodes,
		SaveFacts:             cfg.SaveFacts,
		EnableWikipedia:       cfg.EnableWikipedia,
		EnableDDG:             cfg.EnableDDG,
		EnableBing:            cfg.EnableBing,
		EnableDocumentPDF:     cfg.EnableDocumentPDF,
		DefaultLanguage:       cfg.DefaultLanguage,
		DefaultRegion:         cfg.DefaultRegion,
		EnablePubMed:          cfg.EnablePubMed,
		EnableArXiv:           cfg.EnableArXiv,
		EnableSemanticScholar: cfg.EnableSemanticScholar,
		EnableValyu:           cfg.EnableValyu,
		ValyuAPIKey:           cfg.ValyuAPIKey,
		EnableCrossRef:        cfg.EnableCrossRef,
		CrossRefEmail:         cfg.CrossRefEmail,
		EnableBGPT:            cfg.EnableBGPT,
		BGPTAPIKey:            cfg.BGPTAPIKey,
		// New free providers
		EnableOpenAlex: cfg.EnableOpenAlex,
		EnableGDELT:    cfg.EnableGDELT,
		EnableWayback:  cfg.EnableWayback,
		EnableJina:     cfg.EnableJina,
		EnableYouCom:   cfg.EnableYouCom,
		YouComAPIKey:   cfg.YouComAPIKey,
		EnableContext7: cfg.EnableContext7,
		Context7APIKey: cfg.Context7APIKey,
		// News archive providers
		EnableTheNewsAPI:         cfg.EnableTheNewsAPI,
		TheNewsAPIAPIKey:         cfg.TheNewsAPIAPIKey,
		EnableNewsData:           cfg.EnableNewsData,
		NewsDataAPIKey:           cfg.NewsDataAPIKey,
		EnableGNews:              cfg.EnableGNews,
		GNewsAPIKey:              cfg.GNewsAPIKey,
		EnableChroniclingAmerica: cfg.EnableChroniclingAmerica,
	}
}
