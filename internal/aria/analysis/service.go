package analysis

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/fulvian/aria/internal/aria/agency"
	"github.com/fulvian/aria/internal/aria/scheduler"
	"github.com/fulvian/aria/internal/aria/skill"
	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/logging"
)

// selfAnalysisService implements SelfAnalysisService.
type selfAnalysisService struct {
	db       db.Querier
	stopCh   chan struct{}
	interval time.Duration
}

// NewService creates a new SelfAnalysisService instance.
func NewService(q db.Querier) SelfAnalysisService {
	return &selfAnalysisService{
		db:       q,
		stopCh:   make(chan struct{}),
		interval: 1 * time.Hour, // Default interval for periodic analysis
	}
}

// RunPeriodicAnalysis runs scheduled self-analysis using a simple ticker.
// This is an MVP implementation - FASE 3 will add proper scheduler integration.
func (s *selfAnalysisService) RunPeriodicAnalysis(ctx context.Context) error {
	ticker := time.NewTicker(s.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-s.stopCh:
			return nil
		case <-ticker.C:
			if err := s.runAnalysis(ctx); err != nil {
				logging.Error("Periodic analysis failed", "error", err)
			}
		}
	}
}

// Stop stops the periodic analysis loop.
func (s *selfAnalysisService) Stop() {
	close(s.stopCh)
}

// runAnalysis performs a complete analysis cycle.
func (s *selfAnalysisService) runAnalysis(ctx context.Context) error {
	now := time.Now()
	timeRange := TimeRange{
		Start: now.Add(-s.interval),
		End:   now,
	}

	// Run all analysis types
	if _, err := s.AnalyzePerformance(ctx, timeRange); err != nil {
		return fmt.Errorf("performance analysis failed: %w", err)
	}

	if _, err := s.AnalyzePatterns(ctx); err != nil {
		return fmt.Errorf("pattern analysis failed: %w", err)
	}

	if _, err := s.AnalyzeFailures(ctx); err != nil {
		return fmt.Errorf("failure analysis failed: %w", err)
	}

	return nil
}

// AnalyzePerformance analyzes task performance for the given time range.
func (s *selfAnalysisService) AnalyzePerformance(ctx context.Context, timeRange TimeRange) (PerformanceReport, error) {
	report := PerformanceReport{
		Period:    timeRange,
		ByAgency:  make(map[agency.AgencyName]AgencyMetrics),
		ByAgent:   make(map[string]AgentMetrics),
		BySkill:   make(map[skill.SkillName]SkillMetrics),
		Trends:    []Trend{},
		Anomalies: []Anomaly{},
	}

	// Get tasks - fetch more for time range filtering
	tasks, err := s.db.ListTasks(ctx, db.ListTasksParams{
		Limit:  1000, // Increased for time range filtering
		Offset: 0,
	})
	if err != nil {
		return report, fmt.Errorf("failed to list tasks: %w", err)
	}

	// Filter tasks by time range
	filteredTasks := filterTasksByTimeRange(tasks, timeRange)

	// Calculate overall metrics
	var totalDurationMs int64
	var completedTasks int64

	for _, task := range filteredTasks {
		if task.Status == "completed" {
			completedTasks++
			if task.StartedAt.Valid && task.CompletedAt.Valid {
				duration := task.CompletedAt.Int64 - task.StartedAt.Int64
				totalDurationMs += duration * 1000 // Convert to ms
			}
		}
	}

	report.TotalTasks = int64(len(filteredTasks))
	if len(filteredTasks) > 0 {
		report.SuccessRate = float64(completedTasks) / float64(len(filteredTasks))
	}
	if completedTasks > 0 {
		report.AverageTimeMs = totalDurationMs / completedTasks
	}

	// Aggregate by agency (use filteredTasks)
	agencyStats := make(map[string]struct {
		total    int64
		success  int64
		duration int64
	})

	for _, task := range filteredTasks {
		if !task.Agency.Valid || task.Agency.String == "" {
			continue
		}
		agencyID := task.Agency.String
		stats := agencyStats[agencyID]
		stats.total++

		if task.Status == "completed" {
			stats.success++
			if task.StartedAt.Valid && task.CompletedAt.Valid {
				stats.duration += task.CompletedAt.Int64 - task.StartedAt.Int64
			}
		}

		agencyStats[agencyID] = stats
	}

	for agencyID, stats := range agencyStats {
		rate := 0.0
		if stats.total > 0 {
			rate = float64(stats.success) / float64(stats.total)
		}
		avgDuration := int64(0)
		if stats.success > 0 {
			avgDuration = (stats.duration * 1000) / stats.success
		}

		report.ByAgency[agency.AgencyName(agencyID)] = AgencyMetrics{
			TotalTasks:    stats.total,
			SuccessRate:   rate,
			AverageTimeMs: avgDuration,
			TasksByStatus: map[scheduler.TaskStatus]int64{
				"completed": stats.success,
				"failed":    stats.total - stats.success,
			},
		}
	}

	return report, nil
}

// filterTasksByTimeRange filters tasks that fall within the time range.
func filterTasksByTimeRange(tasks []db.Task, timeRange TimeRange) []db.Task {
	// If no time range specified, return all tasks (backward compatibility)
	if timeRange.Start.IsZero() && timeRange.End.IsZero() {
		return tasks
	}

	var result []db.Task
	for _, task := range tasks {
		// Use created_at as the timestamp for filtering
		// CreatedAt is int64 (Unix timestamp), 0 means not set
		// Tasks with CreatedAt == 0 are included only if no end boundary is set
		// (they're assumed to be recent enough to be included if end is now)
		if task.CreatedAt == 0 {
			// If end boundary is set, exclude tasks without valid timestamp
			if !timeRange.End.IsZero() {
				continue
			}
			// Otherwise include them (only start boundary set, end is unbounded)
			result = append(result, task)
			continue
		}
		taskTime := time.Unix(task.CreatedAt, 0)

		if !timeRange.Start.IsZero() && taskTime.Before(timeRange.Start) {
			continue
		}
		if !timeRange.End.IsZero() && taskTime.After(timeRange.End) {
			continue
		}
		result = append(result, task)
	}
	return result
}

// AnalyzePatterns analyzes patterns in behavior.
func (s *selfAnalysisService) AnalyzePatterns(ctx context.Context) (PatternReport, error) {
	report := PatternReport{
		RecurringTasks:   []RecurringPattern{},
		CommonWorkflows:  []WorkflowPattern{},
		UserPreferences:  []PreferencePattern{},
		OptimizationOpps: []Optimization{},
	}

	// Get recent episodes to identify patterns
	episodes, err := s.db.ListEpisodes(ctx, db.ListEpisodesParams{
		Limit:  100,
		Offset: 0,
	})
	if err != nil {
		return report, fmt.Errorf("failed to list episodes: %w", err)
	}

	// Analyze task type frequency
	taskTypeCount := make(map[string]int)
	taskTypeDuration := make(map[string]int64)
	taskTypeSuccess := make(map[string]int)

	for _, ep := range episodes {
		if ep.Task.Valid && ep.Task.String != "" {
			var task map[string]any
			if err := json.Unmarshal([]byte(ep.Task.String), &task); err == nil {
				if taskType, ok := task["type"].(string); ok {
					taskTypeCount[taskType]++
					if ep.Outcome.Valid && !strings.HasPrefix(ep.Outcome.String, "failure") {
						taskTypeSuccess[taskType]++
					}
				}
			}
		}
	}

	// Convert to recurring patterns (top 5)
	type taskStat struct {
		taskType string
		count    int
	}
	var taskStats []taskStat
	for tt, count := range taskTypeCount {
		taskStats = append(taskStats, taskStat{tt, count})
	}

	// Simple sort by count (bubble sort for small lists)
	for i := 0; i < len(taskStats)-1; i++ {
		for j := i + 1; j < len(taskStats); j++ {
			if taskStats[j].count > taskStats[i].count {
				taskStats[i], taskStats[j] = taskStats[j], taskStats[i]
			}
		}
	}

	for i, ts := range taskStats {
		if i >= 5 {
			break
		}
		success := taskTypeSuccess[ts.taskType]
		rate := 0.0
		if ts.count > 0 {
			rate = float64(success) / float64(ts.count)
		}
		report.RecurringTasks = append(report.RecurringTasks, RecurringPattern{
			TaskType:    ts.taskType,
			Frequency:   fmt.Sprintf("%d times", ts.count),
			AvgDuration: taskTypeDuration[ts.taskType] / int64(maxInt(1, ts.count)),
			SuccessRate: rate,
		})
	}

	// Identify optimization opportunities
	if len(episodes) > 50 {
		report.OptimizationOpps = append(report.OptimizationOpps, Optimization{
			Type:        "caching",
			Description: "Consider caching frequent task results",
			Impact:      "medium",
			Effort:      "low",
		})
	}

	return report, nil
}

// maxInt returns the maximum of two integers.
func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// AnalyzeFailures analyzes failure patterns.
func (s *selfAnalysisService) AnalyzeFailures(ctx context.Context) (FailureReport, error) {
	report := FailureReport{
		CommonReasons: make(map[string]int64),
		FailedTasks:   []FailedTaskInfo{},
		RootCauses:    []RootCause{},
	}

	// Get recent task events to find failures
	events, err := s.db.GetRecentTaskEvents(ctx, 100)
	if err != nil {
		return report, fmt.Errorf("failed to get task events: %w", err)
	}

	// Get failed tasks
	failedTasks, err := s.db.ListTasksByStatus(ctx, db.ListTasksByStatusParams{
		Status: "failed",
		Limit:  50,
		Offset: 0,
	})
	if err != nil {
		return report, fmt.Errorf("failed to list failed tasks: %w", err)
	}

	var totalFailures int64
	for _, task := range failedTasks {
		totalFailures++
		reason := "unknown"
		if task.Error.Valid {
			reason = task.Error.String
		}
		report.CommonReasons[reason]++

		failedAt := time.Now()
		if task.CompletedAt.Valid {
			failedAt = time.Unix(task.CompletedAt.Int64, 0)
		}

		report.FailedTasks = append(report.FailedTasks, FailedTaskInfo{
			TaskID:     scheduler.TaskID(task.ID),
			TaskName:   task.Name,
			FailedAt:   failedAt,
			Reason:     reason,
			RetryCount: 0,
		})
	}

	report.TotalFailures = totalFailures
	if len(events) > 0 {
		report.FailureRate = float64(totalFailures) / float64(len(events))
	}

	// Identify root causes (simple heuristic: most common failure reasons)
	var reasons []struct {
		reason string
		count  int64
	}
	for reason, count := range report.CommonReasons {
		reasons = append(reasons, struct {
			reason string
			count  int64
		}{reason, count})
	}

	// Sort by count
	for i := 0; i < len(reasons)-1; i++ {
		for j := i + 1; j < len(reasons); j++ {
			if reasons[j].count > reasons[i].count {
				reasons[i], reasons[j] = reasons[j], reasons[i]
			}
		}
	}

	// Top 3 root causes
	for i := 0; i < min(3, len(reasons)); i++ {
		if reasons[i].count < 2 {
			continue
		}
		report.RootCauses = append(report.RootCauses, RootCause{
			Description:   fmt.Sprintf("Frequently failing with: %s", reasons[i].reason),
			AffectedTasks: reasons[i].count,
			Symptoms:      []string{reasons[i].reason},
			SuggestedFix:  "Review error handling for this failure type",
		})
	}

	return report, nil
}

// GenerateImprovements generates up to 3 rule-based improvement suggestions.
func (s *selfAnalysisService) GenerateImprovements(ctx context.Context) ([]Improvement, error) {
	var improvements []Improvement

	// Get metrics based on analysis interval
	timeRange := TimeRange{
		Start: time.Now().Add(-s.interval),
		End:   time.Now(),
	}

	report, err := s.AnalyzePerformance(ctx, timeRange)
	if err != nil {
		return improvements, fmt.Errorf("failed to analyze performance: %w", err)
	}

	// Improvement 1: Low success rate
	if report.SuccessRate < 0.7 && report.TotalTasks > 5 {
		improvements = append(improvements, Improvement{
			ID:          uuid.New().String(),
			Type:        "process",
			Description: fmt.Sprintf("Success rate is below 70%% (currently %.1f%%). Consider reviewing task definitions and error handling.", report.SuccessRate*100),
			Impact:      "high",
			Confidence:  0.8,
			AutoApply:   false,
			CreatedAt:   time.Now(),
		})
	}

	// Improvement 2: High average time
	if report.AverageTimeMs > 60000 && report.TotalTasks > 3 { // > 1 minute
		improvements = append(improvements, Improvement{
			ID:          uuid.New().String(),
			Type:        "process",
			Description: fmt.Sprintf("Average task duration is %.1f seconds. Consider optimizing or breaking down long-running tasks.", float64(report.AverageTimeMs)/1000),
			Impact:      "medium",
			Confidence:  0.7,
			AutoApply:   false,
			CreatedAt:   time.Now(),
		})
	}

	// Improvement 3: Check failure patterns
	failureReport, err := s.AnalyzeFailures(ctx)
	if err == nil && len(failureReport.RootCauses) > 0 {
		improvements = append(improvements, Improvement{
			ID:          uuid.New().String(),
			Type:        "skill",
			Description: fmt.Sprintf("Identified %d recurring failure patterns. Addressing these could improve success rate.", len(failureReport.RootCauses)),
			Impact:      "high",
			Confidence:  0.85,
			AutoApply:   false,
			CreatedAt:   time.Now(),
		})
	}

	// Limit to 3 improvements
	if len(improvements) > 3 {
		improvements = improvements[:3]
	}

	return improvements, nil
}

// ApplyInsights applies selected improvements.
// MVP: Only applies non-destructive, easily reversible improvements.
func (s *selfAnalysisService) ApplyInsights(ctx context.Context, insights []Improvement) error {
	for _, insight := range insights {
		// Only auto-apply if explicitly allowed and marked as safe
		if !insight.AutoApply {
			continue
		}

		// MVP: Only apply optimizations (non-destructive)
		if insight.Type == "process" && insight.Impact == "low" {
			logging.Info("Applying insight", "id", insight.ID, "description", insight.Description)

			// Record the application
			now := time.Now()
			insight.AppliedAt = &now
		}
		// Don't apply skill improvements automatically in MVP
	}

	return nil
}

// PersistInsight stores an insight as a fact in semantic memory.
func (s *selfAnalysisService) PersistInsight(ctx context.Context, insight Insight) error {
	// Store insight as a fact with special domain
	fact := Fact{
		ID:         insight.ID,
		Domain:     "insight",
		Category:   insight.Category,
		Content:    fmt.Sprintf("[%s] %s: %s", insight.Category, insight.Title, insight.Description),
		Source:     "self_analysis",
		Confidence: 0.9,
	}

	// Store fact via the DB directly since analysis doesn't have memory service reference
	params := db.CreateFactParams{
		ID:         fact.ID,
		Domain:     fact.Domain,
		Category:   toNullString(fact.Category),
		Content:    fact.Content,
		Source:     toNullString(fact.Source),
		Confidence: fact.Confidence,
	}

	_, err := s.db.CreateFact(ctx, params)
	if err != nil {
		return fmt.Errorf("failed to persist insight: %w", err)
	}
	return nil
}

// Fact represents a fact stored in semantic memory.
type Fact struct {
	ID         string
	Domain     string
	Category   string
	Content    string
	Source     string
	Confidence float64
}

// toNullString converts a string to sql.NullString.
func toNullString(s string) sql.NullString {
	if s == "" {
		return sql.NullString{}
	}
	return sql.NullString{String: s, Valid: true}
}
