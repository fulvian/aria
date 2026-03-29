package app

import (
	"context"
	"time"

	"github.com/fulvian/aria/internal/aria/agency"
	"github.com/fulvian/aria/internal/aria/analysis"
	ariaConfig "github.com/fulvian/aria/internal/aria/config"
	"github.com/fulvian/aria/internal/aria/core"
	"github.com/fulvian/aria/internal/aria/guardrail"
	"github.com/fulvian/aria/internal/aria/memory"
	"github.com/fulvian/aria/internal/aria/permission"
	"github.com/fulvian/aria/internal/aria/scheduler"
	"github.com/fulvian/aria/internal/aria/skill"
	"github.com/fulvian/aria/internal/logging"
)

// ARIAComponents holds ARIA-specific components when enabled.
type ARIAComponents struct {
	Orchestrator      *core.BasicOrchestrator
	SkillRegistry     *skill.DefaultSkillRegistry
	DevelopmentAgency *agency.DevelopmentAgency
	WeatherAgency     *agency.WeatherAgency
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
	registry := skill.NewDefaultSkillRegistry()
	if err := skill.SetupDefaultSkills(registry); err != nil {
		logging.Error("Failed to setup default skills", err)
		return err
	}
	logging.Info("Registered default skills", "count", len(registry.List()))

	// Initialize development agency with coder agent bridge
	devAgency := agency.NewDevelopmentAgency(app.CoderAgent, app.Sessions, app.Messages)
	logging.Info("Initialized development agency", "name", devAgency.Name())

	// Initialize weather agency if enabled
	weatherCfg := ariaConfig.DefaultWeatherConfig()
	var weatherAgency *agency.WeatherAgency
	if ariaCfg.Agencies.Weather.Enabled && weatherCfg.IsConfigured() {
		weatherAgency = agency.NewWeatherAgency(weatherCfg)
		logging.Info("Initialized weather agency", "name", weatherAgency.Name(), "provider", weatherCfg.Provider)
	} else {
		logging.Info("Weather agency disabled or not configured")
	}

	// Initialize memory service (FASE 2: Memory & Learning)
	// 30 minute TTL for working memory context persistence
	memorySvc := memory.NewService(app.DB, 30*time.Minute)
	logging.Info("Initialized memory service")

	// Initialize analysis service (FASE 2: Memory & Learning)
	analysisSvc := analysis.NewService(app.DB)
	logging.Info("Initialized analysis service")

	// Initialize orchestrator with memory and analysis services
	orchestrator := core.NewBasicOrchestrator(core.OrchestratorConfig{
		EnableFallback:      ariaCfg.Routing.EnableFallback,
		DefaultAgency:       agency.AgencyName(ariaCfg.Routing.DefaultAgency),
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

	// Start dispatcher
	dispatcher.Run(ctx)

	// Start worker
	worker.Run(ctx)

	// Start recurring planner
	recurringPlanner.Run(ctx)

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
