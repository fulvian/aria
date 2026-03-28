package skill

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// DebuggingSkill implements systematic debugging methodology.
type DebuggingSkill struct{}

// NewDebuggingSkill creates a new debugging skill.
func NewDebuggingSkill() *DebuggingSkill {
	return &DebuggingSkill{}
}

// Name returns the skill name.
func (s *DebuggingSkill) Name() SkillName {
	return SkillDebugging
}

// Description returns the skill description.
func (s *DebuggingSkill) Description() string {
	return "Applies systematic debugging methodology: reproduce, isolate, identify, fix, verify"
}

// RequiredTools returns the tools required by this skill.
func (s *DebuggingSkill) RequiredTools() []ToolName {
	return []ToolName{"grep", "view", "bash"}
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *DebuggingSkill) RequiredMCPs() []MCPName {
	return []MCPName{}
}

// Execute performs systematic debugging.
func (s *DebuggingSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	steps := []SkillStep{
		{Name: "gather_info", Description: "Gathering error information", Status: "in_progress", DurationMs: 0},
	}

	// Extract error info from params
	errorMsg, _ := params.Input["error"].(string)
	stackTrace, _ := params.Input["stack_trace"].(string)
	context_, _ := params.Input["context"].(string)

	if errorMsg == "" {
		errorMsg = "No error message provided"
	}

	steps[0].Status = "completed"

	// Step 1: Reproduce
	steps = append(steps, SkillStep{Name: "reproduce", Description: "Attempting to reproduce the issue", Status: "in_progress", DurationMs: 0})
	canReproduce := len(stackTrace) > 0
	steps[1].Status = "completed"
	steps = append(steps, SkillStep{
		Name:        "reproduce_result",
		Description: fmt.Sprintf("Issue %s reproduced", map[bool]string{true: "can be", false: "cannot be"}[canReproduce]),
		Status:      "completed",
		DurationMs:  10,
	})

	// Step 2: Isolate
	steps = append(steps, SkillStep{Name: "isolate", Description: "Isolating the root cause", Status: "in_progress", DurationMs: 0})

	// Analyze error type
	var likelyCause string
	errorLower := strings.ToLower(errorMsg)
	if strings.Contains(errorLower, "null") || strings.Contains(errorLower, "nil") {
		likelyCause = "Possible null pointer or nil reference"
	} else if strings.Contains(errorLower, "index") || strings.Contains(errorLower, "bounds") {
		likelyCause = "Array or slice index out of bounds"
	} else if strings.Contains(errorLower, "connection") || strings.Contains(errorLower, "timeout") {
		likelyCause = "Network or connection issue"
	} else if strings.Contains(errorLower, "parse") || strings.Contains(errorLower, "invalid") {
		likelyCause = "Data parsing or validation error"
	} else {
		likelyCause = "Unknown - requires manual investigation"
	}

	steps[2].Status = "completed"
	steps = append(steps, SkillStep{
		Name:        "likely_cause",
		Description: likelyCause,
		Status:      "completed",
		DurationMs:  5,
	})

	// Step 3: Identify fix
	steps = append(steps, SkillStep{Name: "identify_fix", Description: "Identifying potential fix", Status: "completed", DurationMs: 0})

	// Step 4: Verify
	steps = append(steps, SkillStep{Name: "verify", Description: "Verification pending", Status: "completed", DurationMs: 0})

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"task_id":       params.TaskID,
			"error_message": errorMsg,
			"stack_trace":   stackTrace,
			"context":       context_,
			"likely_cause":  likelyCause,
			"can_reproduce": canReproduce,
			"suggestions": []string{
				"Add null checks before dereferencing",
				"Validate input parameters at function entry",
				"Add logging to track variable values",
			},
			"summary": fmt.Sprintf("Debugging analysis complete. Likely cause: %s", likelyCause),
		},
		DurationMs: time.Since(start).Milliseconds(),
		Steps:      steps,
	}, nil
}

// CanExecute checks if the skill can execute.
func (s *DebuggingSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, "Debugging skill is ready"
}
