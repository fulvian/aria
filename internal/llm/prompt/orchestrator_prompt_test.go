package prompt

import (
	"strings"
	"testing"

	"github.com/fulvian/aria/internal/llm/models"
	"github.com/stretchr/testify/assert"
)

func TestPlannerPrompt_Format(t *testing.T) {
	t.Parallel()

	ctx := PlanContext{
		Query:      "Refactor the user authentication module",
		Complexity: 75,
		RiskLevel:  "medium",
		Domain:     "development",
		Intent:     "task",
	}

	prompt := PlannerPrompt(models.ProviderAnthropic, ctx)

	// Verify required sections are present
	assert.Contains(t, prompt, "ARIA Planner", "should contain ARIA Planner role")
	assert.Contains(t, prompt, "Objective Normalization", "should contain objective normalization section")
	assert.Contains(t, prompt, "Steps Generation", "should contain steps generation section")
	assert.Contains(t, prompt, "Hypotheses", "should contain hypotheses section")
	assert.Contains(t, prompt, "Risks", "should contain risks section")
	assert.Contains(t, prompt, "Fallbacks", "should contain fallbacks section")
	assert.Contains(t, prompt, "Done Criteria", "should contain done criteria section")
	assert.Contains(t, prompt, "Output Format", "should mention output format")
}

func TestPlannerPrompt_Context(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name           string
		ctx            PlanContext
		expectInPrompt []string
	}{
		{
			name: "contains query context",
			ctx: PlanContext{
				Query:      "Test query",
				Complexity: 50,
				RiskLevel:  "low",
				Domain:     "development",
				Intent:     "task",
			},
			expectInPrompt: []string{"Test query", "50", "low", "development", "task"},
		},
		{
			name: "contains high complexity",
			ctx: PlanContext{
				Query:      "Complex refactoring",
				Complexity: 85,
				RiskLevel:  "high",
				Domain:     "development",
				Intent:     "planning",
			},
			expectInPrompt: []string{"85", "high", "planning"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			prompt := PlannerPrompt(models.ProviderAnthropic, tt.ctx)
			for _, expected := range tt.expectInPrompt {
				assert.Contains(t, prompt, expected, "prompt should contain expected value")
			}
		})
	}
}

func TestPlannerPrompt_Role(t *testing.T) {
	t.Parallel()

	ctx := PlanContext{
		Query:      "Test query",
		Complexity: 50,
		RiskLevel:  "low",
		Domain:     "general",
		Intent:     "question",
	}

	prompt := PlannerPrompt(models.ProviderAnthropic, ctx)

	// Verify role is clearly defined
	assert.True(t, strings.Contains(prompt, "ARIA Planner") || strings.Contains(prompt, "Planner"),
		"prompt should define the Planner role")
	assert.Contains(t, prompt, "execution plan", "prompt should mention execution plans")
}

func TestPlannerPrompt_OutputSchema(t *testing.T) {
	t.Parallel()

	ctx := PlanContext{
		Query:      "Test query",
		Complexity: 50,
		RiskLevel:  "low",
		Domain:     "general",
		Intent:     "question",
	}

	prompt := PlannerPrompt(models.ProviderAnthropic, ctx)

	// Verify JSON schema elements are present
	assert.Contains(t, prompt, "objective", "should include objective field")
	assert.Contains(t, prompt, "steps", "should include steps field")
	assert.Contains(t, prompt, "hypotheses", "should include hypotheses field")
	assert.Contains(t, prompt, "risks", "should include risks field")
	assert.Contains(t, prompt, "fallbacks", "should include fallbacks field")
	assert.Contains(t, prompt, "done_criteria", "should include done_criteria field")
}

func TestExecutorPrompt_Format(t *testing.T) {
	t.Parallel()

	ctx := ExecutorContext{
		Plan:            "plan-123",
		CurrentStep:     0,
		AvailableAgents: []string{"coder", "summarizer"},
		AvailableTools:  []string{"bash", "edit"},
	}

	prompt := ExecutorPrompt(models.ProviderAnthropic, ctx)

	// Verify required sections are present
	assert.Contains(t, prompt, "ARIA Executor", "should contain ARIA Executor role")
	assert.Contains(t, prompt, "Execute", "should contain execution instructions")
	assert.Contains(t, prompt, "handoff", "should mention handoff protocol")
	assert.Contains(t, prompt, "permission", "should mention permission checks")
	assert.Contains(t, prompt, "guardrail", "should mention guardrail checks")
	assert.Contains(t, prompt, "error", "should mention error handling")
}

func TestExecutorPrompt_Context(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name           string
		ctx            ExecutorContext
		expectInPrompt []string
	}{
		{
			name: "contains plan context",
			ctx: ExecutorContext{
				Plan:            "plan-456",
				CurrentStep:     2,
				AvailableAgents: []string{"coder"},
				AvailableTools:  []string{"bash"},
			},
			expectInPrompt: []string{"plan-456", "2", "coder", "bash"},
		},
		{
			name: "empty agents and tools",
			ctx: ExecutorContext{
				Plan:            "plan-789",
				CurrentStep:     0,
				AvailableAgents: []string{},
				AvailableTools:  []string{},
			},
			expectInPrompt: []string{"plan-789", "0", "No agents available", "No tools available"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			prompt := ExecutorPrompt(models.ProviderAnthropic, tt.ctx)
			for _, expected := range tt.expectInPrompt {
				assert.Contains(t, prompt, expected, "prompt should contain expected value")
			}
		})
	}
}

func TestExecutorPrompt_HandoffProtocol(t *testing.T) {
	t.Parallel()

	ctx := ExecutorContext{
		Plan:            "plan-123",
		CurrentStep:     1,
		AvailableAgents: []string{"coder", "summarizer"},
		AvailableTools:  []string{"bash"},
	}

	prompt := ExecutorPrompt(models.ProviderAnthropic, ctx)

	// Verify handoff protocol is documented
	assert.Contains(t, prompt, "Handoff Protocol", "should have handoff protocol section")
	assert.Contains(t, prompt, "context", "should mention context preservation")
	assert.Contains(t, prompt, "budget", "should mention budget constraints")
}

func TestReviewerPrompt_Format(t *testing.T) {
	t.Parallel()

	ctx := ReviewContext{
		Plan:               "plan-123",
		ExecutionResult:    "success",
		MinAcceptanceScore: 0.75,
	}

	prompt := ReviewerPrompt(models.ProviderAnthropic, ctx)

	// Verify required sections are present
	assert.Contains(t, prompt, "ARIA Reviewer", "should contain ARIA Reviewer role")
	assert.Contains(t, prompt, "acceptance criteria", "should mention acceptance criteria")
	assert.Contains(t, prompt, "APPROVED", "should define APPROVED verdict")
	assert.Contains(t, prompt, "REVISION_NEEDED", "should define REVISION_NEEDED verdict")
	assert.Contains(t, prompt, "REPLAN_NEEDED", "should define REPLAN_NEEDED verdict")
}

func TestReviewerPrompt_AcceptanceCriteria(t *testing.T) {
	t.Parallel()

	ctx := ReviewContext{
		Plan:               "plan-123",
		ExecutionResult:    "success",
		MinAcceptanceScore: 0.75,
	}

	prompt := ReviewerPrompt(models.ProviderAnthropic, ctx)

	// Verify all acceptance criteria are listed with weights
	assert.Contains(t, prompt, "Objective Satisfied", "should have objective criterion")
	assert.Contains(t, prompt, "Constraints Respected", "should have constraints criterion")
	assert.Contains(t, prompt, "Risk Within Threshold", "should have risk criterion")
	assert.Contains(t, prompt, "Evidence Available", "should have evidence criterion")
	assert.Contains(t, prompt, "Fallback Not Triggered", "should have fallback criterion")

	// Verify weights are present
	assert.Contains(t, prompt, "0.30", "should have weight 0.30 for objective")
	assert.Contains(t, prompt, "0.25", "should have weight 0.25 for constraints")
	assert.Contains(t, prompt, "0.20", "should have weight 0.20 for risk")
	assert.Contains(t, prompt, "0.15", "should have weight 0.15 for evidence")
	assert.Contains(t, prompt, "0.10", "should have weight 0.10 for fallback")
}

func TestReviewerPrompt_ScoreThresholds(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name               string
		minAcceptanceScore float64
		expectInPrompt     []string
	}{
		{
			name:               "default threshold 0.75",
			minAcceptanceScore: 0.75,
			expectInPrompt:     []string{"0.75"},
		},
		{
			name:               "custom threshold 0.80",
			minAcceptanceScore: 0.80,
			expectInPrompt:     []string{"0.80"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ctx := ReviewContext{
				Plan:               "plan-123",
				ExecutionResult:    "result",
				MinAcceptanceScore: tt.minAcceptanceScore,
			}
			prompt := ReviewerPrompt(models.ProviderAnthropic, ctx)
			for _, expected := range tt.expectInPrompt {
				assert.Contains(t, prompt, expected, "prompt should contain threshold")
			}
		})
	}
}

func TestReviewerPrompt_VerdictLogic(t *testing.T) {
	t.Parallel()

	ctx := ReviewContext{
		Plan:               "plan-123",
		ExecutionResult:    "execution completed",
		MinAcceptanceScore: 0.75,
	}

	prompt := ReviewerPrompt(models.ProviderAnthropic, ctx)

	// Verify verdict logic is documented
	assert.Contains(t, prompt, "Score >= 0.75", "should document APPROVED threshold")
	assert.Contains(t, prompt, "Score >= 0.50", "should document REVISION_NEEDED threshold")
	assert.Contains(t, prompt, "Score < 0.50", "should document REPLAN_NEEDED threshold")
	assert.Contains(t, prompt, "critical failure", "should mention critical failures")
}

func TestReviewerPrompt_Context(t *testing.T) {
	t.Parallel()

	ctx := ReviewContext{
		Plan:               "plan-abc",
		ExecutionResult:    "Step 0: success\nStep 1: success",
		MinAcceptanceScore: 0.75,
	}

	prompt := ReviewerPrompt(models.ProviderAnthropic, ctx)

	// Verify context is included
	assert.Contains(t, prompt, "plan-abc", "should include plan ID")
	assert.Contains(t, prompt, "0.75", "should include min score")
	assert.Contains(t, prompt, "Step 0: success", "should include execution result")
}

func TestPlannerPrompt_Provider(t *testing.T) {
	t.Parallel()

	ctx := PlanContext{
		Query:      "Test query",
		Complexity: 50,
		RiskLevel:  "low",
		Domain:     "general",
		Intent:     "question",
	}

	// Test with different providers - prompt should be generated (provider-specific prompts reserved for future)
	promptAnthropic := PlannerPrompt(models.ProviderAnthropic, ctx)
	promptOpenAI := PlannerPrompt(models.ProviderOpenAI, ctx)

	assert.NotEmpty(t, promptAnthropic)
	assert.NotEmpty(t, promptOpenAI)
}

func TestExecutorPrompt_Provider(t *testing.T) {
	t.Parallel()

	ctx := ExecutorContext{
		Plan:            "plan-123",
		CurrentStep:     0,
		AvailableAgents: []string{"coder"},
		AvailableTools:  []string{"bash"},
	}

	promptAnthropic := ExecutorPrompt(models.ProviderAnthropic, ctx)
	promptOpenAI := ExecutorPrompt(models.ProviderOpenAI, ctx)

	assert.NotEmpty(t, promptAnthropic)
	assert.NotEmpty(t, promptOpenAI)
}

func TestReviewerPrompt_Provider(t *testing.T) {
	t.Parallel()

	ctx := ReviewContext{
		Plan:               "plan-123",
		ExecutionResult:    "success",
		MinAcceptanceScore: 0.75,
	}

	promptAnthropic := ReviewerPrompt(models.ProviderAnthropic, ctx)
	promptOpenAI := ReviewerPrompt(models.ProviderOpenAI, ctx)

	assert.NotEmpty(t, promptAnthropic)
	assert.NotEmpty(t, promptOpenAI)
}
