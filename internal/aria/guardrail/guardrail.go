// Package guardrail provides guardrails for proactive behavior in ARIA,
// including action budgets, user preferences, and audit logging.
//
// This package implements the guardrail interfaces defined in Blueprint Section 5.2.
package guardrail

import (
	"context"
	"time"
)

// ActionType represents types of proactive actions.
type ActionType string

// ImpactLevel represents the potential impact of an action.
type ImpactLevel string

// Impact level constants
const (
	ImpactLow      ImpactLevel = "low"
	ImpactMedium   ImpactLevel = "medium"
	ImpactHigh     ImpactLevel = "high"
	ImpactCritical ImpactLevel = "critical"
)

// ProactiveAction represents an action ARIA wants to take proactively.
type ProactiveAction struct {
	ID          string
	Type        ActionType
	Description string
	Impact      ImpactLevel
	Reversible  bool
	Reason      string
	Context     map[string]any
	CreatedAt   time.Time
}

// Budget represents a rate limit budget for actions.
type Budget struct {
	ActionType  ActionType
	Limit       int
	Used        int
	ResetAt     time.Time
	WindowHours int
}

// TimeRange represents a time range for preferences.
type TimeRange struct {
	Start string // "HH:MM"
	End   string // "HH:MM"
	Days  []int  // 0=Sunday, 1=Monday, etc.
}

// NotificationLevel determines how ARIA should notify.
type NotificationLevel string

// Notification level constants
const (
	NotifyAll       NotificationLevel = "all"
	NotifyImportant NotificationLevel = "important"
	NotifyMinimal   NotificationLevel = "minimal"
	NotifyNone      NotificationLevel = "none"
)

// NotifyChannel represents where to send notifications.
type NotifyChannel string

// Notify channel constants
const (
	ChannelTUI      NotifyChannel = "tui"
	ChannelTerminal NotifyChannel = "terminal"
	ChannelFile     NotifyChannel = "file"
)

// AutoApproveRule defines patterns for auto-approval.
type AutoApproveRule struct {
	ID              string
	ActionType      ActionType
	ResourcePattern string
	MaxPerDay       int
	UsedToday       int
	LastUsed        *time.Time
}

// ProactivePreferences define how ARIA should behave proactively.
type ProactivePreferences struct {
	// What ARIA can do proactively
	AllowedActions   []ActionType
	ForbiddenActions []ActionType

	// When ARIA can act
	QuietHours  []TimeRange
	ActiveHours []TimeRange

	// How ARIA should notify
	NotificationLevel NotificationLevel
	NotifyChannels    []NotifyChannel

	// Limits
	MaxDailyActions       int
	MaxPendingSuggestions int

	// Auto-approval rules
	AutoApprovePatterns []AutoApproveRule
}

// AuditEntry represents an entry in the audit log.
type AuditEntry struct {
	ID          string
	Action      ProactiveAction
	Decision    string // approved, denied, rate_limited
	Reason      string
	Preferences ProactivePreferences
	Timestamp   time.Time
}

// AuditFilter represents filters for audit log queries.
type AuditFilter struct {
	AgencyID   string
	ActionType ActionType
	Decision   string
	StartTime  *time.Time
	EndTime    *time.Time
	Limit      int
}

// GuardrailService checks if proactive actions are allowed.
//
// Reference: Blueprint Section 5.2
type GuardrailService interface {
	// CanExecute checks if an action can be executed
	CanExecute(ctx context.Context, action ProactiveAction) (bool, string, error)

	// GetActionBudget returns the current budget for an action type
	GetActionBudget(ctx context.Context, actionType ActionType) (Budget, error)

	// ConsumeAction consumes from the action budget
	ConsumeAction(ctx context.Context, action ProactiveAction) error

	// GetUserPreferences returns the user's proactive preferences
	GetUserPreferences(ctx context.Context) (ProactivePreferences, error)

	// UpdatePreferences updates user preferences
	UpdatePreferences(ctx context.Context, prefs ProactivePreferences) error

	// LogAction logs an action and its outcome
	LogAction(ctx context.Context, action ProactiveAction, outcome string) error

	// GetAuditLog returns the audit log
	GetAuditLog(ctx context.Context, filter AuditFilter) ([]AuditEntry, error)
}
