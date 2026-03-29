package guardrail

import (
	"context"
	"testing"
	"time"

	"github.com/fulvian/aria/internal/aria/config"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewService(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}

	svc := NewService(cfg)
	assert.NotNil(t, svc)

	// Verify it implements GuardrailService
	var _ GuardrailService = svc
}

func TestDefaultPreferences(t *testing.T) {
	prefs := defaultPreferences()

	assert.Contains(t, prefs.AllowedActions, ActionRead)
	assert.Contains(t, prefs.ForbiddenActions, ActionDelete)
	assert.Equal(t, NotifyImportant, prefs.NotificationLevel)
	assert.Contains(t, prefs.NotifyChannels, ChannelTUI)
	assert.Equal(t, 10, prefs.MaxDailyActions)
	assert.Equal(t, 5, prefs.MaxPendingSuggestions)
}

func TestCanExecute_ProactiveDisabled(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  false,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	action := ProactiveAction{
		ID:          "test-1",
		Type:        ActionRead,
		Description: "Test action",
		Impact:      ImpactLow,
		CreatedAt:   time.Now(),
	}

	allowed, reason, err := svc.CanExecute(context.Background(), action)
	require.NoError(t, err)
	assert.False(t, allowed)
	assert.Contains(t, reason, "disabled")
}

func TestCanExecute_ForbiddenAction(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	action := ProactiveAction{
		ID:          "test-1",
		Type:        ActionDelete, // This is in ForbiddenActions
		Description: "Delete action",
		Impact:      ImpactLow,
		CreatedAt:   time.Now(),
	}

	allowed, reason, err := svc.CanExecute(context.Background(), action)
	require.NoError(t, err)
	assert.False(t, allowed)
	assert.Contains(t, reason, "forbidden")
}

func TestCanExecute_NotInAllowedList(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	// Update prefs to have a specific allowed list
	prefs := ProactivePreferences{
		AllowedActions:   []ActionType{ActionRead},
		ForbiddenActions: []ActionType{},
	}
	err := svc.UpdatePreferences(context.Background(), prefs)
	require.NoError(t, err)

	action := ProactiveAction{
		ID:          "test-1",
		Type:        ActionNotify, // Not in allowed list
		Description: "Notify action",
		Impact:      ImpactLow,
		CreatedAt:   time.Now(),
	}

	allowed, reason, err := svc.CanExecute(context.Background(), action)
	require.NoError(t, err)
	assert.False(t, allowed)
	assert.Contains(t, reason, "not in the allowed list")
}

func TestCanExecute_BudgetLimitReached(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 2, // Very low limit for testing
	}
	svc := NewService(cfg)
	gs := svc.(*guardrailService)

	// Clear active hours so we're not restricted by time
	gs.mu.Lock()
	gs.prefs.ActiveHours = []TimeRange{}
	gs.mu.Unlock()

	action := ProactiveAction{
		ID:          "test-1",
		Type:        ActionRead,
		Description: "Test action",
		Impact:      ImpactLow,
		CreatedAt:   time.Now(),
	}

	// Consume the budget
	err := svc.ConsumeAction(context.Background(), action)
	require.NoError(t, err)

	err = svc.ConsumeAction(context.Background(), action)
	require.NoError(t, err)

	// Try to execute a third time
	allowed, reason, err := svc.CanExecute(context.Background(), action)
	require.NoError(t, err)
	assert.False(t, allowed)
	assert.Contains(t, reason, "budget limit reached")
}

func TestCanExecute_Approved(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)
	gs := svc.(*guardrailService)

	// Clear active hours so we're not restricted by time
	gs.mu.Lock()
	gs.prefs.ActiveHours = []TimeRange{}
	gs.mu.Unlock()

	action := ProactiveAction{
		ID:          "test-1",
		Type:        ActionRead,
		Description: "Test action",
		Impact:      ImpactLow,
		CreatedAt:   time.Now(),
	}

	allowed, reason, err := svc.CanExecute(context.Background(), action)
	require.NoError(t, err)
	assert.True(t, allowed)
	assert.Equal(t, "approved", reason)
}

func TestGetActionBudget(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	budget, err := svc.GetActionBudget(context.Background(), ActionRead)
	require.NoError(t, err)
	assert.Equal(t, ActionRead, budget.ActionType)
	assert.Equal(t, 10, budget.Limit)
	assert.Equal(t, 0, budget.Used)
}

func TestConsumeAction(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	action := ProactiveAction{
		ID:          "test-1",
		Type:        ActionRead,
		Description: "Test action",
		Impact:      ImpactLow,
		CreatedAt:   time.Now(),
	}

	// Consume should succeed
	err := svc.ConsumeAction(context.Background(), action)
	require.NoError(t, err)

	// Check budget was updated
	budget, err := svc.GetActionBudget(context.Background(), ActionRead)
	require.NoError(t, err)
	assert.Equal(t, 1, budget.Used)
}

func TestConsumeAction_OverLimit(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 1,
	}
	svc := NewService(cfg)

	action := ProactiveAction{
		ID:          "test-1",
		Type:        ActionRead,
		Description: "Test action",
		Impact:      ImpactLow,
		CreatedAt:   time.Now(),
	}

	// First consume should succeed
	err := svc.ConsumeAction(context.Background(), action)
	require.NoError(t, err)

	// Second consume should fail
	err = svc.ConsumeAction(context.Background(), action)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "budget limit exceeded")
}

func TestGetUserPreferences(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	prefs, err := svc.GetUserPreferences(context.Background())
	require.NoError(t, err)
	assert.Contains(t, prefs.AllowedActions, ActionRead)
}

func TestUpdatePreferences(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	newPrefs := ProactivePreferences{
		AllowedActions:        []ActionType{ActionRead, ActionNotify},
		ForbiddenActions:      []ActionType{ActionDelete},
		NotificationLevel:     NotifyAll,
		NotifyChannels:        []NotifyChannel{ChannelTerminal},
		MaxDailyActions:       20,
		MaxPendingSuggestions: 10,
		QuietHours:            []TimeRange{},
		ActiveHours: []TimeRange{
			{Start: "08:00", End: "20:00", Days: []int{1, 2, 3, 4, 5}},
		},
	}

	err := svc.UpdatePreferences(context.Background(), newPrefs)
	require.NoError(t, err)

	updated, err := svc.GetUserPreferences(context.Background())
	require.NoError(t, err)
	assert.Equal(t, NotifyAll, updated.NotificationLevel)
	assert.Equal(t, 20, updated.MaxDailyActions)
	assert.Equal(t, "08:00", updated.ActiveHours[0].Start)
}

func TestUpdatePreferences_InvalidMaxDailyActions(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	invalidPrefs := ProactivePreferences{
		MaxDailyActions: -1,
	}

	err := svc.UpdatePreferences(context.Background(), invalidPrefs)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cannot be negative")
}

func TestUpdatePreferences_InvalidTimeRange(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	invalidPrefs := ProactivePreferences{
		QuietHours: []TimeRange{
			{Start: "invalid", End: "18:00", Days: []int{1}},
		},
	}

	err := svc.UpdatePreferences(context.Background(), invalidPrefs)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid quiet hours")
}

func TestLogAction(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	action := ProactiveAction{
		ID:          "test-1",
		Type:        ActionRead,
		Description: "Test action",
		Impact:      ImpactLow,
		CreatedAt:   time.Now(),
	}

	err := svc.LogAction(context.Background(), action, "approved")
	require.NoError(t, err)

	log, err := svc.GetAuditLog(context.Background(), AuditFilter{})
	require.NoError(t, err)
	assert.Len(t, log, 1)
	assert.Equal(t, "approved", log[0].Decision)
}

func TestGetAuditLog_FilterByActionType(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	// Log different action types
	action1 := ProactiveAction{ID: "1", Type: ActionRead, Impact: ImpactLow, CreatedAt: time.Now()}
	action2 := ProactiveAction{ID: "2", Type: ActionNotify, Impact: ImpactLow, CreatedAt: time.Now()}
	action3 := ProactiveAction{ID: "3", Type: ActionRead, Impact: ImpactLow, CreatedAt: time.Now()}

	svc.LogAction(context.Background(), action1, "approved")
	svc.LogAction(context.Background(), action2, "approved")
	svc.LogAction(context.Background(), action3, "approved")

	// Filter by ActionRead
	log, err := svc.GetAuditLog(context.Background(), AuditFilter{ActionType: ActionRead})
	require.NoError(t, err)
	assert.Len(t, log, 2)
	for _, entry := range log {
		assert.Equal(t, ActionRead, entry.Action.Type)
	}
}

func TestGetAuditLog_FilterByDecision(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	action := ProactiveAction{ID: "1", Type: ActionRead, Impact: ImpactLow, CreatedAt: time.Now()}

	svc.LogAction(context.Background(), action, "approved")
	svc.LogAction(context.Background(), action, "denied")
	svc.LogAction(context.Background(), action, "approved")

	log, err := svc.GetAuditLog(context.Background(), AuditFilter{Decision: "denied"})
	require.NoError(t, err)
	assert.Len(t, log, 1)
	assert.Equal(t, "denied", log[0].Decision)
}

func TestGetAuditLog_WithTimeRange(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)

	action := ProactiveAction{ID: "1", Type: ActionRead, Impact: ImpactLow, CreatedAt: time.Now()}
	svc.LogAction(context.Background(), action, "approved")

	// Filter with time range
	now := time.Now()
	startTime := now.Add(-1 * time.Hour)
	endTime := now.Add(1 * time.Hour)

	log, err := svc.GetAuditLog(context.Background(), AuditFilter{
		StartTime: &startTime,
		EndTime:   &endTime,
	})
	require.NoError(t, err)
	assert.Len(t, log, 1)
}

func TestGetAuditLog_Limit(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 100, // High limit so we can log many actions
	}
	svc := NewService(cfg)

	action := ProactiveAction{ID: "1", Type: ActionRead, Impact: ImpactLow, CreatedAt: time.Now()}

	// Log 5 actions
	for i := 0; i < 5; i++ {
		svc.LogAction(context.Background(), action, "approved")
	}

	// Request only 3
	log, err := svc.GetAuditLog(context.Background(), AuditFilter{Limit: 3})
	require.NoError(t, err)
	assert.Len(t, log, 3)
}

func TestIsQuietHours(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)
	gs := svc.(*guardrailService)

	// Set quiet hours to 00:00-23:59 every day (always quiet)
	gs.mu.Lock()
	gs.prefs.QuietHours = []TimeRange{
		{Start: "00:00", End: "23:59", Days: []int{0, 1, 2, 3, 4, 5, 6}},
	}
	gs.mu.Unlock()

	allowed, reason, err := svc.CanExecute(context.Background(), ProactiveAction{
		ID:        "test",
		Type:      ActionRead,
		Impact:    ImpactLow,
		CreatedAt: time.Now(),
	})
	require.NoError(t, err)
	assert.False(t, allowed)
	assert.Contains(t, reason, "quiet hours")
}

func TestIsActiveHours(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)
	gs := svc.(*guardrailService)

	// Set active hours to 00:00-00:01 (very narrow window that likely won't include now)
	now := time.Now()
	weekday := int(now.Weekday())

	gs.mu.Lock()
	gs.prefs.ActiveHours = []TimeRange{
		{Start: "00:00", End: "00:01", Days: []int{weekday}},
	}
	gs.mu.Unlock()

	allowed, reason, err := svc.CanExecute(context.Background(), ProactiveAction{
		ID:        "test",
		Type:      ActionRead,
		Impact:    ImpactLow,
		CreatedAt: time.Now(),
	})
	require.NoError(t, err)
	assert.False(t, allowed)
	assert.Contains(t, reason, "outside active hours")
}

func TestValidateTimeRange(t *testing.T) {
	tests := []struct {
		name    string
		tr      TimeRange
		wantErr bool
	}{
		{
			name:    "valid time range",
			tr:      TimeRange{Start: "09:00", End: "18:00", Days: []int{1, 2, 3}},
			wantErr: false,
		},
		{
			name:    "empty start",
			tr:      TimeRange{Start: "", End: "18:00", Days: []int{1}},
			wantErr: true,
		},
		{
			name:    "invalid format",
			tr:      TimeRange{Start: "9:00", End: "18:00", Days: []int{1}},
			wantErr: true,
		},
		{
			name:    "invalid day",
			tr:      TimeRange{Start: "09:00", End: "18:00", Days: []int{7}},
			wantErr: true,
		},
		{
			name:    "no days specified",
			tr:      TimeRange{Start: "09:00", End: "18:00", Days: []int{}},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateTimeRange(tt.tr)
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestShouldAutoApprove(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)
	gs := svc.(*guardrailService)

	// Clear active hours and add auto-approve rule
	gs.mu.Lock()
	gs.prefs.ActiveHours = []TimeRange{}
	gs.prefs.AutoApprovePatterns = []AutoApproveRule{
		{ID: "1", ActionType: ActionRead, MaxPerDay: 5, UsedToday: 0},
	}
	gs.mu.Unlock()

	// Low impact should be auto-approved if rule matches
	lowImpactAction := ProactiveAction{
		ID:        "test",
		Type:      ActionRead,
		Impact:    ImpactLow,
		CreatedAt: time.Now(),
	}

	allowed, reason, err := svc.CanExecute(context.Background(), lowImpactAction)
	require.NoError(t, err)
	assert.True(t, allowed)
	assert.Contains(t, reason, "auto-approved")
}

func TestShouldAutoApprove_HighImpactNotApproved(t *testing.T) {
	cfg := config.GuardrailsConfig{
		AllowProactive:  true,
		MaxDailyActions: 10,
	}
	svc := NewService(cfg)
	gs := svc.(*guardrailService)

	// Clear active hours so we're not restricted by time
	gs.mu.Lock()
	gs.prefs.ActiveHours = []TimeRange{}
	gs.mu.Unlock()

	// High impact action should NOT be auto-approved even if it matches a rule
	highImpactAction := ProactiveAction{
		ID:        "test",
		Type:      ActionRead,
		Impact:    ImpactHigh,
		CreatedAt: time.Now(),
	}

	allowed, reason, err := svc.CanExecute(context.Background(), highImpactAction)
	require.NoError(t, err)
	assert.True(t, allowed)
	assert.Equal(t, "approved", reason)
	assert.NotContains(t, reason, "auto-approved")
}
