package plan

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/fulvian/aria/internal/aria/routing"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestPlan_Structure(t *testing.T) {
	t.Parallel()

	plan := &Plan{
		ID:           "test-plan-1",
		Query:        "Test query",
		Objective:    "Test objective",
		Steps:        []PlanStep{},
		Hypotheses:   []Hypothesis{},
		Risks:        []PlanRisk{},
		Fallbacks:    []FallbackStrategy{},
		DoneCriteria: "completed",
		CreatedAt:    time.Now(),
		Metadata:     map[string]any{"key": "value"},
	}

	assert.NotEmpty(t, plan.ID)
	assert.NotEmpty(t, plan.Query)
	assert.NotEmpty(t, plan.Objective)
	assert.NotEmpty(t, plan.DoneCriteria)
	assert.NotNil(t, plan.Metadata)
}

func TestPlanStep_Structure(t *testing.T) {
	t.Parallel()

	step := PlanStep{
		Index:       0,
		Action:      "execute",
		Target:      "agent",
		Inputs:      map[string]any{"key": "value"},
		ExpectedOut: map[string]any{"result": "ok"},
		Constraints: []string{"constraint1"},
		Timeout:     30 * time.Second,
	}

	assert.Equal(t, 0, step.Index)
	assert.Equal(t, "execute", step.Action)
	assert.Equal(t, "agent", step.Target)
	assert.NotNil(t, step.Inputs)
	assert.NotNil(t, step.ExpectedOut)
	assert.Len(t, step.Constraints, 1)
	assert.Equal(t, 30*time.Second, step.Timeout)
}

func TestHypothesis_Structure(t *testing.T) {
	t.Parallel()

	h := Hypothesis{
		Description: "Test hypothesis",
		Confidence:  0.85,
		Conditions:  []string{"condition1", "condition2"},
	}

	assert.Equal(t, "Test hypothesis", h.Description)
	assert.Equal(t, 0.85, h.Confidence)
	assert.Len(t, h.Conditions, 2)
}

func TestPlanRisk_Structure(t *testing.T) {
	t.Parallel()

	r := PlanRisk{
		Description: "Test risk",
		Probability: 0.3,
		Impact:      "medium",
		Mitigation:  " mitigation plan",
	}

	assert.Equal(t, "Test risk", r.Description)
	assert.Equal(t, 0.3, r.Probability)
	assert.Equal(t, "medium", r.Impact)
	assert.NotEmpty(t, r.Mitigation)
}

func TestFallbackStrategy_Structure(t *testing.T) {
	t.Parallel()

	f := FallbackStrategy{
		Condition: "failed",
		Action:    "retry",
		Target:    "simpler",
	}

	assert.Equal(t, "failed", f.Condition)
	assert.Equal(t, "retry", f.Action)
	assert.Equal(t, "simpler", f.Target)
}

func TestHandoff_Structure(t *testing.T) {
	t.Parallel()

	h := Handoff{
		From: routing.AgentID{
			Name:   "agent1",
			Agency: "agency1",
		},
		To: routing.AgentID{
			Name:   "agent2",
			Agency: "agency2",
		},
		Reason:      "handoff reason",
		ExpectedOut: "expected output",
		Constraints: []string{"constraint1"},
		Budget: HandoffBudget{
			Timeout:    60 * time.Second,
			TokenLimit: 1000,
		},
	}

	assert.Equal(t, "agent1", h.From.Name)
	assert.Equal(t, "agent2", h.To.Name)
	assert.NotEmpty(t, h.Reason)
	assert.NotEmpty(t, h.ExpectedOut)
	assert.Equal(t, 60*time.Second, h.Budget.Timeout)
	assert.Equal(t, 1000, h.Budget.TokenLimit)
}

func TestPlan_Serialization(t *testing.T) {
	t.Parallel()

	original := &Plan{
		ID:        "test-plan-1",
		Query:     "Test query",
		Objective: "Test objective",
		Steps: []PlanStep{
			{
				Index:       0,
				Action:      "execute",
				Target:      "agent",
				Inputs:      map[string]any{"key": "value"},
				ExpectedOut: map[string]any{"result": "ok"},
				Constraints: []string{"constraint1"},
				Timeout:     30 * time.Second,
			},
		},
		Hypotheses: []Hypothesis{
			{
				Description: "Test hypothesis",
				Confidence:  0.85,
				Conditions:  []string{"condition1"},
			},
		},
		Risks: []PlanRisk{
			{
				Description: "Test risk",
				Probability: 0.3,
				Impact:      "medium",
				Mitigation:  "mitigation",
			},
		},
		Fallbacks: []FallbackStrategy{
			{
				Condition: "failed",
				Action:    "retry",
				Target:    "simpler",
			},
		},
		DoneCriteria: "completed",
		CreatedAt:    time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC),
		Metadata:     map[string]any{"key": "value"},
	}

	// Serialize to JSON
	data, err := json.Marshal(original)
	require.NoError(t, err)
	assert.NotEmpty(t, data)

	// Deserialize back
	var restored Plan
	err = json.Unmarshal(data, &restored)
	require.NoError(t, err)

	// Verify fields
	assert.Equal(t, original.ID, restored.ID)
	assert.Equal(t, original.Query, restored.Query)
	assert.Equal(t, original.Objective, restored.Objective)
	assert.Equal(t, original.DoneCriteria, restored.DoneCriteria)
	assert.Len(t, restored.Steps, 1)
	assert.Len(t, restored.Hypotheses, 1)
	assert.Len(t, restored.Risks, 1)
	assert.Len(t, restored.Fallbacks, 1)
}

func TestPlanStep_Serialization(t *testing.T) {
	t.Parallel()

	original := PlanStep{
		Index:       1,
		Action:      "analyze",
		Target:      "context",
		Inputs:      map[string]any{"query": "test"},
		ExpectedOut: map[string]any{"analysis": "done"},
		Constraints: []string{"preserve context"},
		Timeout:     15 * time.Second,
	}

	data, err := json.Marshal(original)
	require.NoError(t, err)

	var restored PlanStep
	err = json.Unmarshal(data, &restored)
	require.NoError(t, err)

	assert.Equal(t, original.Index, restored.Index)
	assert.Equal(t, original.Action, restored.Action)
	assert.Equal(t, original.Target, restored.Target)
}

func TestHandoffBudget_Serialization(t *testing.T) {
	t.Parallel()

	original := HandoffBudget{
		Timeout:    120 * time.Second,
		TokenLimit: 5000,
	}

	data, err := json.Marshal(original)
	require.NoError(t, err)

	var restored HandoffBudget
	err = json.Unmarshal(data, &restored)
	require.NoError(t, err)

	assert.Equal(t, original.Timeout, restored.Timeout)
	assert.Equal(t, original.TokenLimit, restored.TokenLimit)
}
