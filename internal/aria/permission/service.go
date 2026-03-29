// Package permission provides the extended permission system for ARIA,
// including permission levels, scopes, rules, and action types.
package permission

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// permissionService implements ExtendedPermissionService.
type permissionService struct {
	mu        sync.RWMutex
	rules     map[string][]PermissionRule // agencyID -> rules
	requests  map[string]Request          // requestID -> request
	responses map[string]Response         // requestID -> response
}

// NewService creates a new ExtendedPermissionService.
func NewService() ExtendedPermissionService {
	return &permissionService{
		rules:     make(map[string][]PermissionRule),
		requests:  make(map[string]Request),
		responses: make(map[string]Response),
	}
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
// Since PermissionRule doesn't have an AgencyID field, we use the CreatedBy as the agency key
// or default to "global" if CreatedBy is empty.
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
