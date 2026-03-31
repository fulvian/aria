package core

import (
	"context"
	"testing"

	"github.com/fulvian/aria/internal/aria/memory"
)

func TestRoutingLearner_AnalyzeAndAdjust(t *testing.T) {
	// Test with mock memory service
	mockMemory := &mockMemoryService{
		episodes: generateTestEpisodes(20),
	}

	learner := NewRoutingLearner(mockMemory, &mockPolicyRouter{})

	err := learner.AnalyzeAndAdjust(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Verify policy was adjusted
	if learner.GetLastAnalysis().IsZero() {
		t.Error("expected lastAnalysis to be updated")
	}
}

func TestRoutingLearner_ShouldAdjust(t *testing.T) {
	learner := NewRoutingLearner(nil, nil)

	// Should adjust on first call
	if !learner.ShouldAdjust() {
		t.Error("expected ShouldAdjust to return true on first call")
	}
}

func TestCalculateAgencyStats(t *testing.T) {
	episodes := []memory.Episode{
		{AgencyID: "knowledge", Outcome: "success"},
		{AgencyID: "knowledge", Outcome: "success"},
		{AgencyID: "knowledge", Outcome: "failure"},
		{AgencyID: "development", Outcome: "success"},
	}

	stats := calculateAgencyStats(episodes)

	if stats["knowledge"].total != 3 {
		t.Errorf("expected knowledge total=3, got %d", stats["knowledge"].total)
	}
	if stats["knowledge"].successes != 2 {
		t.Errorf("expected knowledge successes=2, got %d", stats["knowledge"].successes)
	}
}

type mockMemoryService struct {
	episodes []memory.Episode
}

func (m *mockMemoryService) GetRecentEpisodes(ctx context.Context, limit int) ([]memory.Episode, error) {
	return m.episodes, nil
}

type mockPolicyRouter struct{}

func (m *mockPolicyRouter) BoostAgencyConfidence(agency string, boost float64)    {}
func (m *mockPolicyRouter) ReduceAgencyConfidence(agency string, penalty float64) {}

func generateTestEpisodes(count int) []memory.Episode {
	episodes := make([]memory.Episode, count)
	for i := 0; i < count; i++ {
		outcome := "success"
		if i%5 == 0 {
			outcome = "failure"
		}
		episodes[i] = memory.Episode{
			AgencyID: "knowledge",
			Outcome:  outcome,
		}
	}
	return episodes
}
