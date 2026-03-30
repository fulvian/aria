// Package guardrail provides guardrails for proactive behavior in ARIA,
// including action budgets, user preferences, and audit logging.
package guardrail

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"slices"
	"sync"
	"time"

	"github.com/fulvian/aria/internal/aria/config"
)

// PersistenceManager handles saving and loading guardrail state.
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

// PersistenceData represents the serializable state of the guardrail service.
type PersistenceData struct {
	Budgets  map[string]Budget    `json:"budgets"`
	Prefs    ProactivePreferences `json:"prefs"`
	AuditLog []AuditEntry         `json:"audit_log"`
}

// Save saves the guardrail state to a file.
func (f *FilePersistenceManager) Save(ctx context.Context, data *PersistenceData) error {
	f.mu.Lock()
	defer f.mu.Unlock()

	jsonData, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal guardrail state: %w", err)
	}

	if err := os.WriteFile(f.filePath, jsonData, 0o644); err != nil {
		return fmt.Errorf("failed to write guardrail state file: %w", err)
	}

	return nil
}

// Load loads the guardrail state from a file.
func (f *FilePersistenceManager) Load(ctx context.Context) (*PersistenceData, error) {
	f.mu.RLock()
	defer f.mu.RUnlock()

	jsonData, err := os.ReadFile(f.filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil // No file exists yet
		}
		return nil, fmt.Errorf("failed to read guardrail state file: %w", err)
	}

	var data PersistenceData
	if err := json.Unmarshal(jsonData, &data); err != nil {
		return nil, fmt.Errorf("failed to unmarshal guardrail state: %w", err)
	}

	return &data, nil
}

// Action type constants for proactive actions
const (
	ActionRead    ActionType = "read"
	ActionWrite   ActionType = "write"
	ActionDelete  ActionType = "delete"
	ActionNotify  ActionType = "notify"
	ActionExecute ActionType = "execute"
)

// Default maximum audit entries to keep in memory
const defaultMaxAuditEntries = 1000

// guardrailService implements the GuardrailService interface.
type guardrailService struct {
	config      config.GuardrailsConfig
	mu          sync.RWMutex
	budgets     map[ActionType]*Budget
	prefs       ProactivePreferences
	auditLog    []AuditEntry
	maxAudit    int
	persistence PersistenceManager
}

// NewService creates a new GuardrailService with the given configuration.
func NewService(cfg config.GuardrailsConfig) GuardrailService {
	return &guardrailService{
		config:   cfg,
		budgets:  make(map[ActionType]*Budget),
		prefs:    defaultPreferences(),
		auditLog: make([]AuditEntry, 0, defaultMaxAuditEntries),
		maxAudit: defaultMaxAuditEntries,
	}
}

// NewServiceWithPersistence creates a new service with persistence manager.
func NewServiceWithPersistence(cfg config.GuardrailsConfig, persistence PersistenceManager) GuardrailService {
	svc := &guardrailService{
		config:      cfg,
		budgets:     make(map[ActionType]*Budget),
		prefs:       defaultPreferences(),
		auditLog:    make([]AuditEntry, 0, defaultMaxAuditEntries),
		maxAudit:    defaultMaxAuditEntries,
		persistence: persistence,
	}

	// Try to load existing state
	if persistence != nil {
		if data, err := persistence.Load(context.Background()); err == nil && data != nil {
			// Restore budgets
			for actionType, budget := range data.Budgets {
				svc.budgets[ActionType(actionType)] = &budget
			}
			// Restore preferences
			svc.prefs = data.Prefs
			// Restore audit log
			svc.auditLog = data.AuditLog
		}
	}

	return svc
}

// persistIfEnabled saves state if persistence is configured.
func (s *guardrailService) persistIfEnabled() {
	if s.persistence != nil {
		data := &PersistenceData{
			Budgets:  make(map[string]Budget),
			AuditLog: s.auditLog,
		}
		for actionType, budget := range s.budgets {
			data.Budgets[string(actionType)] = *budget
		}
		// Fire and forget persistence save
		go s.persistence.Save(context.Background(), data)
	}
}

// SavePersistence exports the current state for external persistence.
func (s *guardrailService) SavePersistence(ctx context.Context) error {
	if s.persistence == nil {
		return fmt.Errorf("no persistence manager configured")
	}
	data := &PersistenceData{
		Budgets: make(map[string]Budget),
		Prefs:   s.prefs,
	}
	for actionType, budget := range s.budgets {
		data.Budgets[string(actionType)] = *budget
	}
	data.AuditLog = s.auditLog
	return s.persistence.Save(ctx, data)
}

// defaultPreferences returns sensible defaults for proactive preferences.
func defaultPreferences() ProactivePreferences {
	return ProactivePreferences{
		AllowedActions:        []ActionType{ActionRead, ActionNotify},
		ForbiddenActions:      []ActionType{ActionDelete, ActionWrite},
		NotificationLevel:     NotifyImportant,
		NotifyChannels:        []NotifyChannel{ChannelTUI},
		MaxDailyActions:       10,
		MaxPendingSuggestions: 5,
		AutoApprovePatterns:   []AutoApproveRule{},
		QuietHours:            []TimeRange{},
		ActiveHours: []TimeRange{
			{Start: "09:00", End: "18:00", Days: []int{1, 2, 3, 4, 5}}, // Weekdays 9-18
		},
	}
}

// CanExecute checks if an action can be executed.
func (s *guardrailService) CanExecute(ctx context.Context, action ProactiveAction) (bool, string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	// Check if proactive is allowed in config
	if !s.config.AllowProactive {
		return false, "proactive actions are disabled in configuration", nil
	}

	// Check if action type is forbidden
	for _, forbidden := range s.prefs.ForbiddenActions {
		if action.Type == forbidden {
			return false, fmt.Sprintf("action type %s is forbidden by user preferences", action.Type), nil
		}
	}

	// Check if action type is allowed (if AllowedActions is not empty)
	if len(s.prefs.AllowedActions) > 0 {
		allowed := false
		for _, allowedType := range s.prefs.AllowedActions {
			if action.Type == allowedType {
				allowed = true
				break
			}
		}
		if !allowed {
			return false, fmt.Sprintf("action type %s is not in the allowed list", action.Type), nil
		}
	}

	// Check QuietHours
	if s.isQuietHours() {
		return false, "current time is within quiet hours", nil
	}

	// Check ActiveHours (if defined)
	if len(s.prefs.ActiveHours) > 0 && !s.isActiveHours() {
		return false, "current time is outside active hours", nil
	}

	// Check budget limits
	budget := s.getBudget(action.Type)
	if budget.Used >= budget.Limit {
		return false, fmt.Sprintf("budget limit reached for action type %s", action.Type), nil
	}

	// Check total daily actions limit
	totalUsed := 0
	for _, b := range s.budgets {
		totalUsed += b.Used
	}
	if totalUsed >= s.config.MaxDailyActions {
		return false, "total daily action limit reached", nil
	}

	// Check auto-approve rules for low-impact auto-approval
	if s.shouldAutoApprove(action) {
		return true, "auto-approved low-impact action", nil
	}

	return true, "approved", nil
}

// GetActionBudget returns the current budget for an action type.
func (s *guardrailService) GetActionBudget(ctx context.Context, actionType ActionType) (Budget, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	budget := s.getBudget(actionType)
	return *budget, nil
}

// ConsumeAction consumes from the action budget.
func (s *guardrailService) ConsumeAction(ctx context.Context, action ProactiveAction) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	budget := s.getBudget(action.Type)

	// Check if window has expired and reset if needed
	if time.Now().After(budget.ResetAt) {
		budget.Used = 0
		budget.ResetAt = time.Now().Add(time.Duration(budget.WindowHours) * time.Hour)
	}

	// Check if over limit
	if budget.Used >= budget.Limit {
		return fmt.Errorf("budget limit exceeded for action type %s", action.Type)
	}

	budget.Used++
	return nil
}

// GetUserPreferences returns the user's proactive preferences.
func (s *guardrailService) GetUserPreferences(ctx context.Context) (ProactivePreferences, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return s.prefs, nil
}

// UpdatePreferences updates user preferences.
func (s *guardrailService) UpdatePreferences(ctx context.Context, prefs ProactivePreferences) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Validate input
	if prefs.MaxDailyActions < 0 {
		return fmt.Errorf("maxDailyActions cannot be negative")
	}
	if prefs.MaxPendingSuggestions < 0 {
		return fmt.Errorf("maxPendingSuggestions cannot be negative")
	}

	// Validate TimeRanges
	for _, tr := range prefs.QuietHours {
		if err := validateTimeRange(tr); err != nil {
			return fmt.Errorf("invalid quiet hours: %w", err)
		}
	}
	for _, tr := range prefs.ActiveHours {
		if err := validateTimeRange(tr); err != nil {
			return fmt.Errorf("invalid active hours: %w", err)
		}
	}

	s.prefs = prefs
	return nil
}

// LogAction logs an action and its outcome.
func (s *guardrailService) LogAction(ctx context.Context, action ProactiveAction, outcome string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	entry := AuditEntry{
		ID:          fmt.Sprintf("%d", time.Now().UnixNano()),
		Action:      action,
		Decision:    outcome,
		Reason:      "",
		Preferences: s.prefs,
		Timestamp:   time.Now(),
	}

	s.auditLog = append(s.auditLog, entry)

	// Trim if exceeds maxAudit
	if len(s.auditLog) > s.maxAudit {
		s.auditLog = s.auditLog[len(s.auditLog)-s.maxAudit:]
	}

	return nil
}

// GetAuditLog returns the audit log with optional filtering.
func (s *guardrailService) GetAuditLog(ctx context.Context, filter AuditFilter) ([]AuditEntry, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	result := make([]AuditEntry, 0, len(s.auditLog))

	for _, entry := range s.auditLog {
		// Apply filters
		if filter.AgencyID != "" && entry.Action.Context != nil {
			agencyID, ok := entry.Action.Context["agencyID"].(string)
			if !ok || agencyID != filter.AgencyID {
				continue
			}
		}

		if filter.ActionType != "" && entry.Action.Type != filter.ActionType {
			continue
		}

		if filter.Decision != "" && entry.Decision != filter.Decision {
			continue
		}

		if filter.StartTime != nil && entry.Timestamp.Before(*filter.StartTime) {
			continue
		}

		if filter.EndTime != nil && entry.Timestamp.After(*filter.EndTime) {
			continue
		}

		result = append(result, entry)
	}

	// Apply limit (most recent first)
	if filter.Limit > 0 && len(result) > filter.Limit {
		result = result[len(result)-filter.Limit:]
	}

	// Reverse to return most recent first
	slices.Reverse(result)

	return result, nil
}

// isQuietHours checks if current time is in a quiet hour.
func (s *guardrailService) isQuietHours() bool {
	if len(s.prefs.QuietHours) == 0 {
		return false
	}

	now := time.Now()
	currentTime := now.Format("15:04")
	currentDay := int(now.Weekday())

	for _, tr := range s.prefs.QuietHours {
		if !s.isTimeInRange(currentTime, tr.Start, tr.End) {
			continue
		}
		if len(tr.Days) == 0 || slices.Contains(tr.Days, currentDay) {
			return true
		}
	}

	return false
}

// isActiveHours checks if current time is in an active hour.
func (s *guardrailService) isActiveHours() bool {
	if len(s.prefs.ActiveHours) == 0 {
		return true // No restrictions if no active hours defined
	}

	now := time.Now()
	currentTime := now.Format("15:04")
	currentDay := int(now.Weekday())

	for _, tr := range s.prefs.ActiveHours {
		if !s.isTimeInRange(currentTime, tr.Start, tr.End) {
			continue
		}
		if len(tr.Days) == 0 || slices.Contains(tr.Days, currentDay) {
			return true
		}
	}

	return false
}

// getBudget returns budget for action type, creating if needed.
func (s *guardrailService) getBudget(actionType ActionType) *Budget {
	if budget, exists := s.budgets[actionType]; exists {
		return budget
	}

	// Create default budget
	budget := &Budget{
		ActionType:  actionType,
		Limit:       s.config.MaxDailyActions,
		Used:        0,
		ResetAt:     time.Now().Add(24 * time.Hour),
		WindowHours: 24,
	}
	s.budgets[actionType] = budget
	return budget
}

// shouldAutoApprove checks if action should be auto-approved.
func (s *guardrailService) shouldAutoApprove(action ProactiveAction) bool {
	// Only auto-approve low-impact actions
	if action.Impact != ImpactLow {
		return false
	}

	// Check against auto-approve patterns
	for _, rule := range s.prefs.AutoApprovePatterns {
		if rule.ActionType != action.Type {
			continue
		}

		// Check daily limit for this rule
		if rule.MaxPerDay > 0 && rule.UsedToday >= rule.MaxPerDay {
			continue
		}

		// For MVP, simple pattern matching (can be enhanced later)
		return true
	}

	return false
}

// isTimeInRange checks if a time string (HH:MM format) is within a range.
func (s *guardrailService) isTimeInRange(current, start, end string) bool {
	// Handle overnight ranges (e.g., 22:00 to 06:00)
	if start > end {
		return current >= start || current <= end
	}
	return current >= start && current <= end
}

// validateTimeRange validates a TimeRange struct.
func validateTimeRange(tr TimeRange) error {
	if tr.Start == "" || tr.End == "" {
		return fmt.Errorf("start and end time are required")
	}

	// Validate time format (HH:MM)
	if len(tr.Start) != 5 || tr.Start[2] != ':' {
		return fmt.Errorf("invalid start time format, expected HH:MM")
	}
	if len(tr.End) != 5 || tr.End[2] != ':' {
		return fmt.Errorf("invalid end time format, expected HH:MM")
	}

	// Validate day values
	for _, day := range tr.Days {
		if day < 0 || day > 6 {
			return fmt.Errorf("invalid day value %d, expected 0-6 (Sunday-Saturday)", day)
		}
	}

	return nil
}
