package plan

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestDefaultSequentialThinkingConfig(t *testing.T) {
	config := DefaultSequentialThinkingConfig()

	assert.Equal(t, "npx", config.Command)
	assert.Equal(t, []string{"-y", "@modelcontextprotocol/server-sequential-thinking"}, config.Args)
	assert.Equal(t, 12000, config.TimeoutMs)
	assert.Equal(t, 12, config.MaxThoughts)
	assert.Nil(t, config.Env)
}

func TestSequentialThinkingConfigWithEnv(t *testing.T) {
	config := SequentialThinkingConfig{
		Command:     "node",
		Args:        []string{"server.js"},
		Env:         []string{"DEBUG=true", "LOG_LEVEL=info"},
		TimeoutMs:   6000,
		MaxThoughts: 6,
	}

	assert.Equal(t, "node", config.Command)
	assert.Equal(t, []string{"server.js"}, config.Args)
	assert.Equal(t, []string{"DEBUG=true", "LOG_LEVEL=info"}, config.Env)
	assert.Equal(t, 6000, config.TimeoutMs)
	assert.Equal(t, 6, config.MaxThoughts)
}

func TestNewSequentialThinkingCaller(t *testing.T) {
	config := DefaultSequentialThinkingConfig()
	caller := NewSequentialThinkingCaller(config)

	assert.NotNil(t, caller)
	assert.Equal(t, config, caller.config)
}

func TestBuildInitialThought(t *testing.T) {
	query := "Refactor the user authentication module"
	complexity := 75
	risk := 40

	thought := buildInitialThought(query, complexity, risk)

	assert.Contains(t, thought, query)
	assert.Contains(t, thought, "Complexity: 75/100")
	assert.Contains(t, thought, "Risk: 40/100")
	assert.Contains(t, thought, "ARIA orchestrator planning")
}

func TestBuildFollowUpThought(t *testing.T) {
	query := "Implement new feature"
	previousThoughts := []string{
		"First analysis: needs context loading",
		"Second analysis: plan created",
	}

	thought := buildFollowUpThought(query, previousThoughts)

	assert.Contains(t, thought, query)
	assert.Contains(t, thought, "First analysis: needs context loading")
	assert.Contains(t, thought, "Second analysis: plan created")
	assert.Contains(t, thought, "Continue analysis")
}

func TestBuildDeliberationResult(t *testing.T) {
	thoughts := []string{
		"1) First step: analyze the task\nRisk: may timeout\nFallback: use cached result",
		"2) Second step: execute plan\nDone: when complete",
	}

	result := buildDeliberationResult(thoughts)

	assert.NotNil(t, result)
	assert.True(t, len(result.Steps) > 0)
	assert.True(t, len(result.Risks) > 0)
	assert.True(t, len(result.Fallbacks) > 0)
	assert.NotEmpty(t, result.DoneCriteria)
}

func TestBuildDeliberationResultEmptyThoughts(t *testing.T) {
	thoughts := []string{}

	result := buildDeliberationResult(thoughts)

	assert.NotNil(t, result)
	assert.Equal(t, 0.7, result.Confidence)
}

func TestBuildDeliberationResultWithSteps(t *testing.T) {
	thoughts := []string{
		"Step 1: analyze requirements",
		"Step 2: implement solution",
		"Step 3: verify output",
	}

	result := buildDeliberationResult(thoughts)

	// Parser should detect steps
	assert.True(t, len(result.Steps) >= 3)
}

func TestBuildDeliberationResultWithRisks(t *testing.T) {
	thoughts := []string{
		"Consider the risk of memory failure",
		"Another danger: API timeout",
	}

	result := buildDeliberationResult(thoughts)

	// Parser should detect risks
	assert.True(t, len(result.Risks) >= 2)
}

func TestBuildDeliberationResultConfidence(t *testing.T) {
	thoughts := []string{}

	result := buildDeliberationResult(thoughts)

	// Default confidence should be 0.7
	assert.Equal(t, 0.7, result.Confidence)
}

func TestBuildDeliberationResultFallbacks(t *testing.T) {
	thoughts := []string{
		"Use fallback strategy if primary fails",
		"Alternative approach available",
	}

	result := buildDeliberationResult(thoughts)

	// Parser should detect fallbacks
	assert.True(t, len(result.Fallbacks) >= 2)
}

func TestBuildDeliberationResultDoneCriteria(t *testing.T) {
	thoughts := []string{
		"Done when all tests pass",
		"Done upon user approval",
	}

	result := buildDeliberationResult(thoughts)

	assert.NotEmpty(t, result.DoneCriteria)
	assert.Contains(t, result.DoneCriteria, "Done")
}

func TestBuildDeliberationResultStepsFallback(t *testing.T) {
	// When no keywords are found, all thoughts should become steps
	thoughts := []string{
		"Just some random analysis text without keywords",
	}

	result := buildDeliberationResult(thoughts)

	// When no steps detected but thoughts exist, thoughts become steps
	assert.True(t, len(result.Steps) > 0)
}
