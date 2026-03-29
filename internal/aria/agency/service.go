// Package agency provides the Agency persistence service.
package agency

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/db"
)

// AgencyService handles persistence of agency data to the database.
type AgencyService struct {
	querier db.Querier
}

// NewAgencyService creates a new AgencyService.
func NewAgencyService(querier db.Querier) *AgencyService {
	return &AgencyService{
		querier: querier,
	}
}

// RegisterAgency persists an agency to the database.
func (s *AgencyService) RegisterAgency(ctx context.Context, agency Agency) error {
	// Convert in-memory Agency to DB params
	params := db.CreateAgencyParams{
		ID:          string(agency.Name()),
		Name:        string(agency.Name()),
		Domain:      agency.Domain(),
		Description: sql.NullString{String: agency.Description(), Valid: true},
		Status:      string(agency.Status()),
	}

	_, err := s.querier.CreateAgency(ctx, params)
	if err != nil {
		return fmt.Errorf("failed to create agency: %w", err)
	}

	return nil
}

// UnregisterAgency removes an agency from the database.
func (s *AgencyService) UnregisterAgency(ctx context.Context, name contracts.AgencyName) error {
	err := s.querier.DeleteAgency(ctx, string(name))
	if err != nil {
		return fmt.Errorf("failed to delete agency: %w", err)
	}
	return nil
}

// GetAgency retrieves an agency by name from the database.
func (s *AgencyService) GetAgency(ctx context.Context, name contracts.AgencyName) (Agency, error) {
	dbAgency, err := s.querier.GetAgencyByName(ctx, string(name))
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("agency not found: %s", name)
		}
		return nil, fmt.Errorf("failed to get agency: %w", err)
	}

	// Convert DB model to in-memory AgencyState
	state := AgencyState{
		AgencyID:   contracts.AgencyName(dbAgency.Name),
		Status:     dbAgency.Status,
		LastTaskID: "",
		Metrics:    make(map[string]any),
		UpdatedAt:  dbAgency.UpdatedAt,
	}

	// Note: For runtime, we return a wrapper that will be
	// replaced by the actual implementation when registered
	return &dbAgencyWrapper{
		name:        contracts.AgencyName(dbAgency.Name),
		domain:      dbAgency.Domain,
		description: dbAgency.Description.String,
		state:       state,
	}, nil
}

// ListAgencies retrieves all agencies from the database.
func (s *AgencyService) ListAgencies(ctx context.Context) ([]Agency, error) {
	dbAgencies, err := s.querier.ListAgencies(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to list agencies: %w", err)
	}

	agencies := make([]Agency, 0, len(dbAgencies))
	for _, dbA := range dbAgencies {
		state := AgencyState{
			AgencyID:   contracts.AgencyName(dbA.Name),
			Status:     dbA.Status,
			LastTaskID: "",
			Metrics:    make(map[string]any),
			UpdatedAt:  dbA.UpdatedAt,
		}
		agencies = append(agencies, &dbAgencyWrapper{
			name:        contracts.AgencyName(dbA.Name),
			domain:      dbA.Domain,
			description: dbA.Description.String,
			state:       state,
		})
	}

	return agencies, nil
}

// UpdateAgencyStatus updates an agency's status in the database.
func (s *AgencyService) UpdateAgencyStatus(ctx context.Context, name contracts.AgencyName, status AgencyStatus) error {
	params := db.UpdateAgencyStatusParams{
		Status: string(status),
		ID:     string(name),
	}
	err := s.querier.UpdateAgencyStatus(ctx, params)
	if err != nil {
		return fmt.Errorf("failed to update agency status: %w", err)
	}
	return nil
}

// SaveAgencyState persists agency state to the database.
// Uses the agency_states table for full state including metrics.
func (s *AgencyService) SaveAgencyState(ctx context.Context, name contracts.AgencyName, state AgencyState) error {
	// Serialize metrics to JSON
	metricsJSON := sql.NullString{String: "{}", Valid: true}
	if state.Metrics != nil {
		metricsBytes, err := json.Marshal(state.Metrics)
		if err == nil {
			metricsJSON = sql.NullString{String: string(metricsBytes), Valid: true}
		}
	}

	// Upsert full state to agency_states table
	params := db.UpsertAgencyStateParams{
		ID:         string(name) + "-state",
		AgencyID:   string(name),
		Status:     state.Status,
		LastTaskID: sql.NullString{String: state.LastTaskID, Valid: state.LastTaskID != ""},
		Metrics:    metricsJSON,
	}
	_, err := s.querier.UpsertAgencyState(ctx, params)
	if err != nil {
		return fmt.Errorf("failed to save agency state: %w", err)
	}

	return nil
}

// LoadAgencyState loads agency state from the database.
func (s *AgencyService) LoadAgencyState(ctx context.Context, name contracts.AgencyName) (AgencyState, error) {
	dbState, err := s.querier.GetAgencyState(ctx, string(name))
	if err != nil {
		if err == sql.ErrNoRows {
			// Return empty state if not found
			return AgencyState{
				AgencyID: name,
				Status:   "active",
				Metrics:  make(map[string]any),
			}, nil
		}
		return AgencyState{}, fmt.Errorf("failed to load agency state: %w", err)
	}

	// Parse metrics JSON
	metrics := make(map[string]any)
	if dbState.Metrics.Valid && dbState.Metrics.String != "" {
		if err := json.Unmarshal([]byte(dbState.Metrics.String), &metrics); err != nil {
			metrics = make(map[string]any)
		}
	}

	return AgencyState{
		AgencyID:   contracts.AgencyName(dbState.AgencyID),
		Status:     dbState.Status,
		LastTaskID: dbState.LastTaskID.String,
		Metrics:    metrics,
		UpdatedAt:  dbState.UpdatedAt,
	}, nil
}

// LoadAgenciesFromDB loads all registered agencies from database.
// Returns a map of agency name to state.
func (s *AgencyService) LoadAgenciesFromDB(ctx context.Context) (map[contracts.AgencyName]AgencyState, error) {
	dbAgencies, err := s.querier.ListAgencies(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to load agencies: %w", err)
	}

	result := make(map[contracts.AgencyName]AgencyState)
	for _, dbA := range dbAgencies {
		name := contracts.AgencyName(dbA.Name)

		// Try to load full state from agency_states table
		state, err := s.LoadAgencyState(ctx, name)
		if err != nil {
			// Fall back to basic agency info
			state = AgencyState{
				AgencyID:   name,
				Status:     dbA.Status,
				LastTaskID: "",
				Metrics:    make(map[string]any),
				UpdatedAt:  dbA.UpdatedAt,
			}
		}

		result[name] = state
	}

	return result, nil
}

// IsAgencyRegistered checks if an agency is registered in the database.
func (s *AgencyService) IsAgencyRegistered(ctx context.Context, name contracts.AgencyName) (bool, error) {
	_, err := s.querier.GetAgencyByName(ctx, string(name))
	if err != nil {
		if err == sql.ErrNoRows {
			return false, nil
		}
		return false, fmt.Errorf("failed to check agency: %w", err)
	}
	return true, nil
}

// dbAgencyWrapper is a minimal implementation of Agency for database operations.
type dbAgencyWrapper struct {
	name        contracts.AgencyName
	domain      string
	description string
	state       AgencyState
}

func (a *dbAgencyWrapper) Name() contracts.AgencyName { return a.name }
func (a *dbAgencyWrapper) Domain() string             { return a.domain }
func (a *dbAgencyWrapper) Description() string        { return a.description }
func (a *dbAgencyWrapper) Status() AgencyStatus       { return AgencyStatus(a.state.Status) }
func (a *dbAgencyWrapper) GetState() AgencyState      { return a.state }
func (a *dbAgencyWrapper) SaveState(state AgencyState) error {
	a.state = state
	return nil
}
func (a *dbAgencyWrapper) Agents() []contracts.AgentName { return nil }
func (a *dbAgencyWrapper) GetAgent(name contracts.AgentName) (interface{}, error) {
	return nil, fmt.Errorf("agent not found: %s", name)
}
func (a *dbAgencyWrapper) Memory() DomainMemory { return nil }
func (a *dbAgencyWrapper) Subscribe(ctx context.Context) <-chan contracts.AgencyEvent {
	ch := make(chan contracts.AgencyEvent, 64)
	close(ch)
	return ch
}
func (a *dbAgencyWrapper) Start(ctx context.Context) error  { return nil }
func (a *dbAgencyWrapper) Stop(ctx context.Context) error   { return nil }
func (a *dbAgencyWrapper) Pause(ctx context.Context) error  { return nil }
func (a *dbAgencyWrapper) Resume(ctx context.Context) error { return nil }
func (a *dbAgencyWrapper) Execute(ctx context.Context, task contracts.Task) (contracts.Result, error) {
	return contracts.Result{}, nil
}

// PersistableAgency extends Agency with persistence support.
type PersistableAgency interface {
	Agency
	PersistState(ctx context.Context, service *AgencyService) error
	LoadState(ctx context.Context, service *AgencyService) error
}

// DefaultPersistableAgency wraps an agency with persistence capabilities.
type DefaultPersistableAgency struct {
	Agency
	service *AgencyService
}

// NewPersistableAgency creates a new persistable agency.
func NewPersistableAgency(agency Agency, service *AgencyService) PersistableAgency {
	return &DefaultPersistableAgency{
		Agency:  agency,
		service: service,
	}
}

// PersistState saves the current agency state to the database.
func (p *DefaultPersistableAgency) PersistState(ctx context.Context, service *AgencyService) error {
	state := p.Agency.GetState()
	return service.SaveAgencyState(ctx, p.Agency.Name(), state)
}

// LoadState loads agency state from the database.
func (p *DefaultPersistableAgency) LoadState(ctx context.Context, service *AgencyService) error {
	agency, err := service.GetAgency(ctx, p.Agency.Name())
	if err != nil {
		return err
	}
	return p.Agency.SaveState(agency.GetState())
}

// AutoPersistAgency wraps an agency to automatically persist state on changes.
type AutoPersistAgency struct {
	PersistableAgency
	persistInterval time.Duration
	service         *AgencyService
}

// NewAutoPersistAgency creates an agency that automatically persists state.
func NewAutoPersistAgency(agency Agency, service *AgencyService, interval time.Duration) *AutoPersistAgency {
	return &AutoPersistAgency{
		PersistableAgency: NewPersistableAgency(agency, service),
		persistInterval:   interval,
		service:           service,
	}
}

// Start starts the agency and begins auto-persist goroutine.
func (a *AutoPersistAgency) Start(ctx context.Context) error {
	if err := a.PersistableAgency.Start(ctx); err != nil {
		return err
	}
	go a.autoPersistLoop(ctx)
	return nil
}

func (a *AutoPersistAgency) autoPersistLoop(ctx context.Context) {
	ticker := time.NewTicker(a.persistInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := a.PersistState(ctx, a.service); err != nil {
				fmt.Printf("auto-persist error: %v\n", err)
			}
		}
	}
}

// AgencyMetrics holds metrics data for persistence.
type AgencyMetrics struct {
	TasksCompleted int64          `json:"tasks_completed"`
	TasksFailed    int64          `json:"tasks_failed"`
	AvgDurationMs  int64          `json:"avg_duration_ms"`
	LastTaskID     string         `json:"last_task_id"`
	Custom         map[string]any `json:"custom"`
}

// MetricsToJSON converts metrics to JSON string for DB storage.
func MetricsToJSON(metrics map[string]any) (string, error) {
	if metrics == nil {
		return "{}", nil
	}
	data, err := json.Marshal(metrics)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// JSONToMetrics converts JSON string to metrics map.
func JSONToMetrics(data string) (map[string]any, error) {
	if data == "" {
		return make(map[string]any), nil
	}
	var result map[string]any
	err := json.Unmarshal([]byte(data), &result)
	if err != nil {
		return nil, err
	}
	return result, nil
}
