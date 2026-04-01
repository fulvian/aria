package startup

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/fulvian/aria/internal/logging"
)

// RecoveryManager handles automatic recovery of failed services.
type RecoveryManager struct {
	tracker    *StatusTracker
	checkers   map[string]Checker
	recoveryFn map[string]func(context.Context) error
	interval   time.Duration
	stopCh     chan struct{}
	wg         sync.WaitGroup
	mu         sync.Mutex
}

// NewRecoveryManager creates a new RecoveryManager.
func NewRecoveryManager(tracker *StatusTracker, interval time.Duration) *RecoveryManager {
	return &RecoveryManager{
		tracker:    tracker,
		checkers:   make(map[string]Checker),
		recoveryFn: make(map[string]func(context.Context) error),
		interval:   interval,
		stopCh:     make(chan struct{}),
	}
}

// Register registers a service for automatic recovery.
func (m *RecoveryManager) Register(name string, checker Checker, recoveryFn func(context.Context) error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.checkers[name] = checker
	m.recoveryFn[name] = recoveryFn
}

// Start begins the recovery monitoring loop.
func (m *RecoveryManager) Start(ctx context.Context) {
	m.wg.Add(1)
	go m.runLoop(ctx)
}

// Stop stops the recovery monitoring loop.
func (m *RecoveryManager) Stop() {
	close(m.stopCh)
	m.wg.Wait()
}

// runLoop runs the recovery monitoring loop.
func (m *RecoveryManager) runLoop(ctx context.Context) {
	defer m.wg.Done()
	defer logging.RecoverPanic("RecoveryManager", nil)

	ticker := time.NewTicker(m.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-m.stopCh:
			return
		case <-ticker.C:
			m.checkAndRecover(ctx)
		}
	}
}

// checkAndRecover checks all registered services and attempts recovery if needed.
func (m *RecoveryManager) checkAndRecover(ctx context.Context) {
	m.mu.Lock()
	defer m.mu.Unlock()

	for name := range m.checkers {
		status, _ := m.tracker.GetStatus(name)

		if status.Status == StatusUnhealthy {
			// Try to recover
			recoveryFn, ok := m.recoveryFn[name]
			if !ok {
				continue
			}

			m.tracker.SetStatus(name, StatusRecovering, nil)

			recoveryCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
			err := recoveryFn(recoveryCtx)
			cancel()

			if err != nil {
				logging.Warn("Recovery failed for service",
					"service", name,
					"error", err)
				m.tracker.SetStatus(name, StatusUnhealthy, err)
			} else {
				logging.Info("Recovery succeeded for service",
					"service", name)
				m.tracker.SetStatus(name, StatusHealthy, nil)
			}
		}
	}
}

// RecoveryConfig holds configuration for the recovery manager.
type RecoveryConfig struct {
	// Enabled indicates whether automatic recovery is enabled.
	Enabled bool

	// Interval is the interval between recovery checks.
	Interval time.Duration

	// MaxAttempts is the maximum number of recovery attempts per service.
	MaxAttempts int

	// BackoffMultiplier multiplies the interval after each failed attempt.
	BackoffMultiplier float64
}

// DefaultRecoveryConfig returns the default recovery configuration.
func DefaultRecoveryConfig() *RecoveryConfig {
	return &RecoveryConfig{
		Enabled:           true,
		Interval:          30 * time.Second,
		MaxAttempts:       3,
		BackoffMultiplier: 2.0,
	}
}

// Validate validates the recovery configuration.
func (c *RecoveryConfig) Validate() error {
	if c.Interval < time.Second {
		return fmt.Errorf("recovery interval must be at least 1 second")
	}
	if c.MaxAttempts < 1 {
		return fmt.Errorf("max attempts must be at least 1")
	}
	if c.BackoffMultiplier < 1 {
		return fmt.Errorf("backoff multiplier must be at least 1")
	}
	return nil
}
