// Package analysis provides self-analysis capabilities for ARIA,
// including performance reporting, pattern analysis, and improvement suggestions.
//
// This package implements the self-analysis interfaces defined in Blueprint Section 6.1.
package analysis

import (
	"context"
	"time"

	"github.com/fulvian/aria/internal/aria/agency"
	"github.com/fulvian/aria/internal/aria/scheduler"
	"github.com/fulvian/aria/internal/aria/skill"
)

// TimeRange represents a time range for analysis.
type TimeRange struct {
	Start time.Time
	End   time.Time
}

// PerformanceReport contains overall performance analysis.
type PerformanceReport struct {
	Period        TimeRange
	TotalTasks    int64
	SuccessRate   float64
	AverageTimeMs int64

	ByAgency map[agency.AgencyName]AgencyMetrics
	ByAgent  map[string]AgentMetrics
	BySkill  map[skill.SkillName]SkillMetrics

	Trends    []Trend
	Anomalies []Anomaly
}

// AgencyMetrics represents metrics for a specific agency.
type AgencyMetrics struct {
	TotalTasks    int64
	SuccessRate   float64
	AverageTimeMs int64
	TasksByStatus map[scheduler.TaskStatus]int64
}

// AgentMetrics represents metrics for a specific agent.
type AgentMetrics struct {
	TotalTasks    int64
	SuccessRate   float64
	AverageTimeMs int64
	TasksByStatus map[scheduler.TaskStatus]int64
}

// SkillMetrics represents metrics for a specific skill.
type SkillMetrics struct {
	TotalCalls     int64
	SuccessRate    float64
	AverageTimeMs  int64
	FailureReasons map[string]int64
}

// Trend represents a detected trend.
type Trend struct {
	Type        string // "improving", "declining", "stable"
	Description string
	Metric      string
	Change      float64 // Percentage change
}

// Anomaly represents a detected anomaly.
type Anomaly struct {
	Type        string // "performance_drop", "error_spike", "unusual_pattern"
	Description string
	Metric      string
	Value       float64
	Threshold   float64
	DetectedAt  time.Time
}

// PatternReport contains pattern analysis results.
type PatternReport struct {
	RecurringTasks   []RecurringPattern
	CommonWorkflows  []WorkflowPattern
	UserPreferences  []PreferencePattern
	OptimizationOpps []Optimization
}

// RecurringPattern represents a pattern of recurring tasks.
type RecurringPattern struct {
	TaskType    string
	Frequency   string
	AvgDuration int64
	SuccessRate float64
}

// WorkflowPattern represents a common workflow pattern.
type WorkflowPattern struct {
	Name        string
	Steps       []string
	Frequency   int
	SuccessRate float64
}

// PreferencePattern represents an inferred user preference.
type PreferencePattern struct {
	Type        string // "timing", "quality", "communication"
	Description string
	Confidence  float64
	Evidence    []string
}

// Optimization represents an optimization opportunity.
type Optimization struct {
	Type        string // "automation", "parallelization", "caching"
	Description string
	Impact      string // "high", "medium", "low"
	Effort      string // "high", "medium", "low"
}

// FailureReport contains failure analysis.
type FailureReport struct {
	TotalFailures int64
	FailureRate   float64
	CommonReasons map[string]int64
	FailedTasks   []FailedTaskInfo
	RootCauses    []RootCause
}

// FailedTaskInfo contains info about a failed task.
type FailedTaskInfo struct {
	TaskID     scheduler.TaskID
	TaskName   string
	FailedAt   time.Time
	Reason     string
	RetryCount int
}

// RootCause represents an identified root cause of failures.
type RootCause struct {
	Description   string
	AffectedTasks int64
	Symptoms      []string
	SuggestedFix  string
}

// Improvement represents a suggested improvement.
type Improvement struct {
	ID          string
	Type        string // "process", "configuration", "skill"
	Description string
	Impact      string // "high", "medium", "low"
	Confidence  float64
	AutoApply   bool
	AppliedAt   *time.Time
	CreatedAt   time.Time
}

// Insight represents a generated insight.
type Insight struct {
	ID          string
	Category    string // "performance", "pattern", "recommendation"
	Title       string
	Description string
	Evidence    []string
	CreatedAt   time.Time
}

// SelfAnalysisService provides self-analysis capabilities.
//
// Reference: Blueprint Section 6.1
type SelfAnalysisService interface {
	// RunPeriodicAnalysis runs scheduled self-analysis
	RunPeriodicAnalysis(ctx context.Context) error

	// AnalyzePerformance analyzes task performance
	AnalyzePerformance(ctx context.Context, timeRange TimeRange) (PerformanceReport, error)

	// AnalyzePatterns analyzes patterns in behavior
	AnalyzePatterns(ctx context.Context) (PatternReport, error)

	// AnalyzeFailures analyzes failure patterns
	AnalyzeFailures(ctx context.Context) (FailureReport, error)

	// GenerateImprovements generates improvement suggestions
	GenerateImprovements(ctx context.Context) ([]Improvement, error)

	// ApplyInsights applies selected improvements
	ApplyInsights(ctx context.Context, insights []Improvement) error
}
