package startup

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/sony/gobreaker"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockChecker implements Checker for testing.
type mockChecker struct {
	name       string
	priority   int
	checkFn    func(ctx context.Context) error
	maxRetries int
	retryDelay time.Duration
}

func (m *mockChecker) Name() string                    { return m.name }
func (m *mockChecker) Priority() int                   { return m.priority }
func (m *mockChecker) Check(ctx context.Context) error { return m.checkFn(ctx) }
func (m *mockChecker) MaxRetries() int                 { return m.maxRetries }
func (m *mockChecker) RetryDelay() time.Duration       { return m.retryDelay }

// mockRetryableChecker implements RetryableChecker for testing.
type mockRetryableChecker struct {
	name       string
	priority   int
	checkFn    func(ctx context.Context) error
	maxRetries int
	retryDelay time.Duration
	calls      int
	mu         sync.Mutex
}

func (m *mockRetryableChecker) Name() string              { return m.name }
func (m *mockRetryableChecker) Priority() int             { return m.priority }
func (m *mockRetryableChecker) MaxRetries() int           { return m.maxRetries }
func (m *mockRetryableChecker) RetryDelay() time.Duration { return m.retryDelay }
func (m *mockRetryableChecker) Check(ctx context.Context) error {
	m.mu.Lock()
	m.calls++
	m.mu.Unlock()
	return m.checkFn(ctx)
}
func (m *mockRetryableChecker) Calls() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.calls
}

func TestNewBootstrapManager(t *testing.T) {
	t.Run("sorts checkers by priority", func(t *testing.T) {
		checkers := []Checker{
			&mockChecker{name: "high", priority: 100},
			&mockChecker{name: "low", priority: 200},
			&mockChecker{name: "medium", priority: 150},
		}

		manager := NewBootstrapManager(checkers)

		// Access private field for verification
		assert.Equal(t, "high", manager.checkers[0].Name())
		assert.Equal(t, "medium", manager.checkers[1].Name())
		assert.Equal(t, "low", manager.checkers[2].Name())
	})
}

func TestBootstrapManager_Bootstrap(t *testing.T) {
	t.Run("successful bootstrap", func(t *testing.T) {
		checkers := []Checker{
			&mockChecker{name: "checker1", priority: 10, checkFn: func(ctx context.Context) error {
				return nil
			}},
			&mockChecker{name: "checker2", priority: 20, checkFn: func(ctx context.Context) error {
				return nil
			}},
		}

		manager := NewBootstrapManager(checkers)
		err := manager.Bootstrap(context.Background())

		require.NoError(t, err)

		// Verify all statuses are healthy
		statuses := manager.status.GetAllStatuses()
		assert.Equal(t, StatusHealthy, statuses["checker1"].Status)
		assert.Equal(t, StatusHealthy, statuses["checker2"].Status)
	})

	t.Run("fails on required service error", func(t *testing.T) {
		checkers := []Checker{
			&mockChecker{name: "failing", priority: 10, checkFn: func(ctx context.Context) error {
				return errors.New("service unavailable")
			}},
		}

		manager := NewBootstrapManager(checkers)
		err := manager.Bootstrap(context.Background())

		require.Error(t, err)
		assert.Contains(t, err.Error(), "failing")

		statuses := manager.status.GetAllStatuses()
		assert.Equal(t, StatusUnhealthy, statuses["failing"].Status)
	})

	t.Run("continues on optional service error", func(t *testing.T) {
		optionalChecker := &mockChecker{
			name:     "optional",
			priority: 310, // PhaseOptionalServices
			checkFn: func(ctx context.Context) error {
				return errors.New("optional service failed")
			},
		}

		requiredChecker := &mockChecker{
			name:     "required",
			priority: 10,
			checkFn: func(ctx context.Context) error {
				return nil
			},
		}

		manager := NewBootstrapManager([]Checker{optionalChecker, requiredChecker})
		err := manager.Bootstrap(context.Background())

		// Should not error because optional service failed but required passed
		require.NoError(t, err)

		statuses := manager.status.GetAllStatuses()
		assert.Equal(t, StatusHealthy, statuses["required"].Status)
		assert.Equal(t, StatusUnhealthy, statuses["optional"].Status)
	})

	t.Run("context cancellation stops bootstrap", func(t *testing.T) {
		checker := &mockChecker{
			name:     "slow",
			priority: 10,
			checkFn: func(ctx context.Context) error {
				<-ctx.Done()
				return ctx.Err()
			},
		}

		manager := NewBootstrapManager([]Checker{checker})

		ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
		defer cancel()

		err := manager.Bootstrap(ctx)
		require.Error(t, err)
		assert.Contains(t, err.Error(), "context cancelled")
	})

	t.Run("parallel execution within same priority", func(t *testing.T) {
		var wg sync.WaitGroup
		wg.Add(2)

		checker1 := &mockChecker{
			name:     "parallel1",
			priority: 10,
			checkFn: func(ctx context.Context) error {
				wg.Done()
				// Wait for the other checker to also start
				time.Sleep(10 * time.Millisecond)
				return nil
			},
		}

		checker2 := &mockChecker{
			name:     "parallel2",
			priority: 10,
			checkFn: func(ctx context.Context) error {
				wg.Done()
				time.Sleep(10 * time.Millisecond)
				return nil
			},
		}

		manager := NewBootstrapManager([]Checker{checker1, checker2})

		start := time.Now()
		err := manager.Bootstrap(context.Background())
		elapsed := time.Since(start)

		require.NoError(t, err)
		// Both should run in parallel, so total time should be ~10ms, not 20ms
		assert.Less(t, elapsed, 20*time.Millisecond, "checkers should run in parallel")
	})
}

func TestStatusTracker(t *testing.T) {
	t.Run("SetStatus and GetStatus", func(t *testing.T) {
		tracker := NewStatusTracker()

		err := errors.New("test error")
		tracker.SetStatus("service1", StatusUnhealthy, err)

		state, ok := tracker.GetStatus("service1")
		require.True(t, ok)
		assert.Equal(t, "service1", state.Name)
		assert.Equal(t, StatusUnhealthy, state.Status)
		assert.Equal(t, "test error", state.Error)
	})

	t.Run("GetAllStatuses", func(t *testing.T) {
		tracker := NewStatusTracker()

		tracker.SetStatus("s1", StatusHealthy, nil)
		tracker.SetStatus("s2", StatusUnhealthy, errors.New("error"))

		statuses := tracker.GetAllStatuses()
		assert.Len(t, statuses, 2)
		assert.Equal(t, StatusHealthy, statuses["s1"].Status)
		assert.Equal(t, StatusUnhealthy, statuses["s2"].Status)
	})

	t.Run("Subscribe receives updates", func(t *testing.T) {
		tracker := NewStatusTracker()
		ch := make(chan ServiceState, 10)
		tracker.Subscribe(ch)

		tracker.SetStatus("service", StatusChecking, nil)
		tracker.SetStatus("service", StatusHealthy, nil)

		// Should receive at least one update
		var lastState ServiceState
		timeout := time.After(100 * time.Millisecond)
		for {
			select {
			case state := <-ch:
				lastState = state
			case <-timeout:
				goto done
			}
		}
	done:
		assert.Equal(t, StatusHealthy, lastState.Status)
	})

	t.Run("Unsubscribe stops updates", func(t *testing.T) {
		tracker := NewStatusTracker()
		ch := make(chan ServiceState, 10)
		tracker.Subscribe(ch)
		tracker.Unsubscribe(ch)

		tracker.SetStatus("service", StatusChecking, nil)
		tracker.SetStatus("service", StatusHealthy, nil)

		// Give time for any potential update
		time.Sleep(50 * time.Millisecond)

		// Channel should be empty since unsubscribed
		select {
		case <-ch:
			t.Fatal("should not receive update after unsubscribe")
		default:
			// Expected - no update
		}
	})
}

func TestServiceStatus(t *testing.T) {
	tests := []struct {
		status   ServiceStatus
		expected string
	}{
		{StatusUnknown, "Unknown"},
		{StatusPending, "Pending"},
		{StatusChecking, "Checking"},
		{StatusHealthy, "Healthy"},
		{StatusDegraded, "Degraded"},
		{StatusUnhealthy, "Unhealthy"},
		{StatusRecovering, "Recovering"},
		{ServiceStatus(100), "Invalid"},
	}

	for _, tt := range tests {
		t.Run(tt.expected, func(t *testing.T) {
			assert.Equal(t, tt.expected, tt.status.String())
		})
	}
}

func TestGetPhaseForPriority(t *testing.T) {
	tests := []struct {
		priority int
		expected Phase
	}{
		{0, PhasePreFlight},
		{50, PhasePreFlight},
		{99, PhasePreFlight},
		{100, PhaseCoreServices},
		{150, PhaseCoreServices},
		{199, PhaseCoreServices},
		{200, PhaseAriaComponents},
		{250, PhaseAriaComponents},
		{299, PhaseAriaComponents},
		{300, PhaseOptionalServices},
		{350, PhaseOptionalServices},
		{399, PhaseOptionalServices},
		{400, PhasePreFlight}, // Unknown priority defaults to pre-flight
	}

	for _, tt := range tests {
		t.Run(tt.expected.Name, func(t *testing.T) {
			phase := GetPhaseForPriority(tt.priority)
			assert.Equal(t, tt.expected.Name, phase.Name)
			assert.Equal(t, tt.expected.Optional, phase.Optional)
		})
	}
}

func TestCircuitBreakerConfig(t *testing.T) {
	t.Run("DefaultCircuitBreakerConfig", func(t *testing.T) {
		config := DefaultCircuitBreakerConfig("test")

		assert.Equal(t, "test", config.Name)
		assert.Equal(t, uint32(3), config.MaxRequests)
		assert.Equal(t, 30*time.Second, config.Interval)
		assert.Equal(t, 30*time.Second, config.Timeout)
		assert.NotNil(t, config.ReadyToTrip)
	})

	t.Run("LLMProviderCircuitBreaker", func(t *testing.T) {
		config := LLMProviderCircuitBreaker("llm")

		assert.Equal(t, "llm", config.Name)
		assert.Equal(t, uint32(3), config.MaxRequests)

		// Test ReadyToTrip
		counts := gobreaker.Counts{ConsecutiveFailures: 4}
		assert.False(t, config.ReadyToTrip(counts)) // 4 < 5

		counts.ConsecutiveFailures = 5
		assert.True(t, config.ReadyToTrip(counts))
	})
}

func TestCircuitBreaker(t *testing.T) {
	t.Run("successful execution", func(t *testing.T) {
		config := DefaultCircuitBreakerConfig("test-cb")
		cb, err := NewCircuitBreaker(config)
		require.NoError(t, err)

		err = cb.Execute(context.Background(), func() error {
			return nil
		})

		require.NoError(t, err)
		assert.Equal(t, gobreaker.StateClosed, cb.State())
	})

	t.Run("failed execution records failure", func(t *testing.T) {
		config := DefaultCircuitBreakerConfig("test-cb-fail")
		cb, err := NewCircuitBreaker(config)
		require.NoError(t, err)

		testErr := errors.New("test error")
		err = cb.Execute(context.Background(), func() error {
			return testErr
		})

		require.Error(t, err)
		assert.Contains(t, err.Error(), "test error")
	})

	t.Run("context cancellation", func(t *testing.T) {
		config := DefaultCircuitBreakerConfig("test-cb-cancel")
		cb, err := NewCircuitBreaker(config)
		require.NoError(t, err)

		ctx, cancel := context.WithCancel(context.Background())
		cancel() // Cancel immediately

		err = cb.Execute(ctx, func() error {
			time.Sleep(100 * time.Millisecond)
			return nil
		})

		require.Error(t, err)
		assert.Contains(t, err.Error(), "context canceled")
	})
}

func TestCircuitBreakerManager(t *testing.T) {
	manager := NewCircuitBreakerManager()

	cb1, err := NewCircuitBreaker(DefaultCircuitBreakerConfig("cb1"))
	require.NoError(t, err)

	manager.Register(cb1)

	t.Run("Get existing breaker", func(t *testing.T) {
		cb, ok := manager.Get("cb1")
		require.True(t, ok)
		assert.Equal(t, "cb1", cb.Name())
	})

	t.Run("Get non-existing breaker", func(t *testing.T) {
		_, ok := manager.Get("nonexistent")
		assert.False(t, ok)
	})

	t.Run("MustGet panics for non-existing", func(t *testing.T) {
		assert.Panics(t, func() {
			manager.MustGet("nonexistent")
		})
	})
}
