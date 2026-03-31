package memory

import (
	"context"
	"database/sql"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"hash/fnv"
	"math"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/logging"
)

// EmbeddingConfig defines configuration for the embedding system.
type EmbeddingConfig struct {
	// Enabled indicates whether embedding generation is enabled.
	Enabled bool
	// Provider is the provider name for embeddings (e.g., "local", "openai").
	Provider string
	// Model is the embedding model ID.
	Model string
	// Mode controls the retrieval mode: "lexical", "hybrid", or "vector".
	Mode string
	// BatchSize is the number of texts to batch in a single embedding request.
	BatchSize int
	// Timeout is the timeout for embedding generation.
	Timeout time.Duration
	// VectorCacheEnabled enables in-memory caching of embedding vectors.
	VectorCacheEnabled bool
}

// EmbeddingMetrics tracks embedding generation statistics.
type EmbeddingMetrics struct {
	TotalGenerated  int64
	TotalCacheHits  int64
	TotalBackfilled int64
	AvgLatencyMs    float64
	LastError       string
	LastGeneratedAt time.Time
}

// embeddingRequest represents a request to generate an embedding for an episode.
type embeddingRequest struct {
	episodeID string
	text      string
	textHash  string
}

// memoryService implements MemoryService using sync.Map for working memory
// and the existing sqlc-generated queries for persistent storage.
type memoryService struct {
	db       db.Querier
	working  sync.Map // map[string]Context - session context cache
	metrics  sync.Map // map[string]*Metrics - per-session metrics
	ttl      time.Duration
	gcTick   time.Duration
	stopCh   chan struct{}
	stopOnce sync.Once // Ensures Close() is idempotent

	// Embedding support
	embedConfig  EmbeddingConfig
	embedFunc    func(ctx context.Context, text string) ([]float32, error) // Function to generate embeddings
	embedQueue   chan embeddingRequest                                     // Queue for async embedding generation
	embedStopCh  chan struct{}
	embedCache   sync.Map // map[string][]float32 - episode ID to vector cache
	embedMetrics EmbeddingMetrics
	metricsMu    sync.RWMutex // Protects embedMetrics
}

// RetentionConfig defines retention policy for memory data.
type RetentionConfig struct {
	EpisodeRetention   time.Duration // How long to keep episodes
	FactRetention      time.Duration // How long to keep facts
	ProcedureRetention time.Duration // How long to keep procedures
	InsightRetention   time.Duration // How long to keep insights
	MaxEpisodesPerDay  int           // Max episodes to keep per day
}

// DefaultRetentionConfig returns sensible defaults.
func DefaultRetentionConfig() RetentionConfig {
	return RetentionConfig{
		EpisodeRetention:   30 * 24 * time.Hour,  // 30 days
		FactRetention:      90 * 24 * time.Hour,  // 90 days
		ProcedureRetention: 180 * 24 * time.Hour, // 180 days
		InsightRetention:   7 * 24 * time.Hour,   // 7 days
		MaxEpisodesPerDay:  1000,                 // Max 1000 episodes per day
	}
}

// EmbeddingFunc is a function type that generates embeddings for text.
type EmbeddingFunc func(ctx context.Context, text string) ([]float32, error)

// DefaultEmbeddingConfig returns sensible defaults.
func DefaultEmbeddingConfig() EmbeddingConfig {
	return EmbeddingConfig{
		Enabled:   false,
		Provider:  "",
		Model:     "",
		Mode:      "lexical",
		BatchSize: 1,
		Timeout:   30 * time.Second,
	}
}

// NewService creates a new MemoryService instance with TTL for working memory persistence.
// If embedFunc is provided and config.Enabled is true, embeddings will be generated asynchronously.
func NewService(q db.Querier, ttl time.Duration, embedFunc EmbeddingFunc, embedConfig EmbeddingConfig) MemoryService {
	svc := &memoryService{
		db:     q,
		ttl:    ttl,
		gcTick: 5 * time.Minute,
		stopCh: make(chan struct{}),
	}
	// Start GC goroutine for expired context cleanup
	go svc.runGC()

	// Initialize embedding if enabled
	if embedFunc != nil && embedConfig.Enabled {
		svc.embedFunc = embedFunc
		svc.embedConfig = embedConfig
		svc.embedQueue = make(chan embeddingRequest, embedConfig.BatchSize*4)
		svc.embedStopCh = make(chan struct{})
		go svc.runEmbeddingWorker()
	}

	return svc
}

// Close stops the memory service and cleans up resources.
// It is safe to call multiple times - subsequent calls are no-ops.
func (s *memoryService) Close() error {
	s.stopOnce.Do(func() {
		close(s.stopCh)
		close(s.embedStopCh)
	})
	return nil
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
// It stops when the stop channel is closed.
func (s *memoryService) runGC() {
	defer logging.RecoverPanic("memoryService.runGC", nil)
	ticker := time.NewTicker(s.gcTick)
	defer ticker.Stop()
	for {
		select {
		case <-s.stopCh:
			return
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

	// Generate embedding asynchronously if enabled
	if s.embedFunc != nil && s.embedConfig.Enabled {
		embeddingText := episodeToText(episode)
		s.enqueueEmbedding(episode.ID, embeddingText)
	}

	return nil
}

// SearchEpisodes searches episodic memory using filters and ranking.
// Supports filtering by sessionID, agencyID, agentID, taskType, and timeRange.
// Results are ranked by outcome quality (success > partial > failure) then by recency.
func (s *memoryService) SearchEpisodes(ctx context.Context, query EpisodeQuery) ([]Episode, error) {
	limit := int64(query.Limit)
	if limit <= 0 {
		limit = 20
	}

	var dbEpisodes []db.Episode
	var err error

	// Use most specific query available, then filter in memory
	switch {
	case query.SessionID != "":
		// Filter by session first
		dbEpisodes, err = s.db.ListEpisodesBySession(ctx, db.ListEpisodesBySessionParams{
			SessionID: toNullString(query.SessionID),
			Limit:     100, // Fetch more for additional filtering
			Offset:    0,
		})
	default:
		// Fetch recent episodes
		dbEpisodes, err = s.db.ListEpisodes(ctx, db.ListEpisodesParams{
			Limit:  100,
			Offset: 0,
		})
	}
	if err != nil {
		return nil, fmt.Errorf("failed to search episodes: %w", err)
	}

	episodes := convertDBEpisodes(dbEpisodes)

	// Apply additional filters in memory
	episodes = filterEpisodes(episodes, query)

	// Apply time range filter if specified
	if query.TimeRange != nil {
		episodes = filterEpisodesByTimeRange(episodes, query.TimeRange)
	}

	// Apply ranking: success first, then recency
	episodes = rankEpisodes(episodes)

	// Limit results
	if len(episodes) > int(limit) {
		episodes = episodes[:limit]
	}

	return episodes, nil
}

// filterEpisodes applies filters to episode list
func filterEpisodes(episodes []Episode, query EpisodeQuery) []Episode {
	if query.AgencyID == "" && query.AgentID == "" && query.TaskType == "" {
		return episodes
	}

	var result []Episode
	for _, ep := range episodes {
		if query.AgencyID != "" && ep.AgencyID != query.AgencyID {
			continue
		}
		if query.AgentID != "" && ep.AgentID != query.AgentID {
			continue
		}
		if query.TaskType != "" {
			taskStr, _ := json.Marshal(ep.Task)
			if !strings.Contains(string(taskStr), query.TaskType) {
				continue
			}
		}
		result = append(result, ep)
	}
	return result
}

// GetSimilarEpisodes finds episodes similar to a given situation.
// Uses hybrid scoring: vector similarity (when available) + keyword matching + recency + outcome.
// Falls back to keyword-only scoring when vector embeddings are not available.
func (s *memoryService) GetSimilarEpisodes(ctx context.Context, situation Situation) ([]Episode, error) {
	// Get recent episodes for comparison
	recentEpisodes, err := s.db.ListEpisodes(ctx, db.ListEpisodesParams{
		Limit:  50,
		Offset: 0,
	})
	if err != nil {
		return nil, err
	}

	if len(recentEpisodes) == 0 {
		return nil, nil
	}

	// Generate embedding for the query situation if vector search is enabled
	var queryEmbedding []float32
	if s.embedFunc != nil && s.embedConfig.Enabled && s.embedConfig.Mode != "lexical" {
		queryEmbedding, _ = s.embedFunc(ctx, situation.Description)
	}

	// Score all episodes
	type scoredEpisode struct {
		episode Episode
		score   float64
	}
	var scoredEpisodes []scoredEpisode

	for _, ep := range recentEpisodes {
		episode := convertDBEpisode(ep)
		score := s.calculateHybridScore(ctx, ep, episode, situation, queryEmbedding)
		if score > 0.1 { // Minimum threshold
			scoredEpisodes = append(scoredEpisodes, scoredEpisode{episode, score})
		}
	}

	// If no good matches, fall back to recency-based
	if len(scoredEpisodes) == 0 {
		// Return top 5 most recent episodes
		result := make([]Episode, 0, min(5, len(recentEpisodes)))
		for i := 0; i < min(5, len(recentEpisodes)); i++ {
			result = append(result, convertDBEpisode(recentEpisodes[i]))
		}
		return result, nil
	}

	// Sort by score descending
	sort.Slice(scoredEpisodes, func(i, j int) bool {
		return scoredEpisodes[i].score > scoredEpisodes[j].score
	})

	// Return top 10
	result := make([]Episode, 0, min(10, len(scoredEpisodes)))
	for i := 0; i < min(10, len(scoredEpisodes)); i++ {
		result = append(result, scoredEpisodes[i].episode)
	}

	return result, nil
}

// calculateHybridScore computes a hybrid similarity score for an episode.
// Combines vector similarity (if available), keyword matching, recency, and outcome.
func (s *memoryService) calculateHybridScore(ctx context.Context, ep db.Episode, episode Episode, situation Situation, queryEmbedding []float32) float64 {
	const (
		vectorWeight  = 0.4
		keywordWeight = 0.3
		recencyWeight = 0.2
		outcomeWeight = 0.1
	)

	var totalScore float64

	// 1. Vector similarity (highest weight)
	if queryEmbedding != nil && len(queryEmbedding) > 0 {
		if emb, err := s.getEpisodeEmbedding(ctx, ep.ID); err == nil && len(emb) > 0 {
			cosineSim := cosineSimilarity(queryEmbedding, emb)
			totalScore += vectorWeight * cosineSim
		}
	}

	// 2. Keyword similarity
	keywords := extractKeywords(situation.Description)
	keywordScore := calculateKeywordScore(ep, keywords)
	totalScore += keywordWeight * keywordScore

	// 3. Recency bonus
	recencyBonus := calculateRecencyBonus(ep.CreatedAt)
	totalScore += recencyWeight * recencyBonus

	// 4. Outcome bonus
	outcomeBonus := calculateOutcomeBonus(ep.Outcome.String)
	totalScore += outcomeWeight * outcomeBonus

	return totalScore
}

// cosineSimilarity computes the cosine similarity between two vectors.
func cosineSimilarity(a, b []float32) float64 {
	if len(a) != len(b) || len(a) == 0 {
		return 0
	}

	var dotProduct float64
	var normA float64
	var normB float64

	for i := range a {
		dotProduct += float64(a[i]) * float64(b[i])
		normA += float64(a[i]) * float64(a[i])
		normB += float64(b[i]) * float64(b[i])
	}

	if normA == 0 || normB == 0 {
		return 0
	}

	return dotProduct / (math.Sqrt(normA) * math.Sqrt(normB))
}

// calculateKeywordScore computes keyword-based similarity score.
func calculateKeywordScore(ep db.Episode, keywords []string) float64 {
	if len(keywords) == 0 {
		return 0
	}

	taskStr := ep.Task.String
	matchCount := 0
	for _, kw := range keywords {
		if strings.Contains(taskStr, kw) {
			matchCount++
		}
	}

	return float64(matchCount) / float64(len(keywords))
}

// calculateRecencyBonus returns a recency bonus (0-1) based on episode age.
func calculateRecencyBonus(createdAt int64) float64 {
	age := time.Now().Unix() - createdAt

	switch {
	case age < 3600: // Less than 1 hour
		return 1.0
	case age < 86400: // Less than 1 day
		return 0.8
	case age < 604800: // Less than 1 week
		return 0.5
	case age < 2592000: // Less than 1 month
		return 0.3
	default:
		return 0.1
	}
}

// calculateOutcomeBonus returns an outcome bonus (0-1) based on episode outcome.
func calculateOutcomeBonus(outcome string) float64 {
	switch {
	case strings.HasPrefix(outcome, "success"):
		return 1.0
	case strings.HasPrefix(outcome, "partial"):
		return 0.5
	case strings.HasPrefix(outcome, "failure"):
		return 0.0
	default:
		return 0.3
	}
}

// StoreFact stores a new fact in semantic memory with deduplication.
func (s *memoryService) StoreFact(ctx context.Context, fact Fact) error {
	// Check for duplicate by content hash in same domain
	existingFacts, err := s.db.ListFactsByDomain(ctx, fact.Domain)
	if err != nil {
		return fmt.Errorf("failed to check existing facts: %w", err)
	}

	// Normalize content for comparison
	normalizedContent := normalizeFactContent(fact.Content)

	for _, ef := range existingFacts {
		if ef.Category.String == fact.Category &&
			normalizeFactContent(ef.Content) == normalizedContent {
			// Found duplicate - update confidence based on confirmation
			newConfidence := (ef.Confidence + fact.Confidence) / 2.0
			if fact.Confidence > ef.Confidence {
				newConfidence = ef.Confidence + (1.0-ef.Confidence)*0.1 // Boost
			}
			return s.db.UpdateFactConfidence(ctx, db.UpdateFactConfidenceParams{
				Confidence: newConfidence,
				ID:         ef.ID,
			})
		}
	}

	// No duplicate found - create new fact
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

	_, err = s.db.CreateFact(ctx, params)
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

// QueryKnowledge searches the knowledge base and tracks usage.
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
		// Track usage of this fact
		if err := s.db.IncrementFactUsage(ctx, f.ID); err != nil {
			// Log but don't fail - usage tracking is best effort
			logging.Error("Failed to increment fact usage", "fact_id", f.ID, "error", err)
		}

		result = append(result, KnowledgeItem{
			ID:      f.ID,
			Content: f.Content,
			Domain:  f.Domain,
			Tags:    []string{f.Category.String},
			Source:  f.Source.String,
			Metadata: map[string]any{
				"confidence": f.Confidence,
				"use_count":  f.UseCount,
				"last_used":  time.Now().Unix(),
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

// DiscoverProcedures analyzes episodes to discover new procedures.
// Returns candidate procedures that meet the minimum quality threshold.
func (s *memoryService) DiscoverProcedures(ctx context.Context, minSuccessRate float64, minSamples int) ([]Procedure, error) {
	// Get recent successful episodes
	episodes, err := s.db.ListEpisodes(ctx, db.ListEpisodesParams{
		Limit:  100,
		Offset: 0,
	})
	if err != nil {
		return nil, err
	}

	// Group episodes by task type and actions
	taskPatterns := groupEpisodesByPattern(episodes)

	var candidates []Procedure
	for pattern, eps := range taskPatterns {
		if len(eps) < minSamples {
			continue
		}

		// Calculate success rate for this pattern
		var successes int
		for _, ep := range eps {
			if ep.Outcome.Valid && !strings.HasPrefix(ep.Outcome.String, "failure") {
				successes++
			}
		}
		successRate := float64(successes) / float64(len(eps))

		if successRate >= minSuccessRate && successRate > 0.5 {
			// Extract steps from first successful episode
			var steps []ProcedureStep
			if len(eps) > 0 && eps[0].Actions.Valid {
				var actions []Action
				json.Unmarshal([]byte(eps[0].Actions.String), &actions)
				for i, a := range actions {
					steps = append(steps, ProcedureStep{
						Order:       i,
						Name:        a.Tool,
						Description: fmt.Sprintf("Execute %s", a.Tool),
						Action:      a.Tool,
						Params:      a.Input,
					})
				}
			}

			candidates = append(candidates, Procedure{
				ID:          uuid.New().String(),
				Name:        fmt.Sprintf("auto_%s_%d", pattern, len(eps)),
				Description: fmt.Sprintf("Discovered from %d episodes with %.0f%% success rate", len(eps), successRate*100),
				Trigger: TriggerCondition{
					Type:    "task_type",
					Pattern: pattern,
				},
				Steps:       steps,
				SuccessRate: successRate,
				UseCount:    int64(len(eps)),
			})
		}
	}

	return candidates, nil
}

// groupEpisodesByPattern groups episodes by their task type.
func groupEpisodesByPattern(episodes []db.Episode) map[string][]db.Episode {
	groups := make(map[string][]db.Episode)
	for _, ep := range episodes {
		if !ep.Task.Valid || ep.Task.String == "" {
			continue
		}
		var task map[string]any
		if err := json.Unmarshal([]byte(ep.Task.String), &task); err != nil {
			continue
		}
		taskType, _ := task["type"].(string)
		if taskType == "" {
			taskType = "unknown"
		}
		groups[taskType] = append(groups[taskType], ep)
	}
	return groups
}

// FindApplicableProcedures finds procedures matching a task with scoring.
// Returns procedures sorted by relevance score (highest first).
func (s *memoryService) FindApplicableProcedures(ctx context.Context, task map[string]any) ([]Procedure, error) {
	taskType := ""
	taskDesc := ""
	if v, ok := task["type"].(string); ok {
		taskType = v
	}
	if v, ok := task["description"].(string); ok {
		taskDesc = v
	}

	// Get all procedures
	dbProcs, err := s.db.ListProcedures(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to find procedures: %w", err)
	}

	type scoredProc struct {
		procedure Procedure
		score     float64
	}
	var scored []scoredProc

	for _, p := range dbProcs {
		proc := convertDBProcedure(p)
		score := calculateProcedureScore(proc, taskType, taskDesc)

		// Only include if score exceeds threshold
		if score > 0.1 {
			scored = append(scored, scoredProc{procedure: proc, score: score})
		}
	}

	// Sort by score descending
	sort.Slice(scored, func(i, j int) bool {
		return scored[i].score > scored[j].score
	})

	result := make([]Procedure, 0, len(scored))
	for _, sp := range scored {
		result = append(result, sp.procedure)
	}

	return result, nil
}

// calculateProcedureScore computes relevance score for a procedure given a task.
// Score factors: trigger_type match, pattern match, success rate, usage count.
func calculateProcedureScore(proc Procedure, taskType, taskDesc string) float64 {
	var score float64

	// Trigger type match (highest weight)
	if proc.Trigger.Type == "task_type" && taskType != "" {
		if proc.Trigger.Pattern == taskType {
			score += 0.5
		}
	}

	// Pattern match in description
	if proc.Trigger.Pattern != "" && taskDesc != "" {
		if strings.Contains(strings.ToLower(taskDesc), strings.ToLower(proc.Trigger.Pattern)) {
			score += 0.3
		}
	}

	// Success rate bonus (higher success = more trustworthy)
	score += proc.SuccessRate * 0.15

	// Usage count bonus (more used = validated)
	usageScore := math.Min(float64(proc.UseCount)/100.0, 1.0) * 0.05
	score += usageScore

	return score
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

// rankEpisodes applies multi-criteria ranking: success > partial > failure, then recency
func rankEpisodes(episodes []Episode) []Episode {
	// Sort by outcome quality (success first) then by timestamp (recency)
	sort.Slice(episodes, func(i, j int) bool {
		oi := outcomeRank(episodes[i].Outcome)
		oj := outcomeRank(episodes[j].Outcome)
		if oi != oj {
			return oi < oj
		}
		return episodes[i].Timestamp.After(episodes[j].Timestamp)
	})
	return episodes
}

func outcomeRank(outcome string) int {
	switch {
	case strings.HasPrefix(outcome, "success"):
		return 1
	case strings.HasPrefix(outcome, "partial"):
		return 2
	case strings.HasPrefix(outcome, "failure"):
		return 3
	default:
		return 4
	}
}

func filterEpisodesByTimeRange(episodes []Episode, tr *TimeRange) []Episode {
	if tr == nil {
		return episodes
	}
	var result []Episode
	for _, ep := range episodes {
		if (tr.Start.IsZero() || ep.Timestamp.After(tr.Start)) &&
			(tr.End.IsZero() || ep.Timestamp.Before(tr.End)) {
			result = append(result, ep)
		}
	}
	return result
}

func calculateSimilarityScore(ep db.Episode, situation Situation, keywords []string) float64 {
	var score float64

	// Check task description similarity
	taskStr := ep.Task.String
	for _, kw := range keywords {
		if strings.Contains(taskStr, kw) {
			score += 0.2
		}
	}

	// Outcome bonus
	if strings.HasPrefix(ep.Outcome.String, "success") {
		score += 0.3
	}

	// Recency bonus (recent episodes more likely relevant)
	age := time.Now().Unix() - ep.CreatedAt
	if age < 3600 { // Less than 1 hour
		score += 0.2
	} else if age < 86400 { // Less than 1 day
		score += 0.1
	}

	return score
}

func extractKeywords(text string) []string {
	// Simple keyword extraction - split on spaces, remove common words
	words := strings.Fields(text)
	var keywords []string
	stopWords := map[string]bool{
		"the": true, "a": true, "an": true, "is": true, "are": true,
		"was": true, "were": true, "to": true, "for": true, "of": true,
		"and": true, "or": true, "in": true, "on": true, "at": true,
	}
	for _, w := range words {
		if len(w) > 3 && !stopWords[strings.ToLower(w)] {
			keywords = append(keywords, w)
		}
	}
	return keywords
}

// normalizeFactContent normalizes fact content for deduplication comparison.
func normalizeFactContent(content string) string {
	// Convert to lowercase, trim whitespace, collapse multiple spaces
	normalized := strings.ToLower(content)
	normalized = strings.TrimSpace(normalized)
	normalized = strings.Join(strings.Fields(normalized), " ")
	return normalized
}

// EnforceRetentionPolicy applies retention policy to all memory types.
// Returns count of deleted records per type.
func (s *memoryService) EnforceRetentionPolicy(ctx context.Context, cfg RetentionConfig) (map[string]int64, error) {
	results := make(map[string]int64)
	now := time.Now()

	// Delete old episodes
	if cfg.EpisodeRetention > 0 {
		cutoff := now.Add(-cfg.EpisodeRetention).Unix()
		if err := s.db.DeleteOldEpisodes(ctx, cutoff); err != nil {
			logging.Error("Failed to delete old episodes", "error", err)
			results["episodes"] = 0
		} else {
			results["episodes"] = 1 // Bulk delete succeeded
		}
	}

	// Delete old working memory contexts
	if cfg.EpisodeRetention > 0 {
		if err := s.db.DeleteExpiredContexts(ctx); err != nil {
			logging.Error("Failed to delete expired contexts", "error", err)
		}
	}

	// Delete low-use facts older than retention period
	if cfg.FactRetention > 0 {
		factCutoff := now.Add(-cfg.FactRetention).Unix()
		// Get all facts and delete those that are old and unused
		if facts, err := s.db.ListFactsByDomain(ctx, ""); err == nil {
			for _, fact := range facts {
				// Check if fact is old and has zero use count
				if fact.UseCount == 0 && fact.CreatedAt < int64(factCutoff) {
					if err := s.db.DeleteFact(ctx, fact.ID); err != nil {
						logging.Error("Failed to delete old fact", "id", fact.ID, "error", err)
					} else {
						results["facts"]++
					}
				}
			}
		}
	}

	// Delete low-use procedures older than retention period
	if cfg.ProcedureRetention > 0 {
		procCutoff := now.Add(-cfg.ProcedureRetention).Unix()
		// Get all procedures and delete those that are old and unused
		if procedures, err := s.db.ListProcedures(ctx); err == nil {
			for _, proc := range procedures {
				// Check if procedure is old and has zero use count
				if proc.UseCount == 0 && proc.UpdatedAt < int64(procCutoff) {
					if err := s.db.DeleteProcedure(ctx, proc.ID); err != nil {
						logging.Error("Failed to delete old procedure", "id", proc.ID, "error", err)
					} else {
						results["procedures"]++
					}
				}
			}
		}
	}

	return results, nil
}

// GetRetentionStats returns statistics about memory usage for retention planning.
func (s *memoryService) GetRetentionStats(ctx context.Context) (map[string]int64, error) {
	stats := make(map[string]int64)

	// Estimate episode count using large limit
	if episodes, err := s.db.ListEpisodes(ctx, db.ListEpisodesParams{Limit: 10000, Offset: 0}); err == nil {
		stats["total_episodes"] = int64(len(episodes))
		// Estimate if there are more
		if len(episodes) == 10000 {
			stats["episodes_estimated"] = 1
		}
	}

	// Estimate fact count using large limit
	if facts, err := s.db.ListFactsByDomain(ctx, ""); err == nil {
		stats["total_facts"] = int64(len(facts))
	}

	// Estimate procedure count using large limit
	if procedures, err := s.db.ListProcedures(ctx); err == nil {
		stats["total_procedures"] = int64(len(procedures))
	}

	// Count positive vs negative outcomes
	if episodes, err := s.db.ListEpisodes(ctx, db.ListEpisodesParams{Limit: 1000, Offset: 0}); err == nil {
		positiveCount := int64(0)
		negativeCount := int64(0)
		for _, ep := range episodes {
			outcome := ep.Outcome.String
			if outcome == "success" {
				positiveCount++
			} else if outcome == "failure" {
				negativeCount++
			}
		}
		stats["positive_episodes"] = positiveCount
		stats["negative_episodes"] = negativeCount
		if positiveCount+negativeCount > 0 {
			stats["success_rate"] = positiveCount * 100 / (positiveCount + negativeCount)
		}
	}

	return stats, nil
}

// PseudonymizeEpisode removes or hashes personally identifiable information from an episode.
func (s *memoryService) PseudonymizeEpisode(episode *Episode) {
	// Remove session-specific identifiers
	episode.SessionID = hashString(episode.SessionID)
	// Keep agency/agent for analytics but remove if too specific
	if len(episode.SessionID) > 8 {
		episode.SessionID = episode.SessionID[:8] + "..."
	}
}

// BackfillEmbeddings generates embeddings for all episodes that don't have one.
// Returns the count of episodes that were backfilled.
func (s *memoryService) BackfillEmbeddings(ctx context.Context) (int, error) {
	if s.embedFunc == nil || !s.embedConfig.Enabled {
		return 0, fmt.Errorf("embedding not enabled")
	}

	// Get all episodes
	episodes, err := s.db.ListEpisodes(ctx, db.ListEpisodesParams{
		Limit:  10000, // Large limit to get all episodes
		Offset: 0,
	})
	if err != nil {
		return 0, fmt.Errorf("failed to list episodes: %w", err)
	}

	backfilled := 0
	for _, ep := range episodes {
		// Check if episode already has an embedding
		existing, err := s.db.GetEpisodeEmbedding(ctx, ep.ID)
		if err == nil && existing.ID != "" {
			// Already has embedding, skip
			continue
		}

		// Convert to Episode struct for episodeToText
		episode := convertDBEpisode(ep)
		text := episodeToText(episode)

		// Generate embedding
		embedding, err := s.embedFunc(ctx, text)
		if err != nil {
			logging.Error("Failed to generate embedding during backfill",
				"episode_id", ep.ID,
				"error", err)
			continue
		}

		// Serialize vector
		vectorBytes, err := serializeVector(embedding)
		if err != nil {
			logging.Error("Failed to serialize embedding during backfill",
				"episode_id", ep.ID,
				"error", err)
			continue
		}

		// Get text preview
		textPreview := text
		if len(textPreview) > 500 {
			textPreview = textPreview[:500]
		}

		// Store in database
		textHash := computeTextHash(text)
		params := db.CreateEpisodeEmbeddingParams{
			ID:          uuid.New().String(),
			EpisodeID:   ep.ID,
			Provider:    s.embedConfig.Provider,
			Model:       s.embedConfig.Model,
			Dimensions:  int64(len(embedding)),
			Vector:      vectorBytes,
			TextHash:    textHash,
			TextPreview: textPreview,
		}

		if _, err := s.db.CreateEpisodeEmbedding(ctx, params); err != nil {
			logging.Error("Failed to store embedding during backfill",
				"episode_id", ep.ID,
				"error", err)
			continue
		}

		// Store in cache if enabled
		if s.embedConfig.VectorCacheEnabled {
			s.embedCache.Store(ep.ID, embedding)
		}

		backfilled++
		logging.Debug("Backfilled embedding",
			"episode_id", ep.ID,
			"dimensions", len(embedding))
	}

	// Update metrics
	s.metricsMu.Lock()
	s.embedMetrics.TotalBackfilled += int64(backfilled)
	s.metricsMu.Unlock()

	return backfilled, nil
}

// GetEmbeddingMetrics returns current embedding statistics.
func (s *memoryService) GetEmbeddingMetrics() EmbeddingMetrics {
	s.metricsMu.RLock()
	defer s.metricsMu.RUnlock()
	return s.embedMetrics
}

// hashString returns a hash of the input for pseudonymization.
func hashString(s string) string {
	h := fnv.New32a()
	h.Write([]byte(s))
	return fmt.Sprintf("%x", h.Sum32())
}

// runEmbeddingWorker processes embedding requests from the queue asynchronously.
func (s *memoryService) runEmbeddingWorker() {
	defer logging.RecoverPanic("memoryService.runEmbeddingWorker", nil)

	for {
		select {
		case <-s.embedStopCh:
			return
		case req := <-s.embedQueue:
			s.processEmbedding(req)
		}
	}
}

// processEmbedding generates and stores an embedding for an episode.
func (s *memoryService) processEmbedding(req embeddingRequest) {
	ctx, cancel := context.WithTimeout(context.Background(), s.embedConfig.Timeout)
	defer cancel()

	startTime := time.Now()
	embedding, err := s.embedFunc(ctx, req.text)
	latencyMs := float64(time.Since(startTime).Milliseconds())

	if err != nil {
		s.metricsMu.Lock()
		s.embedMetrics.LastError = err.Error()
		s.metricsMu.Unlock()
		logging.Error("Failed to generate embedding",
			"episode_id", req.episodeID,
			"error", err)
		return
	}

	// Update metrics
	s.metricsMu.Lock()
	s.embedMetrics.TotalGenerated++
	s.embedMetrics.LastGeneratedAt = time.Now()
	// Update running average latency
	if s.embedMetrics.TotalGenerated == 1 {
		s.embedMetrics.AvgLatencyMs = latencyMs
	} else {
		s.embedMetrics.AvgLatencyMs = (s.embedMetrics.AvgLatencyMs*float64(s.embedMetrics.TotalGenerated-1) + latencyMs) / float64(s.embedMetrics.TotalGenerated)
	}
	s.metricsMu.Unlock()

	// Serialize vector to bytes
	vectorBytes, err := serializeVector(embedding)
	if err != nil {
		logging.Error("Failed to serialize embedding vector",
			"episode_id", req.episodeID,
			"error", err)
		return
	}

	// Get text preview (first 500 chars)
	textPreview := req.text
	if len(textPreview) > 500 {
		textPreview = textPreview[:500]
	}

	// Store embedding in database
	params := db.CreateEpisodeEmbeddingParams{
		ID:          uuid.New().String(),
		EpisodeID:   req.episodeID,
		Provider:    s.embedConfig.Provider,
		Model:       s.embedConfig.Model,
		Dimensions:  int64(len(embedding)),
		Vector:      vectorBytes,
		TextHash:    req.textHash,
		TextPreview: textPreview,
	}

	if _, err := s.db.CreateEpisodeEmbedding(ctx, params); err != nil {
		logging.Error("Failed to store embedding",
			"episode_id", req.episodeID,
			"error", err)
		return
	}

	// Store in cache if enabled
	if s.embedConfig.VectorCacheEnabled {
		s.embedCache.Store(req.episodeID, embedding)
	}

	logging.Debug("Stored embedding",
		"episode_id", req.episodeID,
		"dimensions", len(embedding),
		"provider", s.embedConfig.Provider,
		"model", s.embedConfig.Model)
}

// serializeVector converts a float32 vector to bytes for storage.
func serializeVector(vector []float32) ([]byte, error) {
	buf := make([]byte, len(vector)*4)
	for i, v := range vector {
		binary.LittleEndian.PutUint32(buf[i*4:], math.Float32bits(v))
	}
	return buf, nil
}

// deserializeVector converts bytes back to a float32 vector.
func deserializeVector(data []byte) ([]float32, error) {
	if len(data)%4 != 0 {
		return nil, fmt.Errorf("invalid vector data length: %d", len(data))
	}
	vector := make([]float32, len(data)/4)
	for i := range vector {
		vector[i] = math.Float32frombits(binary.LittleEndian.Uint32(data[i*4:]))
	}
	return vector, nil
}

// computeTextHash computes a hash of the text for deduplication.
func computeTextHash(text string) string {
	h := fnv.New64a()
	h.Write([]byte(text))
	return fmt.Sprintf("%x", h.Sum64())
}

// enqueueEmbedding adds an embedding request to the queue if embedding is enabled.
func (s *memoryService) enqueueEmbedding(episodeID, text string) {
	if s.embedFunc == nil || !s.embedConfig.Enabled {
		return
	}

	textHash := computeTextHash(text)
	select {
	case s.embedQueue <- embeddingRequest{
		episodeID: episodeID,
		text:      text,
		textHash:  textHash,
	}:
	default:
		// Queue is full, log and skip
		logging.Warn("Embedding queue full, skipping embedding generation",
			"episode_id", episodeID)
	}
}

// getEpisodeEmbedding retrieves the embedding for an episode.
// It checks the in-memory cache first if VectorCacheEnabled is true.
func (s *memoryService) getEpisodeEmbedding(ctx context.Context, episodeID string) ([]float32, error) {
	// Check cache first if enabled
	if s.embedConfig.VectorCacheEnabled {
		if cached, ok := s.embedCache.Load(episodeID); ok {
			s.metricsMu.Lock()
			s.embedMetrics.TotalCacheHits++
			s.metricsMu.Unlock()
			return cached.([]float32), nil
		}
	}

	// Fetch from database
	emb, err := s.db.GetEpisodeEmbedding(ctx, episodeID)
	if err != nil {
		return nil, err
	}
	vector, err := deserializeVector(emb.Vector)
	if err != nil {
		return nil, err
	}

	// Store in cache if enabled
	if s.embedConfig.VectorCacheEnabled {
		s.embedCache.Store(episodeID, vector)
	}

	return vector, nil
}

// textToString converts an episode's task/actions/outcome to a single text for embedding.
func episodeToText(episode Episode) string {
	var parts []string

	// Add task description
	if episode.Task != nil {
		if taskJSON, err := json.Marshal(episode.Task); err == nil {
			parts = append(parts, string(taskJSON))
		}
	}

	// Add actions
	if len(episode.Actions) > 0 {
		if actionsJSON, err := json.Marshal(episode.Actions); err == nil {
			parts = append(parts, string(actionsJSON))
		}
	}

	// Add outcome
	if episode.Outcome != "" {
		parts = append(parts, episode.Outcome)
	}

	// Add feedback if present
	if episode.Feedback != nil {
		if feedbackJSON, err := json.Marshal(episode.Feedback); err == nil {
			parts = append(parts, string(feedbackJSON))
		}
	}

	return strings.Join(parts, " ")
}
