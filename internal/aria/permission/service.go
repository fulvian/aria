// Package permission provides the extended permission system for ARIA,
// including permission levels, scopes, rules, and action types.
package permission

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"

	"github.com/google/uuid"
)

// PersistenceManager handles saving and loading permission state.
type PersistenceManager interface {
	Save(ctx context.Context, data *PersistenceData) error
	Load(ctx context.Context) (*PersistenceData, error)
}

// FilePersistenceManager implements PersistenceManager using JSON files.
type FilePersistenceManager struct {
	mu       sync.RWMutex
	filePath string
}

// NewFilePersistenceManager creates a file-based persistence manager.
func NewFilePersistenceManager(filePath string) *FilePersistenceManager {
	return &FilePersistenceManager{
		filePath: filePath,
	}
}

// PersistenceData represents the serializable state of the permission service.
type PersistenceData struct {
	Rules     []PermissionRule `json:"rules"`
	Requests  []Request        `json:"requests"`
	Responses []Response       `json:"responses"`
}

// Save saves the permission state to a file.
func (f *FilePersistenceManager) Save(ctx context.Context, data *PersistenceData) error {
	f.mu.Lock()
	defer f.mu.Unlock()

	jsonData, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal permission state: %w", err)
	}

	if err := os.WriteFile(f.filePath, jsonData, 0o644); err != nil {
		return fmt.Errorf("failed to write permission state file: %w", err)
	}

	return nil
}

// Load loads the permission state from a file.
func (f *FilePersistenceManager) Load(ctx context.Context) (*PersistenceData, error) {
	f.mu.RLock()
	defer f.mu.RUnlock()

	jsonData, err := os.ReadFile(f.filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil // No file exists yet
		}
		return nil, fmt.Errorf("failed to read permission state file: %w", err)
	}

	var data PersistenceData
	if err := json.Unmarshal(jsonData, &data); err != nil {
		return nil, fmt.Errorf("failed to unmarshal permission state: %w", err)
	}

	return &data, nil
}

// permissionService implements ExtendedPermissionService with optional persistence.
type permissionService struct {
	mu          sync.RWMutex
	rules       map[string][]PermissionRule // agencyID -> rules
	requests    map[string]Request          // requestID -> request
	responses   map[string]Response         // requestID -> response
	persistence PersistenceManager
}

// NewService creates a new ExtendedPermissionService.
func NewService() ExtendedPermissionService {
	return &permissionService{
		rules:     make(map[string][]PermissionRule),
		requests:  make(map[string]Request),
		responses: make(map[string]Response),
	}
}

// NewServiceWithPersistence creates a new service with persistence manager.
func NewServiceWithPersistence(persistence PersistenceManager) ExtendedPermissionService {
	svc := &permissionService{
		rules:       make(map[string][]PermissionRule),
		requests:    make(map[string]Request),
		responses:   make(map[string]Response),
		persistence: persistence,
	}

	// Try to load existing state
	if persistence != nil {
		if data, err := persistence.Load(context.Background()); err == nil && data != nil {
			// Restore rules
			for _, rule := range data.Rules {
				svc.rules[rule.CreatedBy] = append(svc.rules[rule.CreatedBy], rule)
			}
			// Restore requests
			for _, req := range data.Requests {
				svc.requests[req.ID] = req
			}
			// Restore responses
			for _, resp := range data.Responses {
				svc.responses[resp.RequestID] = resp
			}
		}
	}

	return svc
}

// persistIfEnabled saves state if persistence is configured.
func (s *permissionService) persistIfEnabled() {
	if s.persistence != nil {
		data := &PersistenceData{
			Rules:     make([]PermissionRule, 0),
			Responses: make([]Response, 0),
		}
		for _, rules := range s.rules {
			data.Rules = append(data.Rules, rules...)
		}
		for _, resp := range s.responses {
			data.Responses = append(data.Responses, resp)
		}
		// Fire and forget persistence save
		go s.persistence.Save(context.Background(), data)
	}
}

// SavePersistence exports the current state for external persistence.
func (s *permissionService) SavePersistence(ctx context.Context) error {
	if s.persistence == nil {
		return fmt.Errorf("no persistence manager configured")
	}
	data := &PersistenceData{
		Rules:     make([]PermissionRule, 0),
		Requests:  make([]Request, 0),
		Responses: make([]Response, 0),
	}
	for _, rules := range s.rules {
		data.Rules = append(data.Rules, rules...)
	}
	for _, req := range s.requests {
		data.Requests = append(data.Requests, req)
	}
	for _, resp := range s.responses {
		data.Responses = append(data.Responses, resp)
	}
	return s.persistence.Save(ctx, data)
}

// Request creates a new permission request.
func (s *permissionService) Request(ctx context.Context, req Request) (Response, error) {
	if req.AgencyID == "" {
		return Response{}, fmt.Errorf("agencyID is required")
	}
	if req.AgentID == "" {
		return Response{}, fmt.Errorf("agentID is required")
	}
	if req.Action == "" {
		return Response{}, fmt.Errorf("action is required")
	}
	if req.Resource == "" {
		return Response{}, fmt.Errorf("resource is required")
	}

	req.ID = uuid.New().String()
	req.RequestedAt = time.Now()

	s.mu.Lock()
	s.requests[req.ID] = req
	s.mu.Unlock()

	return Response{
		RequestID:   req.ID,
		Granted:     false,
		Level:       PermissionNone,
		Scope:       ScopeSession,
		RespondedAt: time.Now(),
	}, nil
}

// Grant grants a permission request.
func (s *permissionService) Grant(ctx context.Context, requestID string, level PermissionLevel, scope PermissionScope) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	req, ok := s.requests[requestID]
	if !ok {
		return fmt.Errorf("request not found: %s", requestID)
	}

	expiresAt := s.computeExpiresAt(scope)
	resp := Response{
		RequestID:   requestID,
		Granted:     true,
		Level:       level,
		Scope:       scope,
		ExpiresAt:   expiresAt,
		RespondedAt: time.Now(),
	}
	s.responses[requestID] = resp

	if scope == ScopePermanent {
		rule := PermissionRule{
			ID:        uuid.New().String(),
			Action:    req.Action,
			Resource:  ResourcePattern{Type: "general", Pattern: req.Resource},
			Level:     level,
			Scope:     scope,
			CreatedAt: time.Now(),
			CreatedBy: "system",
		}
		s.rules[req.AgencyID] = append(s.rules[req.AgencyID], rule)
	}

	// Trigger persistence save
	s.persistIfEnabled()

	return nil
}

// Deny denies a permission request.
func (s *permissionService) Deny(ctx context.Context, requestID string, reason string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	_, ok := s.requests[requestID]
	if !ok {
		return fmt.Errorf("request not found: %s", requestID)
	}

	resp := Response{
		RequestID:   requestID,
		Granted:     false,
		Level:       PermissionNone,
		Scope:       ScopeSession,
		Reason:      reason,
		RespondedAt: time.Now(),
	}
	s.responses[requestID] = resp

	// Trigger persistence save
	s.persistIfEnabled()

	return nil
}

// Check verifies if an action is allowed.
func (s *permissionService) Check(ctx context.Context, agencyID, agentID string, action ActionType, resource string) (bool, error) {
	level, err := s.GetEffectiveLevel(ctx, agencyID, agentID, action)
	if err != nil {
		return false, err
	}
	return level >= PermissionAsk, nil
}

// GetRules returns all permission rules for an agency.
func (s *permissionService) GetRules(ctx context.Context, agencyID string) ([]PermissionRule, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	rules, ok := s.rules[agencyID]
	if !ok {
		return []PermissionRule{}, nil
	}

	result := make([]PermissionRule, 0, len(rules))
	now := time.Now()
	for _, rule := range rules {
		if rule.ExpiresAt != nil && rule.ExpiresAt.Before(now) {
			continue
		}
		result = append(result, rule)
	}
	return result, nil
}

// AddRule adds a new permission rule.
func (s *permissionService) AddRule(ctx context.Context, rule PermissionRule) error {
	if rule.Action == "" {
		return fmt.Errorf("action is required")
	}
	if rule.Level == PermissionNone {
		return fmt.Errorf("invalid permission level")
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	if rule.ID == "" {
		rule.ID = uuid.New().String()
	}

	agencyKey := rule.CreatedBy
	if agencyKey == "" {
		agencyKey = "global"
	}
	s.rules[agencyKey] = append(s.rules[agencyKey], rule)

	// Trigger persistence save
	s.persistIfEnabled()

	return nil
}

// RemoveRule removes a permission rule by ID.
func (s *permissionService) RemoveRule(ctx context.Context, ruleID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	for agencyID, rules := range s.rules {
		for i, rule := range rules {
			if rule.ID == ruleID {
				s.rules[agencyID] = append(rules[:i], rules[i+1:]...)
				// Trigger persistence save
				s.persistIfEnabled()
				return nil
			}
		}
	}
	return fmt.Errorf("rule not found: %s", ruleID)
}

// GetEffectiveLevel returns the effective permission level for an agency/agent/action.
func (s *permissionService) GetEffectiveLevel(ctx context.Context, agencyID, agentID string, action ActionType) (PermissionLevel, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	rules, ok := s.rules[agencyID]
	if !ok {
		return PermissionNone, nil
	}

	var highest PermissionLevel
	now := time.Now()
	for _, rule := range rules {
		if rule.ExpiresAt != nil && rule.ExpiresAt.Before(now) {
			continue
		}
		if rule.Action != action {
			continue
		}
		if rule.Level > highest {
			highest = rule.Level
		}
	}
	return highest, nil
}

// computeExpiresAt computes the expiration time based on scope.
func (s *permissionService) computeExpiresAt(scope PermissionScope) *time.Time {
	switch scope {
	case ScopeTemporary:
		t := time.Now().Add(24 * time.Hour)
		return &t
	case ScopeTask:
		t := time.Now().Add(1 * time.Hour)
		return &t
	case ScopeSession:
		t := time.Now().Add(4 * time.Hour)
		return &t
	default:
		return nil
	}
}
