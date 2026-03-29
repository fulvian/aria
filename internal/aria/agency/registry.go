// Package agency provides the Agency system - specialized organizations
// of agents for specific domains (development, knowledge, creative, etc.).
package agency

import (
	"context"
	"fmt"
	"sync"
)

// AgencyRegistry manages multiple agencies.
type AgencyRegistry interface {
	// Register adds an agency to the registry.
	Register(agency Agency) error

	// Unregister removes an agency from the registry.
	Unregister(name AgencyName) error

	// Get returns an agency by name.
	Get(name AgencyName) (Agency, error)

	// List returns all registered agencies.
	List() []Agency

	// StartAll starts all agencies.
	StartAll(ctx context.Context) error

	// StopAll stops all agencies.
	StopAll(ctx context.Context) error
}

// DefaultAgencyRegistry is the default implementation of AgencyRegistry.
type DefaultAgencyRegistry struct {
	mu       sync.RWMutex
	agencies map[AgencyName]Agency
}

// NewDefaultAgencyRegistry creates a new default agency registry.
func NewDefaultAgencyRegistry() *DefaultAgencyRegistry {
	return &DefaultAgencyRegistry{
		agencies: make(map[AgencyName]Agency),
	}
}

// Register adds an agency to the registry.
func (r *DefaultAgencyRegistry) Register(ag Agency) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	name := ag.Name()
	if _, exists := r.agencies[name]; exists {
		return fmt.Errorf("agency already registered: %s", name)
	}

	r.agencies[name] = ag
	return nil
}

// Unregister removes an agency from the registry.
func (r *DefaultAgencyRegistry) Unregister(name AgencyName) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.agencies[name]; !exists {
		return fmt.Errorf("agency not found: %s", name)
	}

	delete(r.agencies, name)
	return nil
}

// Get returns an agency by name.
func (r *DefaultAgencyRegistry) Get(name AgencyName) (Agency, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	ag, exists := r.agencies[name]
	if !exists {
		return nil, fmt.Errorf("agency not found: %s", name)
	}

	return ag, nil
}

// List returns all registered agencies.
func (r *DefaultAgencyRegistry) List() []Agency {
	r.mu.RLock()
	defer r.mu.RUnlock()

	agencies := make([]Agency, 0, len(r.agencies))
	for _, ag := range r.agencies {
		agencies = append(agencies, ag)
	}

	return agencies
}

// StartAll starts all registered agencies.
func (r *DefaultAgencyRegistry) StartAll(ctx context.Context) error {
	r.mu.RLock()
	agencies := make([]Agency, 0, len(r.agencies))
	for _, ag := range r.agencies {
		agencies = append(agencies, ag)
	}
	r.mu.RUnlock()

	var lastErr error
	for _, ag := range agencies {
		if err := ag.Start(ctx); err != nil {
			lastErr = err
		}
	}

	return lastErr
}

// StopAll stops all registered agencies.
func (r *DefaultAgencyRegistry) StopAll(ctx context.Context) error {
	r.mu.RLock()
	agencies := make([]Agency, 0, len(r.agencies))
	for _, ag := range r.agencies {
		agencies = append(agencies, ag)
	}
	r.mu.RUnlock()

	var lastErr error
	for _, ag := range agencies {
		if err := ag.Stop(ctx); err != nil {
			lastErr = err
		}
	}

	return lastErr
}
