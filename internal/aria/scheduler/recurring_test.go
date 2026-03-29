package scheduler

import (
	"testing"
	"time"
)

func TestParseInterval(t *testing.T) {
	tests := []struct {
		name     string
		expr     string
		expected time.Duration
		wantErr  bool
	}{
		{
			name:     "5 minutes",
			expr:     "every:5m",
			expected: 5 * time.Minute,
			wantErr:  false,
		},
		{
			name:     "1 hour",
			expr:     "every:1h",
			expected: 1 * time.Hour,
			wantErr:  false,
		},
		{
			name:     "30 seconds",
			expr:     "every:30s",
			expected: 30 * time.Second,
			wantErr:  false,
		},
		{
			name:     "1 day",
			expr:     "every:1d",
			expected: 24 * time.Hour,
			wantErr:  false,
		},
		{
			name:     "with spaces",
			expr:     "  every:5m  ",
			expected: 5 * time.Minute,
			wantErr:  false,
		},
		{
			name:    "invalid format - missing colon",
			expr:    "every5m",
			wantErr: true,
		},
		{
			name:    "invalid format - no unit",
			expr:    "every:5",
			wantErr: true,
		},
		{
			name:    "invalid unit",
			expr:    "every:5x",
			wantErr: true,
		},
		{
			name:    "zero value",
			expr:    "every:0m",
			wantErr: true,
		},
		{
			name:    "negative value",
			expr:    "every:-5m",
			wantErr: true,
		},
		{
			name:    "empty string",
			expr:    "",
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ParseInterval(tt.expr)
			if (err != nil) != tt.wantErr {
				t.Errorf("ParseInterval() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if !tt.wantErr && got != tt.expected {
				t.Errorf("ParseInterval() = %v, expected %v", got, tt.expected)
			}
		})
	}
}

func TestParseCron(t *testing.T) {
	tests := []struct {
		name      string
		expr      string
		wantErr   bool
		checkNext func(t *testing.T, nextRun time.Time)
	}{
		{
			name:    "every hour at minute 0",
			expr:    "0 * * * *",
			wantErr: false,
			checkNext: func(t *testing.T, nextRun time.Time) {
				if nextRun.Minute() != 0 {
					t.Errorf("expected minute 0, got %d", nextRun.Minute())
				}
			},
		},
		{
			name:    "every weekday at 9am",
			expr:    "0 9 * * 1-5",
			wantErr: false,
			checkNext: func(t *testing.T, nextRun time.Time) {
				if nextRun.Hour() != 9 {
					t.Errorf("expected hour 9, got %d", nextRun.Hour())
				}
				if nextRun.Minute() != 0 {
					t.Errorf("expected minute 0, got %d", nextRun.Minute())
				}
				// Weekday should be 1-5 (Monday-Friday)
				if nextRun.Weekday() == time.Saturday || nextRun.Weekday() == time.Sunday {
					t.Errorf("expected weekday 1-5, got %d", nextRun.Weekday())
				}
			},
		},
		{
			name:    "every 15 minutes",
			expr:    "*/15 * * * *",
			wantErr: false,
			checkNext: func(t *testing.T, nextRun time.Time) {
				if nextRun.Minute()%15 != 0 {
					t.Errorf("expected minute divisible by 15, got %d", nextRun.Minute())
				}
			},
		},
		{
			name:    "every minute",
			expr:    "* * * * *",
			wantErr: false,
		},
		{
			name:    "specific minute",
			expr:    "30 * * * *",
			wantErr: false,
			checkNext: func(t *testing.T, nextRun time.Time) {
				if nextRun.Minute() != 30 {
					t.Errorf("expected minute 30, got %d", nextRun.Minute())
				}
			},
		},
		{
			name:    "specific hour and minute",
			expr:    "30 14 * * *",
			wantErr: false,
			checkNext: func(t *testing.T, nextRun time.Time) {
				if nextRun.Hour() != 14 {
					t.Errorf("expected hour 14, got %d", nextRun.Hour())
				}
				if nextRun.Minute() != 30 {
					t.Errorf("expected minute 30, got %d", nextRun.Minute())
				}
			},
		},
		{
			name:    "specific day of month",
			expr:    "0 0 15 * *",
			wantErr: false,
			checkNext: func(t *testing.T, nextRun time.Time) {
				if nextRun.Day() != 15 {
					t.Errorf("expected day 15, got %d", nextRun.Day())
				}
			},
		},
		{
			name:    "specific month",
			expr:    "0 0 1 6 *",
			wantErr: false,
			checkNext: func(t *testing.T, nextRun time.Time) {
				if nextRun.Month() != time.June {
					t.Errorf("expected month June, got %s", nextRun.Month())
				}
			},
		},
		{
			name:    "weekday 0 (Sunday)",
			expr:    "0 0 * * 0",
			wantErr: false,
		},
		{
			name:    "weekday 6 (Saturday)",
			expr:    "0 0 * * 6",
			wantErr: false,
		},
		{
			name:    "with spaces",
			expr:    "  0 * * * *  ",
			wantErr: false,
		},
		{
			name:    "too few fields",
			expr:    "0 * * *",
			wantErr: true,
		},
		{
			name:    "too many fields",
			expr:    "0 * * * * *",
			wantErr: true,
		},
		{
			name:    "invalid minute",
			expr:    "60 * * * *",
			wantErr: true,
		},
		{
			name:    "invalid hour",
			expr:    "0 25 * * *",
			wantErr: true,
		},
		{
			name:    "invalid day",
			expr:    "0 0 32 * *",
			wantErr: true,
		},
		{
			name:    "invalid month",
			expr:    "0 0 * 13 *",
			wantErr: true,
		},
		{
			name:    "invalid weekday",
			expr:    "0 0 * * 7",
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			nextRun, err := ParseCron(tt.expr)
			if (err != nil) != tt.wantErr {
				t.Errorf("ParseCron() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if !tt.wantErr && tt.checkNext != nil {
				tt.checkNext(t, nextRun)
			}
		})
	}
}

func TestValidateSchedule(t *testing.T) {
	tests := []struct {
		name     string
		schedule Schedule
		wantErr  bool
	}{
		{
			name: "valid cron schedule",
			schedule: Schedule{
				Type:       ScheduleCron,
				Expression: "0 * * * *",
			},
			wantErr: false,
		},
		{
			name: "valid interval schedule",
			schedule: Schedule{
				Type:       ScheduleInterval,
				Expression: "every:5m",
			},
			wantErr: false,
		},
		{
			name: "valid specific times schedule",
			schedule: Schedule{
				Type:       ScheduleSpecific,
				Expression: `["2024-01-01T10:00:00Z"]`,
			},
			wantErr: false,
		},
		{
			name: "empty schedule type",
			schedule: Schedule{
				Type:       "",
				Expression: "every:5m",
			},
			wantErr: true,
		},
		{
			name: "empty cron expression",
			schedule: Schedule{
				Type:       ScheduleCron,
				Expression: "",
			},
			wantErr: true,
		},
		{
			name: "empty interval expression",
			schedule: Schedule{
				Type:       ScheduleInterval,
				Expression: "",
			},
			wantErr: true,
		},
		{
			name: "invalid cron expression",
			schedule: Schedule{
				Type:       ScheduleCron,
				Expression: "invalid",
			},
			wantErr: true,
		},
		{
			name: "invalid interval expression",
			schedule: Schedule{
				Type:       ScheduleInterval,
				Expression: "invalid",
			},
			wantErr: true,
		},
		{
			name: "unknown schedule type",
			schedule: Schedule{
				Type:       "unknown",
				Expression: "every:5m",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateSchedule(tt.schedule)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateSchedule() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestGenerateIdempotencyKey(t *testing.T) {
	key1 := generateIdempotencyKey("parent-123", time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC))
	key2 := generateIdempotencyKey("parent-123", time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC))
	key3 := generateIdempotencyKey("parent-123", time.Date(2024, 1, 1, 11, 0, 0, 0, time.UTC))
	key4 := generateIdempotencyKey("parent-456", time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC))

	// Same inputs should produce same key
	if key1 != key2 {
		t.Errorf("same inputs should produce same key: key1=%s, key2=%s", key1, key2)
	}

	// Different scheduled time should produce different key
	if key1 == key3 {
		t.Errorf("different scheduled time should produce different key")
	}

	// Different parent ID should produce different key
	if key1 == key4 {
		t.Errorf("different parent ID should produce different key")
	}

	// Key should be a valid MD5 hex string (32 characters)
	if len(key1) != 32 {
		t.Errorf("key should be 32 characters, got %d", len(key1))
	}
}

func TestMatchesSingleField(t *testing.T) {
	tests := []struct {
		field    string
		value    int
		min      int
		max      int
		expected bool
	}{
		// Wildcard
		{"*", 5, 0, 59, true},
		{"*", 30, 0, 23, true},

		// Step
		{"*/15", 0, 0, 59, true},
		{"*/15", 15, 0, 59, true},
		{"*/15", 30, 0, 59, true},
		{"*/15", 45, 0, 59, true},
		{"*/15", 5, 0, 59, false},

		// Single value
		{"30", 30, 0, 59, true},
		{"30", 29, 0, 59, false},

		// Range
		{"1-5", 1, 1, 5, true},
		{"1-5", 3, 1, 5, true},
		{"1-5", 5, 1, 5, true},
		{"1-5", 0, 1, 5, false},
		{"1-5", 6, 1, 5, false},

		// Comma-separated
		{"1,3,5", 1, 0, 59, true},
		{"1,3,5", 3, 0, 59, true},
		{"1,3,5", 5, 0, 59, true},
		{"1,3,5", 2, 0, 59, false},
	}

	for _, tt := range tests {
		t.Run(tt.field, func(t *testing.T) {
			result := matchesSingleField(tt.field, tt.value, tt.min, tt.max)
			if result != tt.expected {
				t.Errorf("matchesSingleField(%q, %d, %d, %d) = %v, expected %v",
					tt.field, tt.value, tt.min, tt.max, result, tt.expected)
			}
		})
	}
}

func TestIterateCronMatches(t *testing.T) {
	planner := &RecurringPlanner{
		lookAhead: 2 * time.Hour,
	}

	// Test */15 * * * * (every 15 minutes)
	now := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	windowEnd := now.Add(2 * time.Hour)

	runs := planner.iterateCronMatches("*/15 * * * *", now, windowEnd)

	// Should have runs at 10:15, 10:30, 10:45, 11:00, 11:15, 11:30, 11:45
	expectedCount := 7
	if len(runs) != expectedCount {
		t.Errorf("expected %d runs, got %d", expectedCount, len(runs))
	}

	// Verify first run is at 10:15
	if len(runs) > 0 && runs[0].Minute() != 15 {
		t.Errorf("first run should be at minute 15, got %d", runs[0].Minute())
	}
}
