package memory

import (
	"testing"
	"time"
)

// BenchmarkCalculateProcedureScore benchmarks the procedure scoring function.
func BenchmarkCalculateProcedureScore(b *testing.B) {
	proc := Procedure{
		Trigger: TriggerCondition{
			Type:    "task_type",
			Pattern: "code_review",
		},
		SuccessRate: 0.9,
		UseCount:    50,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		calculateProcedureScore(proc, "code_review", "Please review this code for bugs")
	}
}

// BenchmarkRankEpisodes benchmarks episode ranking.
func BenchmarkRankEpisodes(b *testing.B) {
	episodes := make([]Episode, 100)
	now := time.Now()
	for i := 0; i < 100; i++ {
		outcome := "success"
		if i%3 == 0 {
			outcome = "failure"
		} else if i%5 == 0 {
			outcome = "partial"
		}
		episodes[i] = Episode{
			Outcome:   outcome,
			Timestamp: now.Add(-time.Duration(i) * time.Hour),
		}
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		rankEpisodes(episodes)
	}
}

// BenchmarkCalculateProcedureScore_HighVolume benchmarks scoring with many procedures.
func BenchmarkCalculateProcedureScore_HighVolume(b *testing.B) {
	procs := make([]Procedure, 100)
	for i := 0; i < 100; i++ {
		procs[i] = Procedure{
			Trigger: TriggerCondition{
				Type:    "task_type",
				Pattern: "code_review",
			},
			SuccessRate: 0.5 + float64(i%50)/100.0,
			UseCount:    int64(i * 10),
		}
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		for _, proc := range procs {
			calculateProcedureScore(proc, "code_review", "Please review this code")
		}
	}
}

// BenchmarkFilterEpisodes benchmarks episode filtering.
func BenchmarkFilterEpisodes(b *testing.B) {
	episodes := make([]Episode, 100)
	now := time.Now()
	for i := 0; i < 100; i++ {
		episodes[i] = Episode{
			ID:        "ep-1",
			SessionID: "session-1",
			AgencyID:  "agency-1",
			AgentID:   "agent-1",
			Outcome:   "success",
			Timestamp: now.Add(-time.Duration(i) * time.Hour),
			Task:      map[string]any{"type": "code_review"},
		}
	}

	query := EpisodeQuery{
		AgencyID: "agency-1",
		AgentID:  "agent-1",
		TaskType: "code_review",
		Limit:    50,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		filterEpisodes(episodes, query)
	}
}
