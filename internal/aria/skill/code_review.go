// Package skill provides implementations of development skills.
package skill

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/fulvian/aria/internal/llm/tools"
)

// CodeReviewSkill implements code review functionality.
type CodeReviewSkill struct {
	grepTool tools.BaseTool
	globTool tools.BaseTool
	viewTool tools.BaseTool
}

// NewCodeReviewSkill creates a new code review skill.
func NewCodeReviewSkill() *CodeReviewSkill {
	return &CodeReviewSkill{
		grepTool: tools.NewGrepTool(),
		globTool: tools.NewGlobTool(),
		viewTool: tools.NewViewTool(nil), // No LSP clients needed for basic view
	}
}

// Name returns the skill name.
func (s *CodeReviewSkill) Name() SkillName {
	return SkillCodeReview
}

// Description returns the skill description.
func (s *CodeReviewSkill) Description() string {
	return "Performs systematic code review for quality, security, and best practices"
}

// RequiredTools returns the tools required by this skill.
func (s *CodeReviewSkill) RequiredTools() []ToolName {
	return []ToolName{"glob", "grep", "view"}
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *CodeReviewSkill) RequiredMCPs() []MCPName {
	return []MCPName{}
}

// Execute performs the code review.
func (s *CodeReviewSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()
	steps := []SkillStep{
		{Name: "analyze_request", Description: "Analyzing code review request", Status: "completed", DurationMs: 10},
		{Name: "gather_files", Description: "Gathering relevant files", Status: "in_progress", DurationMs: 0},
	}

	// Extract files to review from params
	files, ok := params.Input["files"].([]string)
	if !ok {
		// Try to get files from glob pattern
		pattern, _ := params.Input["pattern"].(string)
		if pattern != "" {
			files = nil // Will use glob to find files
		} else {
			files = []string{}
		}
	}

	taskDescription, _ := params.Input["description"].(string)

	// If no files provided but pattern exists, use glob to find files
	if len(files) == 0 {
		pattern, _ := params.Input["pattern"].(string)
		if pattern == "" {
			pattern = "**/*.go" // Default to Go files
		}
		globResult, err := s.globTool.Run(ctx, tools.ToolCall{
			ID:    "glob-1",
			Name:  "glob",
			Input: toJSON(map[string]any{"pattern": pattern}),
		})
		if err == nil && !globResult.IsError {
			// Parse glob results - each line is a file path
			filePaths := strings.Split(globResult.Content, "\n")
			for _, fp := range filePaths {
				fp = strings.TrimSpace(fp)
				if fp != "" && !strings.Contains(fp, "(Results") {
					files = append(files, fp)
				}
			}
		}
	}

	steps[1].Status = "completed"
	steps = append(steps, SkillStep{Name: "review_code", Description: "Reviewing code for issues", Status: "in_progress", DurationMs: 0})

	// Search patterns for common issues
	searchPatterns := []struct {
		pattern     string
		description string
		severity    string
	}{
		{"TODO", "TODO comments found - unimplemented code", "info"},
		{"FIXME", "FIXME comments found - known issues that need fixing", "warning"},
		{"XXX", "XXX comments found - problematic code", "warning"},
		{"panic", "Potential panic statements found", "error"},
		{"nil.*\\.\\w+", "Potential nil dereference (nil field access)", "error"},
		{"error.*return.*nil", "Error handling that returns nil without error", "warning"},
		{"if.*err.*!=.*nil.*return", "Error checking pattern", "info"},
		{"log\\..*Error", "Error logging found", "info"},
		{"fmt\\.Sprintf", "fmt.Sprintf usage - consider fmt.F formats for safety", "info"},
		{"//go:nosplit", "Go nosplit directive - may bypass runtime checks", "info"},
	}

	findings := []map[string]any{}
	filesReviewed := 0

	// Review each file
	for _, file := range files {
		if file == "" {
			continue
		}
		filesReviewed++

		// Search for issues in this file
		for _, sp := range searchPatterns {
			grepResult, err := s.grepTool.Run(ctx, tools.ToolCall{
				ID:   fmt.Sprintf("grep-%s-%d", file, filesReviewed),
				Name: "grep",
				Input: toJSON(map[string]any{
					"pattern": sp.pattern,
					"path":    file,
					"include": "*",
				}),
			})
			if err != nil || grepResult.IsError {
				continue
			}

			// Parse grep results
			lines := strings.Split(grepResult.Content, "\n")
			for _, line := range lines {
				if strings.TrimSpace(line) == "" || strings.Contains(line, "No files found") {
					continue
				}
				// Parse line number and content
				parts := strings.SplitN(line, ":", 3)
				if len(parts) >= 3 {
					findings = append(findings, map[string]any{
						"type":        sp.severity,
						"file":        parts[0],
						"line":        parts[1],
						"message":     strings.TrimSpace(parts[2]),
						"pattern":     sp.pattern,
						"description": sp.description,
						"suggestion":  getSuggestion(sp.pattern),
					})
				}
			}
		}

		// View the file to get more context for concerning patterns
		viewResult, err := s.viewTool.Run(ctx, tools.ToolCall{
			ID:    fmt.Sprintf("view-%d", filesReviewed),
			Name:  "view",
			Input: toJSON(map[string]any{"file_path": file}),
		})
		if err == nil && !viewResult.IsError {
			content := viewResult.Content
			// Check for common code smells
			if strings.Contains(content, "any") {
				findings = append(findings, map[string]any{
					"type":       "info",
					"file":       file,
					"line":       0,
					"message":    "Uses 'any' type - consider using proper generics or specific types",
					"suggestion": "Replace 'any' with concrete types for better type safety",
				})
			}
			if strings.Contains(content, "sync.Mutex") && !strings.Contains(content, "sync.RWMutex") {
				// Check if it's a write-heavy scenario that could benefit from RWMutex
			}
		}
	}

	steps[2].Status = "completed"
	steps = append(steps, SkillStep{Name: "compile_report", Description: "Compiling review report", Status: "completed", DurationMs: 5})

	// Count findings by severity
	errorCount := 0
	warningCount := 0
	infoCount := 0
	for _, f := range findings {
		switch f["type"] {
		case "error":
			errorCount++
		case "warning":
			warningCount++
		default:
			infoCount++
		}
	}

	summary := fmt.Sprintf("Reviewed %d files. Found %d issues (%d errors, %d warnings, %d info).",
		filesReviewed, len(findings), errorCount, warningCount, infoCount)

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"task_id":        params.TaskID,
			"description":    taskDescription,
			"files_reviewed": filesReviewed,
			"findings":       findings,
			"summary":        summary,
			"stats": map[string]int{
				"errors":   errorCount,
				"warnings": warningCount,
				"info":     infoCount,
			},
		},
		DurationMs: time.Since(start).Milliseconds(),
		Steps:      steps,
	}, nil
}

// getSuggestion returns a suggestion based on the pattern found.
func getSuggestion(pattern string) string {
	suggestions := map[string]string{
		"TODO":                     "Implement the TODO item or create a tracking issue",
		"FIXME":                    "Address the FIXME issue before releasing",
		"XXX":                      "Review and refactor the XXX comment",
		"panic":                    "Replace panic with proper error handling",
		"nil.*\\.\\w+":             "Add nil check before accessing fields",
		"error.*return.*nil":       "Return error instead of nil for proper error handling",
		"if.*err.*!=.*nil.*return": "Ensure error handling is consistent",
		"log\\..*Error":            "Consider structured logging with error context",
		"fmt\\.Sprintf":            "Use fmt.F* or strconv for type-safe formatting",
		"//go:nosplit":             "Ensure the function is truly safe for nosplit",
	}
	if s, ok := suggestions[pattern]; ok {
		return s
	}
	return "Review and refactor as needed"
}

// toJSON converts a map to JSON string.
func toJSON(m map[string]any) string {
	b, _ := json.Marshal(m)
	return string(b)
}

// CanExecute checks if the skill can execute.
func (s *CodeReviewSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, "Code review skill is ready"
}
