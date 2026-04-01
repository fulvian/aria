package startup

import (
	"context"
	"sync"
	"time"
)

// ServiceStatus represents the current state of a service.
type ServiceStatus int

const (
	StatusUnknown ServiceStatus = iota
	StatusPending
	StatusChecking
	StatusHealthy
	StatusDegraded
	StatusUnhealthy
	StatusRecovering
)

// String returns a human-readable string for the status.
func (s ServiceStatus) String() string {
	switch s {
	case StatusUnknown:
		return "Unknown"
	case StatusPending:
		return "Pending"
	case StatusChecking:
		return "Checking"
	case StatusHealthy:
		return "Healthy"
	case StatusDegraded:
		return "Degraded"
	case StatusUnhealthy:
		return "Unhealthy"
	case StatusRecovering:
		return "Recovering"
	default:
		return "Invalid"
	}
}

// ServiceState holds the current state of a single service.
type ServiceState struct {
	Name      string
	Status    ServiceStatus
	Error     string
	UpdatedAt time.Time
}

// StatusChangeHandler is called when a service status changes.
type StatusChangeHandler func(serviceName string, oldStatus, newStatus ServiceStatus)

// StatusTracker provides atomic service status tracking with subscription support.
type StatusTracker struct {
	mu       sync.RWMutex
	statuses map[string]ServiceState
	subs     map[chan<- ServiceState]struct{}
	subMu    sync.RWMutex
}

// NewStatusTracker creates a new StatusTracker instance.
func NewStatusTracker() *StatusTracker {
	return &StatusTracker{
		statuses: make(map[string]ServiceState),
		subs:     make(map[chan<- ServiceState]struct{}),
	}
}

// SetStatus updates the status of a service and notifies subscribers.
func (t *StatusTracker) SetStatus(name string, status ServiceStatus, err error) {
	t.mu.Lock()
	defer t.mu.Unlock()

	oldState, exists := t.statuses[name]
	newState := ServiceState{
		Name:      name,
		Status:    status,
		UpdatedAt: time.Now(),
	}

	if err != nil {
		newState.Error = err.Error()
	}

	t.statuses[name] = newState

	// Notify subscribers if status changed
	if !exists || oldState.Status != status {
		t.notifySubscribers(name, oldState.Status, status)
	}
}

// GetStatus returns the current status of a service.
func (t *StatusTracker) GetStatus(name string) (ServiceState, bool) {
	t.mu.RLock()
	defer t.mu.RUnlock()

	state, ok := t.statuses[name]
	return state, ok
}

// GetAllStatuses returns a copy of all service statuses.
func (t *StatusTracker) GetAllStatuses() map[string]ServiceState {
	t.mu.RLock()
	defer t.mu.RUnlock()

	result := make(map[string]ServiceState, len(t.statuses))
	for k, v := range t.statuses {
		result[k] = v
	}

	return result
}

// Subscribe registers a channel to receive status change notifications.
// The channel should have adequate buffer space to avoid blocking.
func (t *StatusTracker) Subscribe(ch chan<- ServiceState) {
	t.subMu.Lock()
	defer t.subMu.Unlock()

	t.subs[ch] = struct{}{}
}

// Unsubscribe removes a subscription channel.
func (t *StatusTracker) Unsubscribe(ch chan<- ServiceState) {
	t.subMu.Lock()
	defer t.subMu.Unlock()

	delete(t.subs, ch)
}

// notifySubscribers sends status change notifications to all subscribers.
func (t *StatusTracker) notifySubscribers(serviceName string, oldStatus, newStatus ServiceStatus) {
	t.subMu.RLock()
	defer t.subMu.RUnlock()

	// Make a copy of subscribers to avoid holding lock during notification
	subs := make([]chan<- ServiceState, 0, len(t.subs))
	for ch := range t.subs {
		subs = append(subs, ch)
	}

	// Create the state to send
	state := t.statuses[serviceName]

	// Notify all subscribers (non-blocking send)
	for _, ch := range subs {
		select {
		case ch <- state:
		default:
			// Channel full, skip notification
		}
	}
}

// StatusEvent represents a status change event for pubsub integration.
type StatusEvent struct {
	ServiceName string
	OldStatus   ServiceStatus
	NewStatus   ServiceStatus
	State       ServiceState
}

// SubscribeWithContext returns a channel that receives status updates
// until the context is cancelled.
func (t *StatusTracker) SubscribeWithContext(ctx context.Context) <-chan ServiceState {
	ch := make(chan ServiceState, 64)

	t.subMu.Lock()
	t.subs[ch] = struct{}{}
	t.subMu.Unlock()

	go func() {
		<-ctx.Done()

		t.subMu.Lock()
		delete(t.subs, ch)
		t.subMu.Unlock()

		close(ch)
	}()

	return ch
}
