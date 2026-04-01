package app

import (
	"context"
	"time"

	"github.com/fulvian/aria/internal/aria/agency"
	"github.com/fulvian/aria/internal/aria/analysis"
	ariaConfig "github.com/fulvian/aria/internal/aria/config"
	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/aria/core"
	"github.com/fulvian/aria/internal/aria/guardrail"
	"github.com/fulvian/aria/internal/aria/memory"
	"github.com/fulvian/aria/internal/aria/permission"
	"github.com/fulvian/aria/internal/aria/scheduler"
	"github.com/fulvian/aria/internal/aria/skill"
	"github.com/fulvian/aria/internal/config"
	"github.com/fulvian/aria/internal/llm/models"
	"github.com/fulvian/aria/internal/llm/provider"
	"github.com/fulvian/aria/internal/logging"
)

// ARIAComponents holds ARIA-specific components when enabled.
type ARIAComponents struct {
	Orchestrator      *core.BasicOrchestrator
	SkillRegistry     *skill.DefaultSkillRegistry
	DevelopmentAgency *agency.DevelopmentAgency
	WeatherAgency     *agency.WeatherAgency
	NutritionAgency   *agency.NutritionAgency
	KnowledgeAgency   *agency.KnowledgeAgency
	AgencyService     *agency.AgencyService

	// Scheduler components
	SchedulerService *scheduler.SchedulerService
	Dispatcher       *scheduler.Dispatcher
	Worker           *scheduler.Worker
	RecurringPlanner *scheduler.RecurringPlanner

	// Guardrail and permission services
	GuardrailService  guardrail.GuardrailService           // Implements GuardrailService interface
	PermissionService permission.ExtendedPermissionService // Implements ExtendedPermissionService interface

	// Memory and analysis services (FASE 2: Memory & Learning)
	MemoryService   memory.MemoryService         // Memory service for working context, episodic/semantic/procedural memory
	AnalysisService analysis.SelfAnalysisService // Self-analysis service for performance and pattern analysis
}

// initARIA initializes ARIA components if enabled.
func (app *App) initARIA(ctx context.Context) error {
	ariaCfg := ariaConfig.Load()
	if ariaCfg == nil || !ariaCfg.Enabled {
		logging.Info("ARIA mode is disabled, using legacy mode")
		return nil
	}

	logging.Info("Initializing ARIA mode", "config", ariaCfg)

	// Initialize skill registry with default skills
	logging.Info("DEBUG aria_integration: about to create skill registry")
	registry := skill.NewDefaultSkillRegistry()
	if err := skill.SetupDefaultSkills(registry); err != nil {
		logging.Error("Failed to setup default skills", err)
		return err
	}
	logging.Info("DEBUG aria_integration: skill registry created", "count", len(registry.List()))

	// Initialize development agency with coder agent bridge
	logging.Info("DEBUG aria_integration: about to create development agency")
	devAgency := agency.NewDevelopmentAgency(app.CoderAgent, app.Sessions, app.Messages)
	logging.Info("DEBUG aria_integration: development agency created", "name", devAgency.Name())

	// Initialize weather agency if enabled
	weatherCfg := ariaConfig.DefaultWeatherConfig()
	var weatherAgency *agency.WeatherAgency
	if ariaCfg.Agencies.Weather.Enabled && weatherCfg.IsConfigured() {
		weatherAgency = agency.NewWeatherAgency(weatherCfg)
		logging.Info("Initialized weather agency", "name", weatherAgency.Name(), "provider", weatherCfg.Provider)
	} else {
		logging.Info("Weather agency disabled or not configured")
	}

	// Initialize nutrition agency if enabled
	nutritionCfg := ariaConfig.DefaultNutritionConfig()
	var nutritionAgency *agency.NutritionAgency
	if ariaCfg.Agencies.Nutrition.Enabled && nutritionCfg.IsConfigured() {
		nutritionAgency = agency.NewNutritionAgency(nutritionCfg)
		logging.Info("Initialized nutrition agency", "name", nutritionAgency.Name())
	} else {
		logging.Info("Nutrition agency disabled or not configured")
	}

	// Initialize knowledge agency if enabled
	knowledgeCfg := ariaConfig.DefaultKnowledgeConfig()
	var knowledgeAgency *agency.KnowledgeAgency
	if ariaCfg.Agencies.Knowledge.Enabled {
		knowledgeAgency = agency.NewKnowledgeAgency(knowledgeCfg)
		logging.Info("Initialized knowledge agency", "name", knowledgeAgency.Name())
	} else {
		logging.Info("Knowledge agency disabled")
	}

	// Initialize memory service (FASE 2: Memory & Learning)
	// 30 minute TTL for working memory context persistence
	var memorySvc memory.MemoryService
	var embedFunc memory.EmbeddingFunc
	var embedConfig memory.EmbeddingConfig

	// Check main config for memory embedding settings
	cfg := config.Get()
	logging.Info("DEBUG aria_integration: checking memory config", "enabled", cfg.Memory.Enabled, "provider", cfg.Memory.Provider)
	if cfg.Memory.Enabled {
		// Cast provider string to ModelProvider type
		memProvider := models.ModelProvider(cfg.Memory.Provider)
		// Get the provider config for embeddings
		providerCfg, ok := cfg.Providers[memProvider]
		if !ok || providerCfg.Disabled {
			logging.Warn("Embedding provider not found or disabled, embeddings disabled",
				"provider", cfg.Memory.Provider)
		} else {
			// Create the provider instance
			// We need to create a model with the embedding model name
			embedModel := models.Model{
				Provider: memProvider,
				Name:     cfg.Memory.Model,
				APIModel: cfg.Memory.Model,
			}
			providerInstance, err := provider.NewProvider(
				memProvider,
				provider.WithAPIKey(providerCfg.APIKey),
				provider.WithModel(embedModel),
			)
			if err != nil {
				logging.Warn("Failed to create embedding provider, embeddings disabled",
					"provider", cfg.Memory.Provider,
					"error", err)
			} else {
				// Create embedding function wrapper
				embedFunc = func(ctx context.Context, text string) ([]float32, error) {
					return providerInstance.CreateEmbedding(ctx, text)
				}
				embedConfig = memory.EmbeddingConfig{
					Enabled:            true,
					Provider:           cfg.Memory.Provider,
					Model:              cfg.Memory.Model,
					Mode:               cfg.Memory.Mode,
					BatchSize:          cfg.Memory.BatchSize,
					Timeout:            time.Duration(cfg.Memory.TimeoutMs) * time.Millisecond,
					VectorCacheEnabled: cfg.Memory.VectorCacheEnabled,
				}
				logging.Info("Embedding enabled",
					"provider", embedConfig.Provider,
					"model", embedConfig.Model,
					"mode", embedConfig.Mode)
			}
		}
	}

	memorySvc = memory.NewService(app.DB, 30*time.Minute, embedFunc, embedConfig)
	logging.Info("Initialized memory service")

	// Initialize analysis service (FASE 2: Memory & Learning)
	analysisSvc := analysis.NewService(app.DB)
	logging.Info("Initialized analysis service")

	// Initialize orchestrator with memory and analysis services
	orchestrator := core.NewBasicOrchestrator(core.OrchestratorConfig{
		EnableFallback:      ariaCfg.Routing.EnableFallback,
		DefaultAgency:       contracts.AgencyName(ariaCfg.Routing.DefaultAgency),
		ConfidenceThreshold: ariaCfg.Routing.ConfidenceThreshold,
	}, memorySvc, analysisSvc)

	// Initialize agency service for persistence
	agencyService := agency.NewAgencyService(app.DB)
	logging.Info("Initialized agency service")

	// Register development agency with orchestrator and persist
	orchestrator.RegisterAgency(devAgency)
	if err := agencyService.RegisterAgency(ctx, devAgency); err != nil {
		logging.Warn("Failed to persist development agency", "error", err)
	}
	logging.Info("Registered development agency with orchestrator")

	// Register weather agency with orchestrator and persist if available
	if weatherAgency != nil {
		orchestrator.RegisterAgency(weatherAgency)
		if err := agencyService.RegisterAgency(ctx, weatherAgency); err != nil {
			logging.Warn("Failed to persist weather agency", "error", err)
		}
		logging.Info("Registered weather agency with orchestrator")
	}

	// Register nutrition agency with orchestrator and persist if available
	if nutritionAgency != nil {
		orchestrator.RegisterAgency(nutritionAgency)
		if err := agencyService.RegisterAgency(ctx, nutritionAgency); err != nil {
			logging.Warn("Failed to persist nutrition agency", "error", err)
		}
		logging.Info("Registered nutrition agency with orchestrator")
	}

	// Register knowledge agency with orchestrator and persist if available
	if knowledgeAgency != nil {
		orchestrator.RegisterAgency(knowledgeAgency)
		if err := agencyService.RegisterAgency(ctx, knowledgeAgency); err != nil {
			logging.Warn("Failed to persist knowledge agency", "error", err)
		}
		logging.Info("Registered knowledge agency with orchestrator")
	}

	// Initialize scheduler components
	maxConcurrent := ariaCfg.Scheduler.MaxConcurrentTasks
	if maxConcurrent <= 0 {
		maxConcurrent = 3
	}

	// Create scheduler service
	schedulerSvc := scheduler.NewSchedulerService(app.DB, maxConcurrent)

	// Create dispatcher
	dispatchInterval := time.Duration(ariaCfg.Scheduler.DispatchIntervalMs) * time.Millisecond
	if dispatchInterval <= 0 {
		dispatchInterval = 1 * time.Second
	}
	dispatcher := scheduler.NewDispatcher(schedulerSvc, dispatchInterval, true)

	// Create worker with task executor
	pollInterval := time.Duration(500) * time.Millisecond
	if dispatchInterval < pollInterval {
		pollInterval = dispatchInterval
	}
	executor := scheduler.NewDefaultTaskExecutor()
	worker := scheduler.NewWorker(schedulerSvc, maxConcurrent, pollInterval, executor)

	// Create recurring planner
	lookAhead := time.Duration(ariaCfg.Scheduler.RecurringLookaheadMinutes) * time.Minute
	if lookAhead <= 0 {
		lookAhead = 60 * time.Minute
	}
	recurringPlanner := scheduler.NewRecurringPlanner(schedulerSvc, lookAhead, 5*time.Minute)

	// Create recovery manager and run recovery on startup
	recoveryPolicy := scheduler.RecoveryPolicy(ariaCfg.Scheduler.RecoveryPolicy)
	if recoveryPolicy == "" {
		recoveryPolicy = scheduler.PolicyRequeue
	}
	recoveryManager := scheduler.NewRecoveryManager(app.DB, schedulerSvc.GetEventBroker(), recoveryPolicy)

	if err := recoveryManager.Recover(ctx); err != nil {
		logging.Error("scheduler recovery failed", err)
		// Continue anyway - don't block startup
	}

	// Start dispatcher in background
	go func() {
		defer logging.RecoverPanic("dispatcher", nil)
		dispatcher.Run(ctx)
	}()

	// Start worker in background
	go func() {
		defer logging.RecoverPanic("worker", nil)
		worker.Run(ctx)
	}()

	// Start recurring planner in background
	go func() {
		defer logging.RecoverPanic("recurring-planner", nil)
		recurringPlanner.Run(ctx)
	}()

	// Initialize guardrail service
	guardrailSvc := guardrail.NewService(ariaCfg.Guardrails)

	// Initialize permission service
	permissionSvc := permission.NewService()

	// Store ARIA components
	app.ARIA = &ARIAComponents{
		Orchestrator:      orchestrator,
		SkillRegistry:     registry,
		DevelopmentAgency: devAgency,
		WeatherAgency:     weatherAgency,
		NutritionAgency:   nutritionAgency,
		KnowledgeAgency:   knowledgeAgency,
		AgencyService:     agencyService,
		SchedulerService:  schedulerSvc,
		Dispatcher:        dispatcher,
		Worker:            worker,
		RecurringPlanner:  recurringPlanner,
		GuardrailService:  guardrailSvc,
		PermissionService: permissionSvc,
		MemoryService:     memorySvc,
		AnalysisService:   analysisSvc,
	}

	logging.Info("ARIA initialization complete")
	return nil
}

// GetARIA returns the ARIA components if available.
func (app *App) GetARIA() *ARIAComponents {
	return app.ARIA
}

// IsARIAMode returns true if ARIA mode is enabled.
func (app *App) IsARIAMode() bool {
	ariaCfg := ariaConfig.Load()
	return ariaCfg != nil && ariaCfg.Enabled
}
