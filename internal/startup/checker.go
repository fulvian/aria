package startup

import (
	"context"
	"time"
)

// Checker is the base interface for all health checks.
// Implement this interface to add a service to the startup sequence.
type Checker interface {
	// Name returns the unique service name for logging and identification.
	Name() string

	// Priority returns the initialization priority (0=first).
	// Lower numbers run first. Services within the same priority
	// are executed in parallel using errgroup.
	Priority() int

	// Check verifies the service is healthy and ready.
	// Return nil if healthy, error otherwise.
	// This method should be idempotent and thread-safe.
	Check(ctx context.Context) error
}

// RetryableChecker extends Checker with retry capability.
// Use this for services that may need multiple attempts to become healthy.
type RetryableChecker interface {
	Checker

	// MaxRetries returns the maximum number of retry attempts.
	MaxRetries() int

	// RetryDelay returns the delay between retry attempts.
	// Supports exponential backoff via backoff.ExponentialBackOff.
	RetryDelay() time.Duration
}

// AutoRecoverer is for services that can automatically recover from failure.
// Implement this interface to enable automatic restart capabilities.
type AutoRecoverer interface {
	// Recover attempts to restart or restore the service.
	Recover(ctx context.Context) error

	// IsRecoverable returns true if the service can recover from failure.
	IsRecoverable() bool
}

// Phase represents a startup phase with its priority range and timeout.
type Phase struct {
	Name     string
	MinPrio  int
	MaxPrio  int
	Timeout  time.Duration
	Optional bool
}

// Predefined phases
var (
	// PhasePreFlight covers critical infrastructure (priority 0-99).
	// Timeout: 30 seconds.
	PhasePreFlight = Phase{
		Name:     "PRE-FLIGHT",
		MinPrio:  0,
		MaxPrio:  99,
		Timeout:  30 * time.Second,
		Optional: false,
	}

	// PhaseCoreServices covers core business services (priority 100-199).
	// Timeout: 60 seconds.
	PhaseCoreServices = Phase{
		Name:     "CORE SERVICES",
		MinPrio:  100,
		MaxPrio:  199,
		Timeout:  60 * time.Second,
		Optional: false,
	}

	// PhaseAriaComponents covers ARIA-specific components (priority 200-299).
	// Timeout: 90 seconds.
	PhaseAriaComponents = Phase{
		Name:     "ARIA COMPONENTS",
		MinPrio:  200,
		MaxPrio:  299,
		Timeout:  90 * time.Second,
		Optional: false,
	}

	// PhaseOptionalServices covers optional/degradable services (priority 300-399).
	// These run in background and do not block startup.
	PhaseOptionalServices = Phase{
		Name:     "OPTIONAL SERVICES",
		MinPrio:  300,
		MaxPrio:  399,
		Timeout:  0, // No timeout, runs in background
		Optional: true,
	}
)

// GetPhaseForPriority returns the phase that contains the given priority.
func GetPhaseForPriority(priority int) Phase {
	switch {
	case priority >= PhasePreFlight.MinPrio && priority <= PhasePreFlight.MaxPrio:
		return PhasePreFlight
	case priority >= PhaseCoreServices.MinPrio && priority <= PhaseCoreServices.MaxPrio:
		return PhaseCoreServices
	case priority >= PhaseAriaComponents.MinPrio && priority <= PhaseAriaComponents.MaxPrio:
		return PhaseAriaComponents
	case priority >= PhaseOptionalServices.MinPrio && priority <= PhaseOptionalServices.MaxPrio:
		return PhaseOptionalServices
	default:
		return PhasePreFlight
	}
}
