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

// PersistableAgencyRegistry wraps a registry with database persistence.
type PersistableAgencyRegistry struct {
	*DefaultAgencyRegistry
	service *AgencyService
}

// NewPersistableAgencyRegistry creates a registry with persistence support.
func NewPersistableAgencyRegistry(service *AgencyService) *PersistableAgencyRegistry {
	return &PersistableAgencyRegistry{
		DefaultAgencyRegistry: NewDefaultAgencyRegistry(),
		service:               service,
	}
}

// Register adds an agency to the registry and persists it to the database.
func (r *PersistableAgencyRegistry) Register(ag Agency) error {
	// First register in memory
	if err := r.DefaultAgencyRegistry.Register(ag); err != nil {
		return err
	}

	// Then persist to database (if service is available)
	if r.service != nil {
		ctx := context.Background()
		if err := r.service.RegisterAgency(ctx, ag); err != nil {
			// Log but don't fail - agency is registered in memory
			fmt.Printf("warning: failed to persist agency: %v\n", err)
		}
	}

	return nil
}

// Unregister removes an agency from the registry and database.
func (r *PersistableAgencyRegistry) Unregister(name AgencyName) error {
	// First remove from database (if service is available)
	if r.service != nil {
		ctx := context.Background()
		if err := r.service.UnregisterAgency(ctx, name); err != nil {
			// Log but don't fail - try to remove from memory anyway
			fmt.Printf("warning: failed to remove agency from DB: %v\n", err)
		}
	}

	// Then remove from memory
	return r.DefaultAgencyRegistry.Unregister(name)
}

// LoadFromDatabase loads agencies from database into the registry.
func (r *PersistableAgencyRegistry) LoadFromDatabase(ctx context.Context) error {
	if r.service == nil {
		return fmt.Errorf("no service configured")
	}

	// Get all agencies from DB
	agencies, err := r.service.ListAgencies(ctx)
	if err != nil {
		return fmt.Errorf("failed to load agencies from DB: %w", err)
	}

	// Register each agency in memory
	for _, ag := range agencies {
		// Don't overwrite if already registered
		if _, err := r.DefaultAgencyRegistry.Get(ag.Name()); err == nil {
			continue // already exists
		}
		if err := r.DefaultAgencyRegistry.Register(ag); err != nil {
			fmt.Printf("warning: failed to register agency from DB: %v\n", err)
		}
	}

	return nil
}
