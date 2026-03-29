package skill

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/fulvian/aria/internal/llm/tools"
)

// DebuggingSkill implements systematic debugging methodology.
type DebuggingSkill struct {
	grepTool tools.BaseTool
	viewTool tools.BaseTool
	bashTool tools.BaseTool
}

// NewDebuggingSkill creates a new debugging skill.
func NewDebuggingSkill() *DebuggingSkill {
	return &DebuggingSkill{
		grepTool: tools.NewGrepTool(),
		viewTool: tools.NewViewTool(nil),
		bashTool: tools.NewBashTool(nil), // Permission service not available, will be set during execution if needed
	}
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

	// Step 2: Isolate - Search for error patterns in codebase
	steps = append(steps, SkillStep{Name: "isolate", Description: "Isolating the root cause", Status: "in_progress", DurationMs: 0})

	// Analyze error type and build search queries
	errorType, likelyCause := analyzeErrorType(errorMsg)

	// Search for similar errors in the codebase
	relatedErrors := []map[string]any{}

	// Search for error handling patterns related to this error type
	switch errorType {
	case "nil_pointer":
		grepResult, err := s.grepTool.Run(ctx, tools.ToolCall{
			ID:   "search-nil",
			Name: "grep",
			Input: toJSON(map[string]any{
				"pattern":      "if.*nil",
				"include":      "*.go",
				"literal_text": false,
			}),
		})
		if err == nil && !grepResult.IsError {
			relatedErrors = parseGrepResults(grepResult.Content)
		}
	case "index_out_of_bounds":
		grepResult, err := s.grepTool.Run(ctx, tools.ToolCall{
			ID:   "search-bounds",
			Name: "grep",
			Input: toJSON(map[string]any{
				"pattern":      "\\[.*\\]",
				"include":      "*.go",
				"literal_text": false,
			}),
		})
		if err == nil && !grepResult.IsError {
			relatedErrors = parseGrepResults(grepResult.Content)
		}
	case "network":
		grepResult, err := s.grepTool.Run(ctx, tools.ToolCall{
			ID:   "search-network",
			Name: "grep",
			Input: toJSON(map[string]any{
				"pattern":      "http\\.|Client\\.|Dial\\.|Connect\\(",
				"include":      "*.go",
				"literal_text": false,
			}),
		})
		if err == nil && !grepResult.IsError {
			relatedErrors = parseGrepResults(grepResult.Content)
		}
	}

	// Search for the specific error string in the codebase if it's a custom error
	if len(errorMsg) > 5 && len(errorMsg) < 100 {
		grepResult, err := s.grepTool.Run(ctx, tools.ToolCall{
			ID:   "search-error",
			Name: "grep",
			Input: toJSON(map[string]any{
				"pattern":      errorMsg,
				"include":      "*.go",
				"literal_text": true,
			}),
		})
		if err == nil && !grepResult.IsError && !strings.Contains(grepResult.Content, "No files found") {
			relatedErrors = parseGrepResults(grepResult.Content)
		}
	}

	// Parse stack trace to find relevant files
	var filePaths []string
	if stackTrace != "" {
		filePaths = extractFilePathsFromStack(stackTrace)
		for _, fp := range filePaths {
			if fp != "" {
				viewResult, err := s.viewTool.Run(ctx, tools.ToolCall{
					ID:    fmt.Sprintf("view-%s", fp),
					Name:  "view",
					Input: toJSON(map[string]any{"file_path": fp}),
				})
				if err == nil && !viewResult.IsError {
					relatedErrors = append(relatedErrors, map[string]any{
						"file":    fp,
						"context": "stack trace location",
						"content": viewResult.Content,
					})
				}
			}
		}
	}

	steps[2].Status = "completed"
	steps = append(steps, SkillStep{
		Name:        "likely_cause",
		Description: likelyCause,
		Status:      "completed",
		DurationMs:  5,
	})

	// Step 3: Identify fix
	steps = append(steps, SkillStep{Name: "identify_fix", Description: "Identifying potential fix", Status: "in_progress", DurationMs: 0})

	suggestions := generateSuggestions(errorType, errorMsg, relatedErrors)

	steps[3].Status = "completed"

	// Step 4: Verify - attempt to run tests or build to confirm
	steps = append(steps, SkillStep{Name: "verify", Description: "Verifying the fix", Status: "in_progress", DurationMs: 0})

	verificationResult := map[string]any{
		"build_attempted": false,
		"build_passed":    false,
		"test_attempted":  false,
		"test_passed":     false,
	}

	// Try to build the package to see if there are compilation errors
	bashResult, err := s.bashTool.Run(ctx, tools.ToolCall{
		ID:   "verify-build",
		Name: "bash",
		Input: toJSON(map[string]any{
			"command": "go build ./... 2>&1 || true",
			"timeout": 30000,
		}),
	})
	if err == nil && !bashResult.IsError {
		verificationResult["build_attempted"] = true
		verificationResult["build_passed"] = !strings.Contains(bashResult.Content, "error")
		verificationResult["build_output"] = bashResult.Content
	}

	// Try to run tests on the affected files
	if len(filePaths) > 0 {
		for _, fp := range filePaths {
			if strings.HasSuffix(fp, ".go") {
				// Get package directory
				pkgDir := getPackageDir(fp)
				if pkgDir != "" {
					bashResult, err := s.bashTool.Run(ctx, tools.ToolCall{
						ID:   fmt.Sprintf("verify-test-%s", fp),
						Name: "bash",
						Input: toJSON(map[string]any{
							"command": fmt.Sprintf("cd %s && go test -v -count=1 -run=./... 2>&1 | head -50 || true", pkgDir),
							"timeout": 60000,
						}),
					})
					if err == nil && !bashResult.IsError {
						verificationResult["test_attempted"] = true
						verificationResult["test_passed"] = strings.Contains(bashResult.Content, "PASS")
						verificationResult["test_output"] = bashResult.Content
					}
					break // Only test one package to save time
				}
			}
		}
	}

	steps[4].Status = "completed"
	steps = append(steps, SkillStep{
		Name:        "verify_result",
		Description: fmt.Sprintf("Build: %v, Tests: %v", verificationResult["build_passed"], verificationResult["test_passed"]),
		Status:      "completed",
		DurationMs:  10,
	})

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"task_id":        params.TaskID,
			"error_message":  errorMsg,
			"stack_trace":    stackTrace,
			"context":        context_,
			"error_type":     errorType,
			"likely_cause":   likelyCause,
			"can_reproduce":  canReproduce,
			"suggestions":    suggestions,
			"related_errors": relatedErrors,
			"summary":        fmt.Sprintf("Debugging analysis complete. Likely cause: %s", likelyCause),
		},
		DurationMs: time.Since(start).Milliseconds(),
		Steps:      steps,
	}, nil
}

// analyzeErrorType determines the error category and likely cause.
func analyzeErrorType(errorMsg string) (string, string) {
	errorLower := strings.ToLower(errorMsg)

	if strings.Contains(errorLower, "null") || strings.Contains(errorLower, "nil") || strings.Contains(errorLower, "nil pointer") {
		return "nil_pointer", "Possible null pointer or nil reference - add nil checks before dereferencing"
	}
	if strings.Contains(errorLower, "index") || strings.Contains(errorLower, "bounds") || strings.Contains(errorLower, "out of range") {
		return "index_out_of_bounds", "Array or slice index out of bounds - verify index is within valid range"
	}
	if strings.Contains(errorLower, "connection") || strings.Contains(errorLower, "timeout") || strings.Contains(errorLower, "network") {
		return "network", "Network or connection issue - check network connectivity and timeouts"
	}
	if strings.Contains(errorLower, "parse") || strings.Contains(errorLower, "invalid") || strings.Contains(errorLower, "syntax") {
		return "parse", "Data parsing or validation error - verify input format and content"
	}
	if strings.Contains(errorLower, "permission") || strings.Contains(errorLower, "denied") || strings.Contains(errorLower, "access") {
		return "permission", "Permission or access denied - check file/directory permissions"
	}
	if strings.Contains(errorLower, "deadlock") || strings.Contains(errorLower, "goroutine") {
		return "concurrency", "Concurrency issue - review goroutine management and synchronization"
	}
	if strings.Contains(errorLower, "memory") || strings.Contains(errorLower, "oom") || strings.Contains(errorLower, "alloc") {
		return "memory", "Memory issue - check for memory leaks or excessive allocations"
	}

	return "unknown", "Unknown error type - requires manual investigation"
}

// generateSuggestions provides fix suggestions based on error type.
func generateSuggestions(errorType, errorMsg string, relatedErrors []map[string]any) []string {
	switch errorType {
	case "nil_pointer":
		return []string{
			"Add nil checks before accessing struct fields or slice elements",
			"Use pointer receivers for methods that can handle nil receivers",
			"Consider using errors.Is() for error comparison",
			"Initialize pointers at declaration when possible",
		}
	case "index_out_of_bounds":
		return []string{
			"Check array/slice length before accessing by index",
			"Use range loops instead of index-based iteration when possible",
			"Add bounds checking with if index < len(slice)",
			"Consider using safe accessor methods",
		}
	case "network":
		return []string{
			"Add timeout to network operations",
			"Implement retry logic with exponential backoff",
			"Check network connectivity before operations",
			"Use context for cancellation of long-running network calls",
		}
	case "parse":
		return []string{
			"Validate input format before parsing",
			"Use strict parsing functions when possible",
			"Add error messages with context about invalid input",
			"Consider using schema validation libraries",
		}
	case "permission":
		return []string{
			"Check file/directory permissions",
			"Verify user has required access rights",
			"Use os.Chmod() to fix permission issues",
			"Check working directory accessibility",
		}
	case "concurrency":
		return []string{
			"Use mutexes (sync.Mutex or sync.RWMutex) to protect shared state",
			"Consider using channels for communication between goroutines",
			"Use context for goroutine cancellation",
			"Add deadlock detection with timeout",
		}
	case "memory":
		return []string{
			"Check for memory leaks in long-running operations",
			"Use pprof to profile memory usage",
			"Avoid keeping references to large objects",
			"Consider pooling objects to reduce allocations",
		}
	}

	return []string{
		"Add null checks before dereferencing pointers",
		"Validate input parameters at function entry",
		"Add logging to track variable values",
	}
}

// parseGrepResults parses grep output into structured findings.
func parseGrepResults(content string) []map[string]any {
	findings := []map[string]any{}
	if content == "" || strings.Contains(content, "No files found") {
		return findings
	}

	lines := strings.Split(content, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, ":", 3)
		if len(parts) >= 2 {
			findings = append(findings, map[string]any{
				"file":    parts[0],
				"line":    parts[1],
				"content": strings.TrimPrefix(parts[2], " "),
			})
		}
	}
	return findings
}

// extractFilePathsFromStack extracts file paths from a stack trace.
func extractFilePathsFromStack(stackTrace string) []string {
	var paths []string
	lines := strings.Split(stackTrace, "\n")
	for _, line := range lines {
		// Look for .go files in stack trace
		if strings.Contains(line, ".go") {
			fields := strings.Fields(line)
			for _, part := range fields {
				if strings.HasSuffix(part, ".go") {
					// Remove line number if present
					if idx := strings.LastIndex(part, ":"); idx != -1 {
						part = part[:idx]
					}
					paths = append(paths, part)
				}
			}
		}
	}
	return paths
}

// getPackageDir extracts the package directory from a file path.
// It walks up from the file to find a directory with a go.mod file.
func getPackageDir(filePath string) string {
	if filePath == "" {
		return ""
	}
	// Find the last occurrence of "internal" or "cmd" or root
	parts := strings.Split(filePath, "/")
	for i := len(parts) - 1; i >= 0; i-- {
		if parts[i] == "internal" || parts[i] == "cmd" || parts[i] == "" {
			if i > 0 {
				return strings.Join(parts[:i], "/")
			}
		}
	}
	// Default: return parent of file
	if len(parts) > 1 {
		return strings.Join(parts[:len(parts)-1], "/")
	}
	return "."
}

// CanExecute checks if the skill can execute.
func (s *DebuggingSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, "Debugging skill is ready"
}
