package memory

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/logging"
)

// memoryService implements MemoryService using sync.Map for working memory
// and the existing sqlc-generated queries for persistent storage.
type memoryService struct {
	db      db.Querier
	working sync.Map // map[string]Context - session context cache
	metrics sync.Map // map[string]*Metrics - per-session metrics
	ttl     time.Duration
	gcTick  time.Duration
}

// NewService creates a new MemoryService instance with TTL for working memory persistence.
func NewService(q db.Querier, ttl time.Duration) MemoryService {
	svc := &memoryService{
		db:     q,
		ttl:    ttl,
		gcTick: 5 * time.Minute,
	}
	// Start GC goroutine for expired context cleanup
	go svc.runGC()
	return svc
}

// GetContext retrieves the working memory context for a session.
// First checks in-memory cache, then restores from DB if not found.
func (s *memoryService) GetContext(ctx context.Context, sessionID string) (Context, error) {
	if val, ok := s.working.Load(sessionID); ok {
		return val.(Context), nil
	}
	// Try to restore from database persistence
	context, err := s.RestoreContext(ctx, sessionID)
	if err != nil {
		return Context{}, fmt.Errorf("failed to restore context: %w", err)
	}
	// Check if context was found (SessionID is the primary identifier)
	if context.SessionID != "" {
		// Populate in-memory cache for fast access
		s.working.Store(sessionID, context)
	}
	return context, nil
}

// SetContext stores context in working memory and persists to DB for durability.
func (s *memoryService) SetContext(ctx context.Context, sessionID string, context Context) error {
	// Store in memory cache for fast access
	s.working.Store(sessionID, context)
	// Persist to database for durability
	return s.SaveContext(ctx, sessionID, context)
}

// SaveContext persists working memory context to DB with TTL.
func (s *memoryService) SaveContext(ctx context.Context, sessionID string, context Context) error {
	jsonData, err := json.Marshal(context)
	if err != nil {
		return fmt.Errorf("failed to marshal context: %w", err)
	}

	var expiresAt sql.NullInt64
	if s.ttl > 0 {
		t := time.Now().Add(s.ttl).Unix()
		expiresAt = sql.NullInt64{Int64: t, Valid: true}
	}

	_, err = s.db.SaveWorkingContext(ctx, db.SaveWorkingContextParams{
		ID:          uuid.New().String(),
		SessionID:   sessionID,
		ContextJson: string(jsonData),
		Version:     1,
		ExpiresAt:   expiresAt,
	})
	if err != nil {
		return fmt.Errorf("failed to save working context: %w", err)
	}
	return nil
}

// RestoreContext loads working memory context from DB.
func (s *memoryService) RestoreContext(ctx context.Context, sessionID string) (Context, error) {
	row, err := s.db.GetWorkingContext(ctx, sessionID)
	if err != nil {
		// Not found is OK, return empty context
		return Context{}, nil
	}

	var context Context
	if err := json.Unmarshal([]byte(row.ContextJson), &context); err != nil {
		return Context{}, fmt.Errorf("failed to unmarshal context: %w", err)
	}

	return context, nil
}

// runGC periodically cleans up expired contexts from the database.
func (s *memoryService) runGC() {
	defer logging.RecoverPanic("memoryService.runGC", nil)
	ticker := time.NewTicker(s.gcTick)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			if err := s.db.DeleteExpiredContexts(ctx); err != nil {
				logging.Error("failed to delete expired contexts", "error", err)
			}
			cancel()
		}
	}
}

// RecordEpisode stores a new episode in episodic memory.
func (s *memoryService) RecordEpisode(ctx context.Context, episode Episode) error {
	if episode.ID == "" {
		episode.ID = uuid.New().String()
	}

	taskJSON, err := json.Marshal(episode.Task)
	if err != nil {
		return fmt.Errorf("failed to marshal task: %w", err)
	}

	actionsJSON, err := json.Marshal(episode.Actions)
	if err != nil {
		return fmt.Errorf("failed to marshal actions: %w", err)
	}

	feedbackJSON, err := json.Marshal(episode.Feedback)
	if err != nil {
		return fmt.Errorf("failed to marshal feedback: %w", err)
	}

	params := db.CreateEpisodeParams{
		ID:          episode.ID,
		SessionID:   toNullString(episode.SessionID),
		AgencyID:    toNullString(episode.AgencyID),
		AgentID:     toNullString(episode.AgentID),
		Task:        toNullString(string(taskJSON)),
		Actions:     toNullString(string(actionsJSON)),
		Outcome:     toNullString(episode.Outcome),
		Feedback:    toNullString(string(feedbackJSON)),
		EmbeddingID: toNullString(""),
	}

	_, err = s.db.CreateEpisode(ctx, params)
	if err != nil {
		return fmt.Errorf("failed to create episode: %w", err)
	}

	return nil
}

// SearchEpisodes searches episodic memory using keyword matching.
func (s *memoryService) SearchEpisodes(ctx context.Context, query EpisodeQuery) ([]Episode, error) {
	limit := int64(query.Limit)
	if limit <= 0 {
		limit = 20
	}

	if query.SessionID != "" {
		dbEpisodes, err := s.db.ListEpisodesBySession(ctx, db.ListEpisodesBySessionParams{
			SessionID: toNullString(query.SessionID),
			Limit:     limit,
			Offset:    0,
		})
		if err != nil {
			return nil, fmt.Errorf("failed to search episodes by session: %w", err)
		}
		return convertDBEpisodes(dbEpisodes), nil
	}

	// Fallback to listing all episodes
	dbEpisodes, err := s.db.ListEpisodes(ctx, db.ListEpisodesParams{
		Limit:  limit,
		Offset: 0,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to list episodes: %w", err)
	}

	return convertDBEpisodes(dbEpisodes), nil
}

// GetSimilarEpisodes finds episodes similar to a given situation.
// MVP implementation: uses keyword-based fallback from SearchEpisodes.
func (s *memoryService) GetSimilarEpisodes(ctx context.Context, situation Situation) ([]Episode, error) {
	// Fallback: keyword-based search using the description
	dbEpisodes, err := s.db.SearchEpisodes(ctx, db.SearchEpisodesParams{
		Column1: toNullString(situation.Description),
		Column2: toNullString(situation.Description),
		Limit:   10,
	})
	if err != nil {
		// Fallback to listing recent episodes
		dbEpisodes, err = s.db.ListEpisodes(ctx, db.ListEpisodesParams{
			Limit:  10,
			Offset: 0,
		})
		if err != nil {
			return nil, fmt.Errorf("failed to find similar episodes: %w", err)
		}
	}

	return convertDBEpisodes(dbEpisodes), nil
}

// StoreFact stores a new fact in semantic memory.
func (s *memoryService) StoreFact(ctx context.Context, fact Fact) error {
	if fact.ID == "" {
		fact.ID = uuid.New().String()
	}

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
		return fmt.Errorf("failed to store fact: %w", err)
	}

	return nil
}

// GetFacts retrieves facts for a given domain.
func (s *memoryService) GetFacts(ctx context.Context, domain string) ([]Fact, error) {
	dbFacts, err := s.db.ListFactsByDomain(ctx, domain)
	if err != nil {
		return nil, fmt.Errorf("failed to get facts: %w", err)
	}

	return convertDBFacts(dbFacts), nil
}

// QueryKnowledge searches the knowledge base.
func (s *memoryService) QueryKnowledge(ctx context.Context, query string) ([]KnowledgeItem, error) {
	dbFacts, err := s.db.SearchFacts(ctx, db.SearchFactsParams{
		Column1: toNullString(query),
		Domain:  query,
		Limit:   20,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to query knowledge: %w", err)
	}

	result := make([]KnowledgeItem, 0, len(dbFacts))
	for _, f := range dbFacts {
		result = append(result, KnowledgeItem{
			ID:      f.ID,
			Content: f.Content,
			Domain:  f.Domain,
			Tags:    []string{f.Category.String},
			Source:  f.Source.String,
			Metadata: map[string]any{
				"confidence": f.Confidence,
				"use_count":  f.UseCount,
			},
		})
	}

	return result, nil
}

// SaveProcedure stores a new procedure in procedural memory.
func (s *memoryService) SaveProcedure(ctx context.Context, procedure Procedure) error {
	if procedure.ID == "" {
		procedure.ID = uuid.New().String()
	}

	stepsJSON, err := json.Marshal(procedure.Steps)
	if err != nil {
		return fmt.Errorf("failed to marshal steps: %w", err)
	}

	params := db.CreateProcedureParams{
		ID:             procedure.ID,
		Name:           procedure.Name,
		Description:    toNullString(procedure.Description),
		TriggerType:    procedure.Trigger.Type,
		TriggerPattern: toNullString(procedure.Trigger.Pattern),
		Steps:          string(stepsJSON),
	}

	_, err = s.db.CreateProcedure(ctx, params)
	if err != nil {
		return fmt.Errorf("failed to save procedure: %w", err)
	}

	return nil
}

// GetProcedure retrieves a procedure by name.
func (s *memoryService) GetProcedure(ctx context.Context, name string) (Procedure, error) {
	dbProc, err := s.db.GetProcedureByName(ctx, name)
	if err != nil {
		return Procedure{}, fmt.Errorf("failed to get procedure: %w", err)
	}

	return convertDBProcedure(dbProc), nil
}

// FindApplicableProcedures finds procedures matching a task.
// MVP implementation: simple matching on trigger_type and trigger_pattern (contains/prefix).
func (s *memoryService) FindApplicableProcedures(ctx context.Context, task map[string]any) ([]Procedure, error) {
	taskType := ""
	if v, ok := task["type"].(string); ok {
		taskType = v
	}

	// Try to find by trigger_type first
	dbProcs, err := s.db.ListProceduresByTrigger(ctx, taskType)
	if err != nil || len(dbProcs) == 0 {
		// Fallback to all procedures
		dbProcs, err = s.db.ListProcedures(ctx)
		if err != nil {
			return nil, fmt.Errorf("failed to find procedures: %w", err)
		}
	}

	result := make([]Procedure, 0, len(dbProcs))
	for _, p := range dbProcs {
		proc := convertDBProcedure(p)
		// Simple pattern matching: check if trigger_pattern is contained in task description
		if taskDesc, ok := task["description"].(string); ok {
			if proc.Trigger.Pattern != "" && strings.Contains(taskDesc, proc.Trigger.Pattern) {
				result = append(result, proc)
			}
		}
	}

	return result, nil
}

// LearnFromSuccess updates metrics when an action succeeds.
func (s *memoryService) LearnFromSuccess(ctx context.Context, action Action, outcome string) error {
	// Record the successful episode
	episode := Episode{
		Timestamp: time.Now(),
		Actions:   []Action{action},
		Outcome:   outcome,
	}

	if err := s.RecordEpisode(ctx, episode); err != nil {
		return fmt.Errorf("failed to record success episode: %w", err)
	}

	// Update procedure stats if this was a procedure-based action
	if action.Tool != "" {
		procs, err := s.db.ListProceduresByTrigger(ctx, action.Tool)
		if err == nil && len(procs) > 0 {
			for _, p := range procs {
				newRate := (p.SuccessRate*float64(p.UseCount) + 1.0) / float64(p.UseCount+1)
				err = s.db.UpdateProcedureStats(ctx, db.UpdateProcedureStatsParams{
					SuccessRate: newRate,
					ID:          p.ID,
				})
				if err != nil {
					logging.Error("Failed to update procedure stats", "procedure", p.Name, "error", err)
				}
			}
		}
	}

	return nil
}

// LearnFromFailure records a failure and updates metrics.
func (s *memoryService) LearnFromFailure(ctx context.Context, action Action, err error) error {
	reason := "unknown"
	if err != nil {
		reason = err.Error()
	}

	// Record the failure episode
	episode := Episode{
		Timestamp: time.Now(),
		Actions:   []Action{action},
		Outcome:   "failure: " + reason,
	}

	if recErr := s.RecordEpisode(ctx, episode); recErr != nil {
		return fmt.Errorf("failed to record failure episode: %w", recErr)
	}

	// Store failure fact
	failureFact := Fact{
		Domain:     "failure",
		Category:   "error",
		Content:    fmt.Sprintf("Action %s failed: %s", action.Tool, reason),
		Source:     "learning",
		Confidence: 0.8,
	}

	if storeErr := s.StoreFact(ctx, failureFact); storeErr != nil {
		return fmt.Errorf("failed to store failure fact: %w", storeErr)
	}

	return nil
}

// GetPerformanceMetrics retrieves performance metrics for a time range.
func (s *memoryService) GetPerformanceMetrics(ctx context.Context, timeRange TimeRange) (Metrics, error) {
	// Get all episodes in the time range
	episodes, err := s.db.ListEpisodes(ctx, db.ListEpisodesParams{
		Limit:  1000,
		Offset: 0,
	})
	if err != nil {
		return Metrics{}, fmt.Errorf("failed to get episodes for metrics: %w", err)
	}

	// Calculate basic metrics
	var total int64
	var successes int64

	bySkill := make(map[string]SkillMetrics)
	byAgency := make(map[string]AgencyMetrics)

	for _, ep := range episodes {
		total++
		outcome := ep.Outcome.String

		// Consider success if outcome doesn't start with "failure"
		isSuccess := outcome != "" && !strings.HasPrefix(outcome, "failure")
		if isSuccess {
			successes++
		}

		// Aggregate by agency
		agencyID := ep.AgencyID.String
		if agencyID != "" {
			am := byAgency[agencyID]
			am.TotalTasks++
			if isSuccess {
				am.SuccessRate++
			}
			byAgency[agencyID] = am
		}
	}

	rate := 0.0
	if total > 0 {
		rate = float64(successes) / float64(total)
	}

	return Metrics{
		TotalTasks:  total,
		SuccessRate: rate,
		BySkill:     bySkill,
		ByAgency:    byAgency,
	}, nil
}

// GenerateInsights generates insights from accumulated memory.
func (s *memoryService) GenerateInsights(ctx context.Context) ([]string, error) {
	var insights []string

	// Get top procedures by usage
	procs, err := s.db.ListProcedures(ctx)
	if err == nil && len(procs) > 0 {
		for i, p := range procs {
			if i >= 5 {
				break
			}
			insights = append(insights, fmt.Sprintf("Procedure '%s' used %d times with %.1f%% success rate",
				p.Name, p.UseCount, p.SuccessRate*100))
		}
	}

	// Get failure patterns
	facts, err := s.db.ListFactsByDomain(ctx, "failure")
	if err == nil && len(facts) > 0 {
		insights = append(insights, fmt.Sprintf("Identified %d failure patterns in knowledge base", len(facts)))
	}

	return insights, nil
}

// Helper functions

func toNullString(s string) sql.NullString {
	if s == "" {
		return sql.NullString{}
	}
	return sql.NullString{String: s, Valid: true}
}

func convertDBEpisodes(dbEpisodes []db.Episode) []Episode {
	result := make([]Episode, 0, len(dbEpisodes))
	for _, ep := range dbEpisodes {
		result = append(result, convertDBEpisode(ep))
	}
	return result
}

func convertDBEpisode(ep db.Episode) Episode {
	result := Episode{
		ID:        ep.ID,
		SessionID: ep.SessionID.String,
		AgencyID:  ep.AgencyID.String,
		AgentID:   ep.AgentID.String,
		Outcome:   ep.Outcome.String,
		Timestamp: time.Unix(ep.CreatedAt, 0),
	}

	if ep.Task.String != "" {
		json.Unmarshal([]byte(ep.Task.String), &result.Task)
	}
	if ep.Actions.String != "" {
		json.Unmarshal([]byte(ep.Actions.String), &result.Actions)
	}
	if ep.Feedback.String != "" {
		var fb Feedback
		json.Unmarshal([]byte(ep.Feedback.String), &fb)
		result.Feedback = &fb
	}

	return result
}

func convertDBFacts(dbFacts []db.Fact) []Fact {
	result := make([]Fact, 0, len(dbFacts))
	for _, f := range dbFacts {
		result = append(result, Fact{
			ID:         f.ID,
			Domain:     f.Domain,
			Category:   f.Category.String,
			Content:    f.Content,
			Source:     f.Source.String,
			Confidence: f.Confidence,
			CreatedAt:  time.Unix(f.CreatedAt, 0),
			UseCount:   f.UseCount,
		})
	}
	return result
}

func convertDBProcedure(p db.Procedure) Procedure {
	result := Procedure{
		ID:          p.ID,
		Name:        p.Name,
		Description: p.Description.String,
		Trigger: TriggerCondition{
			Type:    p.TriggerType,
			Pattern: p.TriggerPattern.String,
		},
		SuccessRate: p.SuccessRate,
		UseCount:    p.UseCount,
	}

	if p.Steps != "" {
		json.Unmarshal([]byte(p.Steps), &result.Steps)
	}

	return result
}
