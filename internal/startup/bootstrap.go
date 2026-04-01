package startup

import (
	"context"
	"fmt"
	"sort"
	"time"

	"github.com/fulvian/aria/internal/logging"
	"golang.org/x/sync/errgroup"
)

// BootstrapManager coordinates startup phases and executes health checks.
type BootstrapManager struct {
	checkers       []Checker
	status         *StatusTracker
	cbManager      *CircuitBreakerManager
	onStatusChange []StatusChangeHandler
}

// NewBootstrapManager creates a new BootstrapManager with the given checkers.
func NewBootstrapManager(checkers []Checker) *BootstrapManager {
	// Sort checkers by priority
	sorted := make([]Checker, len(checkers))
	copy(sorted, checkers)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Priority() < sorted[j].Priority()
	})

	return &BootstrapManager{
		checkers:       sorted,
		status:         NewStatusTracker(),
		cbManager:      NewCircuitBreakerManager(),
		onStatusChange: nil,
	}
}

// WithStatusChangeHandler adds a handler for status changes.
func (m *BootstrapManager) WithStatusChangeHandler(handler StatusChangeHandler) *BootstrapManager {
	m.onStatusChange = append(m.onStatusChange, handler)
	return m
}

// StatusTracker returns the status tracker for this manager.
func (m *BootstrapManager) StatusTracker() *StatusTracker {
	return m.status
}

// CircuitBreakerManager returns the circuit breaker manager.
func (m *BootstrapManager) CircuitBreakerManager() *CircuitBreakerManager {
	return m.cbManager
}

// Bootstrap executes all startup phases in order.
// It runs checkers by phase, with parallel execution within each phase.
func (m *BootstrapManager) Bootstrap(ctx context.Context) error {
	// Group checkers by phase
	phases := m.groupCheckersByPhase()

	for phase, phaseCheckers := range phases {
		phaseCtx, cancel := context.WithTimeout(ctx, phase.Timeout)
		defer cancel()

		logging.Info("Starting bootstrap phase", "phase", phase.Name, "checkers", len(phaseCheckers))

		if err := m.runPhase(phaseCtx, phase, phaseCheckers); err != nil {
			if !phase.Optional {
				logging.Error("Bootstrap phase failed", "phase", phase.Name, "error", err)
				return fmt.Errorf("bootstrap phase %s: %w", phase.Name, err)
			}
			logging.Warn("Optional bootstrap phase failed, continuing", "phase", phase.Name, "error", err)
		}

		logging.Info("Bootstrap phase completed", "phase", phase.Name)
	}

	return nil
}

// groupCheckersByPhase organizes checkers into their respective phases.
func (m *BootstrapManager) groupCheckersByPhase() map[Phase][]Checker {
	phases := make(map[Phase][]Checker)

	for _, checker := range m.checkers {
		phase := GetPhaseForPriority(checker.Priority())
		phases[phase] = append(phases[phase], checker)
	}

	return phases
}

// runPhase executes all checkers in a phase with parallel execution.
func (m *BootstrapManager) runPhase(ctx context.Context, phase Phase, checkers []Checker) error {
	// Further group by exact priority for parallel execution within priority level
	priorityGroups := m.groupByPriority(checkers)

	// Process each priority group sequentially, but checkers within same priority run parallel
	for _, group := range priorityGroups {
		groupCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
		defer cancel()

		g, groupCtx := errgroup.WithContext(groupCtx)

		for _, checker := range group {
			checker := checker // capture range variable
			g.Go(func() error {
				return m.runCheckerWithRetry(groupCtx, checker)
			})
		}

		if err := g.Wait(); err != nil {
			// If any required service fails, return error
			return err
		}
	}

	return nil
}

// groupByPriority groups checkers by their exact priority.
func (m *BootstrapManager) groupByPriority(checkers []Checker) [][]Checker {
	// Sort by priority first
	sorted := make([]Checker, len(checkers))
	copy(sorted, checkers)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Priority() < sorted[j].Priority()
	})

	// Group by exact priority
	var groups [][]Checker
	var currentPrio int = -1
	var currentGroup []Checker

	for _, checker := range sorted {
		if checker.Priority() != currentPrio {
			if len(currentGroup) > 0 {
				groups = append(groups, currentGroup)
			}
			currentPrio = checker.Priority()
			currentGroup = []Checker{checker}
		} else {
			currentGroup = append(currentGroup, checker)
		}
	}

	if len(currentGroup) > 0 {
		groups = append(groups, currentGroup)
	}

	return groups
}

// runCheckerWithRetry executes a checker with retry support if applicable.
func (m *BootstrapManager) runCheckerWithRetry(ctx context.Context, checker Checker) error {
	name := checker.Name()

	// Update status to Checking
	m.status.SetStatus(name, StatusChecking, nil)

	// Check if checker supports retries
	retryable, isRetryable := checker.(RetryableChecker)

	if !isRetryable {
		return m.executeChecker(ctx, checker)
	}

	// Execute with retry
	maxRetries := retryable.MaxRetries()
	retryDelay := retryable.RetryDelay()

	attempt := 0
	for {
		err := m.executeChecker(ctx, checker)
		if err == nil {
			return nil
		}

		attempt++
		if attempt > maxRetries {
			return fmt.Errorf("service %s: %w", name, err)
		}

		// Check if context is still valid
		select {
		case <-ctx.Done():
			return fmt.Errorf("service %s: context cancelled during retry", name)
		default:
		}

		logging.Warn("Service check failed, retrying",
			"service", name,
			"attempt", attempt,
			"maxRetries", maxRetries,
			"error", err)

		// Wait before retry with exponential backoff
		backoffDuration := time.Duration(attempt) * retryDelay
		if backoffDuration > 30*time.Second {
			backoffDuration = 30 * time.Second
		}
		backoffTimer := time.NewTimer(backoffDuration)
		defer backoffTimer.Stop()

		select {
		case <-ctx.Done():
			return fmt.Errorf("service %s: context cancelled during backoff", name)
		case <-backoffTimer.C:
			// Continue to next attempt
		}
	}
}

// executeChecker runs a single checker and updates status.
func (m *BootstrapManager) executeChecker(ctx context.Context, checker Checker) error {
	name := checker.Name()

	done := make(chan error, 1)
	go func() {
		done <- checker.Check(ctx)
	}()

	select {
	case <-ctx.Done():
		m.status.SetStatus(name, StatusUnhealthy, ctx.Err())
		return fmt.Errorf("service %s: context cancelled", name)
	case err := <-done:
		if err != nil {
			m.status.SetStatus(name, StatusUnhealthy, err)
			return err
		}
		m.status.SetStatus(name, StatusHealthy, nil)
		return nil
	}
}

// BootstrapResult contains the results of a bootstrap operation.
type BootstrapResult struct {
	PhaseResults map[string]PhaseResult
	TotalTime    time.Duration
	Success      bool
}

// PhaseResult contains the results of a single phase.
type PhaseResult struct {
	Phase         Phase
	Checkers      []string
	SuccessCount  int
	FailureCount  int
	DegradedCount int
	Errors        []error
	Duration      time.Duration
}
