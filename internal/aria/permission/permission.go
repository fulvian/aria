// Package permission provides the extended permission system for ARIA,
// including permission levels, scopes, rules, and action types.
//
// This package extends the existing internal/permission/ package with
// the additional concepts defined in Blueprint Section 5.1.
package permission

import (
	"context"
	"time"
)

// PermissionLevel determines what an entity can do.
type PermissionLevel int

// Permission level constants (higher includes lower)
const (
	PermissionNone   PermissionLevel = 0 // No permission
	PermissionAsk    PermissionLevel = 1 // Must ask every time
	PermissionNotify PermissionLevel = 2 // Notify but execute
	PermissionAuto   PermissionLevel = 3 // Execute automatically
)

// PermissionScope defines how long a permission lasts.
type PermissionScope string

// Permission scope constants
const (
	ScopeSession   PermissionScope = "session"   // Current session only
	ScopeTask      PermissionScope = "task"      // Current task only
	ScopePermanent PermissionScope = "permanent" // Until revoked
	ScopeTemporary PermissionScope = "temporary" // With expiration
)

// ActionType represents types of actions that can be performed.
type ActionType string

// Action type constants
const (
	ActionRead     ActionType = "read"
	ActionWrite    ActionType = "write"
	ActionExecute  ActionType = "execute"
	ActionDelete   ActionType = "delete"
	ActionNetwork  ActionType = "network"
	ActionSchedule ActionType = "schedule"
	ActionNotify   ActionType = "notify"
)

// ResourcePattern represents a pattern for matching resources.
type ResourcePattern struct {
	Type    string // "file", "url", "api", "task"
	Pattern string
}

// Condition represents a condition for a permission rule.
type Condition struct {
	Type     string
	Field    string
	Operator string
	Value    any
}

// PermissionRule defines a permission grant or restriction.
type PermissionRule struct {
	ID         string
	Action     ActionType
	Resource   ResourcePattern
	Level      PermissionLevel
	Scope      PermissionScope
	ExpiresAt  *time.Time
	Conditions []Condition
	CreatedAt  time.Time
	CreatedBy  string
}

// Request represents a permission request.
type Request struct {
	ID          string
	Action      ActionType
	Resource    string
	AgencyID    string
	AgentID     string
	TaskID      string
	Reason      string
	RequestedAt time.Time
}

// Response represents the response to a permission request.
type Response struct {
	RequestID   string
	Granted     bool
	Level       PermissionLevel
	Scope       PermissionScope
	ExpiresAt   *time.Time
	Reason      string
	RespondedAt time.Time
}

// ExtendedPermissionService extends the base permission service
// with ARIA-specific features like rules, scopes, and action types.
//
// Reference: Blueprint Section 5.1
type ExtendedPermissionService interface {
	// Request permission for an action
	Request(ctx context.Context, req Request) (Response, error)

	// Grant gives permission (called by user)
	Grant(ctx context.Context, requestID string, level PermissionLevel, scope PermissionScope) error

	// Deny denies a permission request
	Deny(ctx context.Context, requestID string, reason string) error

	// Check verifies if an action is allowed
	Check(ctx context.Context, agencyID, agentID string, action ActionType, resource string) (bool, error)

	// GetRules returns all permission rules
	GetRules(ctx context.Context, agencyID string) ([]PermissionRule, error)

	// AddRule adds a new permission rule
	AddRule(ctx context.Context, rule PermissionRule) error

	// RemoveRule removes a permission rule
	RemoveRule(ctx context.Context, ruleID string) error

	// GetEffectiveLevel returns the effective permission level
	GetEffectiveLevel(ctx context.Context, agencyID, agentID string, action ActionType) (PermissionLevel, error)
}
