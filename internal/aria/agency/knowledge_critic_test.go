package agency

import (
	"context"
	"testing"

	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewKnowledgeCritic(t *testing.T) {
	t.Run("default threshold", func(t *testing.T) {
		critic := NewKnowledgeCritic(0)
		require.NotNil(t, critic)
		assert.Equal(t, 0.7, critic.qualityThreshold)
	})

	t.Run("custom threshold", func(t *testing.T) {
		critic := NewKnowledgeCritic(0.8)
		require.NotNil(t, critic)
		assert.Equal(t, 0.8, critic.qualityThreshold)
	})
}

func TestKnowledgeCritic_CalculateQualityScore(t *testing.T) {
	critic := NewKnowledgeCritic(0.7)

	tests := []struct {
		name     string
		result   map[string]any
		minScore float64
		maxScore float64
	}{
		{
			name:     "empty result",
			result:   map[string]any{},
			minScore: 0.3,
			maxScore: 0.3,
		},
		{
			name: "result with multiple results",
			result: map[string]any{
				"results": []any{
					map[string]any{"title": "Test 1", "url": "https://example.com/1"},
					map[string]any{"title": "Test 2", "url": "https://example.com/2"},
					map[string]any{"title": "Test 3", "url": "https://example.com/3"},
				},
			},
			minScore: 0.5,
			maxScore: 0.61,
		},
		{
			name: "result with summary",
			result: map[string]any{
				"summary": "This is a detailed summary that is longer than fifty characters for the quality boost",
			},
			minScore: 0.44,
			maxScore: 0.5,
		},
		{
			name: "result with source",
			result: map[string]any{
				"source": "https://example.com",
			},
			minScore: 0.4,
			maxScore: 0.45,
		},
		{
			name: "result with count",
			result: map[string]any{
				"count": 5,
			},
			minScore: 0.35,
			maxScore: 0.4,
		},
		{
			name: "result with all quality attributes",
			result: map[string]any{
				"results": []any{
					map[string]any{"title": "Test 1", "url": "https://example.com/1"},
					map[string]any{"title": "Test 2", "url": "https://example.com/2"},
				},
				"summary": "This is a detailed summary that exceeds the fifty character minimum",
				"source":  "https://example.com",
				"count":   2,
			},
			minScore: 0.7,
			maxScore: 0.9,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			score := critic.calculateQualityScore(tt.result)
			assert.GreaterOrEqual(t, score, tt.minScore)
			assert.LessOrEqual(t, score, tt.maxScore)
		})
	}
}

func TestKnowledgeCritic_AssessConfidence(t *testing.T) {
	critic := NewKnowledgeCritic(0.7)

	tests := []struct {
		name    string
		result  map[string]any
		minConf float64
		maxConf float64
	}{
		{
			name:    "empty result",
			result:  map[string]any{},
			minConf: 0.5,
			maxConf: 0.5,
		},
		{
			name: "multiple sources increase confidence",
			result: map[string]any{
				"results": []any{
					map[string]any{"title": "Test 1"},
					map[string]any{"title": "Test 2"},
					map[string]any{"title": "Test 3"},
				},
			},
			minConf: 0.7,
			maxConf: 0.8,
		},
		{
			name: "source metadata increases confidence",
			result: map[string]any{
				"source": "https://example.com",
			},
			minConf: 0.6,
			maxConf: 0.7,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			conf := critic.assessConfidence(tt.result)
			assert.GreaterOrEqual(t, conf, tt.minConf)
			assert.LessOrEqual(t, conf, tt.maxConf)
		})
	}
}

func TestKnowledgeCritic_DetectContradictions(t *testing.T) {
	critic := NewKnowledgeCritic(0.7)

	tests := []struct {
		name          string
		result        map[string]any
		expectCount   int
		expectContain string
	}{
		{
			name:        "no contradictions",
			result:      map[string]any{},
			expectCount: 0,
		},
		{
			name: "same URL same content",
			result: map[string]any{
				"results": []any{
					map[string]any{"url": "https://example.com", "description": "Same content"},
					map[string]any{"url": "https://example.com", "description": "Same content"},
				},
			},
			expectCount: 0,
		},
		{
			name: "different URLs no contradiction",
			result: map[string]any{
				"results": []any{
					map[string]any{"url": "https://example.com/1", "description": "Content 1"},
					map[string]any{"url": "https://example.com/2", "description": "Content 2"},
				},
			},
			expectCount: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			contradictions := critic.detectContradictions(tt.result)
			assert.Len(t, contradictions, tt.expectCount)
			if tt.expectContain != "" {
				assert.Contains(t, contradictions[0], tt.expectContain)
			}
		})
	}
}

func TestKnowledgeCritic_ValidateCitations(t *testing.T) {
	critic := NewKnowledgeCritic(0.7)

	tests := []struct {
		name  string
		valid bool
	}{
		{
			name:  "empty result",
			valid: false,
		},
		{
			name:  "all valid URLs",
			valid: true,
		},
		{
			name:  "no valid URLs",
			valid: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var result map[string]any
			switch tt.name {
			case "all valid URLs":
				result = map[string]any{
					"results": []any{
						map[string]any{"url": "https://example.com/1"},
						map[string]any{"url": "https://example.com/2"},
					},
				}
			case "no valid URLs":
				result = map[string]any{
					"results": []any{
						map[string]any{"url": "not-a-url"},
						map[string]any{"url": ""},
					},
				}
			default:
				result = map[string]any{}
			}
			valid := critic.validateCitations(result)
			assert.Equal(t, tt.valid, valid)
		})
	}
}

func TestKnowledgeCritic_Review(t *testing.T) {
	critic := NewKnowledgeCritic(0.7)
	ctx := context.Background()
	task := contracts.Task{ID: "test-task", Name: "Test Task"}

	t.Run("low quality result fails gate", func(t *testing.T) {
		result := map[string]any{
			"results": []any{},
		}
		review := critic.Review(ctx, task, result)
		assert.False(t, review.Pass)
		assert.False(t, review.PassesGate())
	})

	t.Run("high quality result passes gate", func(t *testing.T) {
		result := map[string]any{
			"results": []any{
				map[string]any{"title": "Test 1", "url": "https://example.com/1", "description": "Description one"},
				map[string]any{"title": "Test 2", "url": "https://example.com/2", "description": "Description two"},
				map[string]any{"title": "Test 3", "url": "https://example.com/3", "description": "Description three"},
			},
			"summary": "This is a comprehensive summary that provides detailed information about the topic",
			"source":  "https://source.example.com",
			"count":   3,
		}
		review := critic.Review(ctx, task, result)
		assert.True(t, review.Pass)
		assert.True(t, review.PassesGate())
		assert.NotEmpty(t, review.Reasons)
	})

	t.Run("result with contradictions fails gate", func(t *testing.T) {
		result := map[string]any{
			"results": []any{
				map[string]any{"title": "Test 1", "url": "https://example.com", "description": "Content A"},
				map[string]any{"title": "Test 2", "url": "https://example.com", "description": "Completely different content"},
			},
			"summary": "This is a summary that is definitely longer than fifty characters",
			"source":  "https://source.example.com",
		}
		review := critic.Review(ctx, task, result)
		assert.False(t, review.Pass)
		assert.Len(t, review.Contradictions, 1)
	})
}

func TestIsValidURL(t *testing.T) {
	tests := []struct {
		url      string
		expected bool
	}{
		{"https://example.com", true},
		{"http://example.com", true},
		{"ftp://example.com", false},
		{"example.com", false},
		{"", false},
		{"not-a-url", false},
	}

	for _, tt := range tests {
		t.Run(tt.url, func(t *testing.T) {
			result := isValidURL(tt.url)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestReviewResult_PassesGate(t *testing.T) {
	t.Run("pass true returns true", func(t *testing.T) {
		result := &ReviewResult{Pass: true}
		assert.True(t, result.PassesGate())
	})

	t.Run("pass false returns false", func(t *testing.T) {
		result := &ReviewResult{Pass: false}
		assert.False(t, result.PassesGate())
	})
}
