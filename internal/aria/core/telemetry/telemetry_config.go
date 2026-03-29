// Package telemetry provides telemetry, metrics, and feedback loop capabilities
// for the orchestrator enhancement (O5).
package telemetry

import (
	"fmt"
	"time"
)

// TelemetryConfig configurazione per la telemetria.
type TelemetryConfig struct {
	Enabled         bool
	FlushIntervalMs int
	MaxEvents       int // max eventi in buffer prima di flush
}

// DefaultTelemetryConfig returns a TelemetryConfig with sensible defaults.
func DefaultTelemetryConfig() TelemetryConfig {
	return TelemetryConfig{
		Enabled:         true,
		FlushIntervalMs: 5000,
		MaxEvents:       1000,
	}
}

// FlushInterval returns the flush interval as a time.Duration.
func (c TelemetryConfig) FlushInterval() time.Duration {
	return time.Duration(c.FlushIntervalMs) * time.Millisecond
}

// Validate validates the telemetry configuration.
func (c TelemetryConfig) Validate() error {
	if c.FlushIntervalMs < 0 {
		return fmt.Errorf("FlushIntervalMs must be non-negative, got %d", c.FlushIntervalMs)
	}
	if c.MaxEvents < 0 {
		return fmt.Errorf("MaxEvents must be non-negative, got %d", c.MaxEvents)
	}
	return nil
}

// NewTelemetryServiceWithConfig creates a new TelemetryService with configuration.
func NewTelemetryServiceWithConfig(cfg TelemetryConfig) (TelemetryService, error) {
	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("invalid telemetry config: %w", err)
	}

	// For now, the basic telemetry service is used
	// In the future, this could return a buffered/writing service
	return NewTelemetryService(), nil
}
