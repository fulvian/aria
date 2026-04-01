package startup

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/sony/gobreaker"
)

// CircuitBreakerConfig holds configuration for a circuit breaker.
type CircuitBreakerConfig struct {
	Name        string
	MaxRequests uint32        // Max requests in half-open state
	Interval    time.Duration // Cycle period for closed state
	Timeout     time.Duration // Period of open state
	ReadyToTrip func(gobreaker.Counts) bool
}

// DefaultCircuitBreakerConfig returns a default circuit breaker configuration.
func DefaultCircuitBreakerConfig(name string) CircuitBreakerConfig {
	return CircuitBreakerConfig{
		Name:        name,
		MaxRequests: 3,
		Interval:    30 * time.Second,
		Timeout:     30 * time.Second,
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			return counts.ConsecutiveFailures >= 5
		},
	}
}

// LLMProviderCircuitBreaker returns a pre-configured circuit breaker for LLM providers.
func LLMProviderCircuitBreaker(name string) CircuitBreakerConfig {
	return CircuitBreakerConfig{
		Name:        name,
		MaxRequests: 3,
		Interval:    30 * time.Second,
		Timeout:     30 * time.Second,
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			// Open circuit after 5 consecutive failures
			return counts.ConsecutiveFailures >= 5
		},
	}
}

// circuitBreaker wraps gobreaker.CircuitBreaker with additional context.
type circuitBreaker struct {
	cb   *gobreaker.CircuitBreaker
	name string
}

// CircuitBreaker is an interface for circuit breaker functionality.
type CircuitBreaker interface {
	// Execute runs the given function through the circuit breaker.
	Execute(ctx context.Context, fn func() error) error
	// Name returns the circuit breaker name.
	Name() string
	// State returns the current state of the circuit breaker.
	State() gobreaker.State
	// Counts returns the current counts of the circuit breaker.
	Counts() gobreaker.Counts
}

// NewCircuitBreaker creates a new CircuitBreaker instance.
func NewCircuitBreaker(config CircuitBreakerConfig) (CircuitBreaker, error) {
	if config.Name == "" {
		return nil, errors.New("circuit breaker name is required")
	}

	cb := gobreaker.NewCircuitBreaker(gobreaker.Settings{
		Name:        config.Name,
		MaxRequests: config.MaxRequests,
		Interval:    config.Interval,
		Timeout:     config.Timeout,
		ReadyToTrip: config.ReadyToTrip,
	})

	return &circuitBreaker{
		cb:   cb,
		name: config.Name,
	}, nil
}

// Execute runs the given function through the circuit breaker.
func (c *circuitBreaker) Execute(ctx context.Context, fn func() error) error {
	// Create a channel to signal completion
	done := make(chan struct{})
	defer close(done)

	// Wrap the function to handle context cancellation
	wrappedFn := func() (interface{}, error) {
		// Check if context is already cancelled before execution
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		default:
		}

		// Run the actual function
		err := fn()

		return nil, err
	}

	// Execute through circuit breaker
	_, err := c.cb.Execute(wrappedFn)

	// Check if context was cancelled during execution
	if err != nil && ctx.Err() != nil {
		// Prefer context cancellation error
		if errors.Is(ctx.Err(), context.Canceled) || errors.Is(ctx.Err(), context.DeadlineExceeded) {
			return ctx.Err()
		}
	}

	if err != nil {
		return fmt.Errorf("circuit breaker %s: %w", c.name, err)
	}

	return nil
}

// Name returns the circuit breaker name.
func (c *circuitBreaker) Name() string {
	return c.name
}

// State returns the current state of the circuit breaker.
func (c *circuitBreaker) State() gobreaker.State {
	return c.cb.State()
}

// Counts returns the current counts of the circuit breaker.
func (c *circuitBreaker) Counts() gobreaker.Counts {
	return c.cb.Counts()
}

// CircuitBreakerManager manages multiple circuit breakers.
type CircuitBreakerManager struct {
	breakers map[string]CircuitBreaker
	mu       errgroupMutex
}

type errgroupMutex struct {
	mu sync.RWMutex
}

// NewCircuitBreakerManager creates a new CircuitBreakerManager.
func NewCircuitBreakerManager() *CircuitBreakerManager {
	return &CircuitBreakerManager{
		breakers: make(map[string]CircuitBreaker),
	}
}

// Register adds a circuit breaker to the manager.
func (m *CircuitBreakerManager) Register(cb CircuitBreaker) {
	m.mu.mu.Lock()
	defer m.mu.mu.Unlock()

	m.breakers[cb.Name()] = cb
}

// Get retrieves a circuit breaker by name.
func (m *CircuitBreakerManager) Get(name string) (CircuitBreaker, bool) {
	m.mu.mu.RLock()
	defer m.mu.mu.RUnlock()

	cb, ok := m.breakers[name]
	return cb, ok
}

// MustGet retrieves a circuit breaker by name, panics if not found.
func (m *CircuitBreakerManager) MustGet(name string) CircuitBreaker {
	cb, ok := m.Get(name)
	if !ok {
		panic(fmt.Sprintf("circuit breaker %s not found", name))
	}
	return cb
}

// Unwrap returns the underlying gobreaker.CircuitBreaker.
func (c *circuitBreaker) Unwrap() *gobreaker.CircuitBreaker {
	return c.cb
}
