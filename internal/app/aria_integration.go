package app

import (
	"context"

	"github.com/fulvian/aria/internal/aria/agency"
	"github.com/fulvian/aria/internal/aria/core"
	"github.com/fulvian/aria/internal/aria/skill"
	"github.com/fulvian/aria/internal/config"
	"github.com/fulvian/aria/internal/logging"
)

// ARIAComponents holds ARIA-specific components when enabled.
type ARIAComponents struct {
	Orchestrator      *core.BasicOrchestrator
	SkillRegistry     *skill.DefaultSkillRegistry
	DevelopmentAgency *agency.DevelopmentAgency
}

// initARIA initializes ARIA components if enabled.
func (app *App) initARIA(ctx context.Context) error {
	cfg := config.Get()
	if cfg == nil || !cfg.ARIA.Enabled {
		logging.Info("ARIA mode is disabled, using legacy mode")
		return nil
	}

	logging.Info("Initializing ARIA mode", "config", cfg.ARIA)

	// Initialize skill registry with default skills
	registry := skill.NewDefaultSkillRegistry()
	if err := skill.SetupDefaultSkills(registry); err != nil {
		logging.Error("Failed to setup default skills", err)
		return err
	}
	logging.Info("Registered default skills", "count", len(registry.List()))

	// Initialize development agency
	devAgency := agency.NewDevelopmentAgency()
	logging.Info("Initialized development agency", "name", devAgency.Name())

	// Initialize orchestrator
	orchestrator := core.NewBasicOrchestrator(core.OrchestratorConfig{
		EnableFallback:      cfg.ARIA.Routing.EnableFallback,
		DefaultAgency:       agency.AgencyName(cfg.ARIA.Routing.DefaultAgency),
		ConfidenceThreshold: cfg.ARIA.Routing.ConfidenceThreshold,
	})

	// Register development agency with orchestrator
	orchestrator.RegisterAgency(devAgency)
	logging.Info("Registered development agency with orchestrator")

	// Store ARIA components
	app.ARIA = &ARIAComponents{
		Orchestrator:      orchestrator,
		SkillRegistry:     registry,
		DevelopmentAgency: devAgency,
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
	cfg := config.Get()
	return cfg != nil && cfg.ARIA.Enabled
}
