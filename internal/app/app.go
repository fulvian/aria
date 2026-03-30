package app

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"maps"
	"strings"
	"sync"
	"time"

	"github.com/fulvian/aria/internal/aria/core"
	"github.com/fulvian/aria/internal/aria/core/decision"
	"github.com/fulvian/aria/internal/aria/core/plan"
	"github.com/fulvian/aria/internal/aria/routing"
	"github.com/fulvian/aria/internal/config"
	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/format"
	"github.com/fulvian/aria/internal/history"
	"github.com/fulvian/aria/internal/llm/agent"
	"github.com/fulvian/aria/internal/logging"
	"github.com/fulvian/aria/internal/lsp"
	"github.com/fulvian/aria/internal/message"
	"github.com/fulvian/aria/internal/permission"
	"github.com/fulvian/aria/internal/session"
	"github.com/fulvian/aria/internal/tui/theme"
)

type App struct {
	Sessions    session.Service
	Messages    message.Service
	History     history.Service
	Permissions permission.Service

	CoderAgent agent.Service

	// DB is the database querier for components that need direct DB access
	DB db.Querier

	LSPClients map[string]*lsp.Client

	// ARIA components (nil when aria.enabled = false)
	ARIA *ARIAComponents

	clientsMutex sync.RWMutex

	watcherCancelFuncs []context.CancelFunc
	cancelFuncsMutex   sync.Mutex
	watcherWG          sync.WaitGroup
}

func New(ctx context.Context, conn *sql.DB) (*App, error) {
	q := db.New(conn)
	sessions := session.NewService(q)
	messages := message.NewService(q)
	files := history.NewService(q, conn)

	app := &App{
		Sessions:    sessions,
		Messages:    messages,
		History:     files,
		Permissions: permission.NewPermissionService(),
		DB:          q,
		LSPClients:  make(map[string]*lsp.Client),
	}

	// Initialize theme based on configuration
	app.initTheme()

	// Initialize LSP clients in the background
	go app.initLSPClients(ctx)

	var err error
	app.CoderAgent, err = agent.NewAgent(
		config.AgentCoder,
		app.Sessions,
		app.Messages,
		agent.CoderAgentTools(
			app.Permissions,
			app.Sessions,
			app.Messages,
			app.History,
			app.LSPClients,
		),
	)
	if err != nil {
		logging.Error("Failed to create coder agent", err)
		return nil, err
	}

	// Initialize ARIA if enabled
	if err := app.initARIA(ctx); err != nil {
		logging.Error("Failed to initialize ARIA", err)
		// Continue in legacy mode even if ARIA init fails
	}

	return app, nil
}

// initTheme sets the application theme based on the configuration
func (app *App) initTheme() {
	cfg := config.Get()
	if cfg == nil || cfg.TUI.Theme == "" {
		return // Use default theme
	}

	// Try to set the theme from config
	err := theme.SetTheme(cfg.TUI.Theme)
	if err != nil {
		logging.Warn("Failed to set theme from config, using default theme", "theme", cfg.TUI.Theme, "error", err)
	} else {
		logging.Debug("Set theme from config", "theme", cfg.TUI.Theme)
	}
}

// RunNonInteractive handles the execution flow when a prompt is provided via CLI flag.
func (a *App) RunNonInteractive(ctx context.Context, prompt string, outputFormat string, quiet bool) error {
	logging.Info("Running in non-interactive mode")

	// Check if ARIA mode is enabled and use orchestrator
	if a.IsARIAMode() && a.ARIA != nil && a.ARIA.Orchestrator != nil {
		return a.runARIA(ctx, prompt, outputFormat, quiet)
	}

	// Legacy mode - use coder agent directly
	return a.runLegacy(ctx, prompt, outputFormat, quiet)
}

// runARIA handles non-interactive execution in ARIA mode.
func (a *App) runARIA(ctx context.Context, prompt string, outputFormat string, quiet bool) error {
	logging.Info("Running in ARIA mode")

	// Check for slash command first
	if strings.HasPrefix(prompt, slashCommandPrefix) {
		return a.runSlashCommand(ctx, prompt, outputFormat, quiet)
	}

	// Start spinner if not in quiet mode
	var spinner *format.Spinner
	if !quiet {
		spinner = format.NewSpinner("ARIA processing...")
		spinner.Start()
		defer spinner.Stop()
	}

	// Create a minimal session for context
	sess, err := a.Sessions.Create(ctx, "ARIA: "+truncateString(prompt, 50))
	if err != nil {
		return fmt.Errorf("failed to create session: %w", err)
	}
	logging.Info("Created session for ARIA run", "session_id", sess.ID)

	// Process query through ARIA orchestrator
	query := core.Query{
		Text:      prompt,
		SessionID: sess.ID,
		UserID:    "cli",
		Metadata: map[string]any{
			"mode":   "non-interactive",
			"quiet":  quiet,
			"format": outputFormat,
		},
	}

	response, err := a.ARIA.Orchestrator.ProcessQuery(ctx, query)
	if err != nil {
		return fmt.Errorf("ARIA processing failed: %w", err)
	}

	// Stop spinner before printing output
	if !quiet && spinner != nil {
		spinner.Stop()
	}

	// Handle fallback to legacy mode
	if response.Text == "FALLBACK_TO_LEGACY" {
		logging.Info("ARIA routing fell back to legacy mode")
		return a.runLegacy(ctx, prompt, outputFormat, quiet)
	}

	// Output the response
	content := response.Text
	if content == "" {
		content = fmt.Sprintf("ARIA processed your request.\nAgency: %s\nSkills: %v\nConfidence: %.2f",
			response.Agency, response.Skills, response.Confidence)
	}

	fmt.Println(format.FormatOutput(content, outputFormat))
	logging.Info("ARIA run completed", "session_id", sess.ID, "agency", response.Agency)

	return nil
}

// runSlashCommand handles slash command execution.
func (a *App) runSlashCommand(ctx context.Context, prompt string, outputFormat string, quiet bool) error {
	result, err := a.HandleSlashCommand(ctx, prompt)
	if err != nil {
		return fmt.Errorf("slash command failed: %w", err)
	}

	fmt.Println(format.FormatOutput(result, outputFormat))
	return nil
}

// runLegacy handles non-interactive execution using the legacy coder agent.
func (a *App) runLegacy(ctx context.Context, prompt string, outputFormat string, quiet bool) error {
	// Start spinner if not in quiet mode
	var spinner *format.Spinner
	if !quiet {
		spinner = format.NewSpinner("Thinking...")
		spinner.Start()
		defer spinner.Stop()
	}

	const maxPromptLengthForTitle = 100
	titlePrefix := "Non-interactive: "
	var titleSuffix string

	if len(prompt) > maxPromptLengthForTitle {
		titleSuffix = prompt[:maxPromptLengthForTitle] + "..."
	} else {
		titleSuffix = prompt
	}
	title := titlePrefix + titleSuffix

	sess, err := a.Sessions.Create(ctx, title)
	if err != nil {
		return fmt.Errorf("failed to create session for non-interactive mode: %w", err)
	}
	logging.Info("Created session for non-interactive run", "session_id", sess.ID)

	// Automatically approve all permission requests for this non-interactive session
	a.Permissions.AutoApproveSession(sess.ID)

	done, err := a.CoderAgent.Run(ctx, sess.ID, prompt)
	if err != nil {
		return fmt.Errorf("failed to start agent processing stream: %w", err)
	}

	result := <-done
	if result.Error != nil {
		if errors.Is(result.Error, context.Canceled) || errors.Is(result.Error, agent.ErrRequestCancelled) {
			logging.Info("Agent processing cancelled", "session_id", sess.ID)
			return nil
		}
		return fmt.Errorf("agent processing failed: %w", result.Error)
	}

	// Stop spinner before printing output
	if !quiet && spinner != nil {
		spinner.Stop()
	}

	// Get the text content from the response
	content := "No content available"
	if result.Message.Content().String() != "" {
		content = result.Message.Content().String()
	}

	fmt.Println(format.FormatOutput(content, outputFormat))

	logging.Info("Non-interactive run completed", "session_id", sess.ID)

	return nil
}

// truncateString truncates a string to maxLen characters.
func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	if len(s) > maxLen {
		return s[:maxLen] + "..."
	}
	return s
}

// slashCommandPrefix is the prefix for slash commands.
const slashCommandPrefix = "/"

// HandleSlashCommand processes a slash command and returns the result.
func (a *App) HandleSlashCommand(ctx context.Context, input string) (string, error) {
	// Parse command and arguments
	parts := strings.Fields(input)
	if len(parts) == 0 {
		return "", fmt.Errorf("empty command")
	}

	cmd := parts[0]
	args := ""
	if len(parts) > 1 {
		args = strings.Join(parts[1:], " ")
	}

	// Check if ARIA is available
	if !a.IsARIAMode() || a.ARIA == nil || a.ARIA.Orchestrator == nil {
		return "", fmt.Errorf("ARIA mode not enabled")
	}

	orchestrator := a.ARIA.Orchestrator

	switch cmd {
	case "/decide-agent":
		return a.handleDecideAgent(ctx, args, orchestrator)
	case "/plan":
		return a.handlePlan(ctx, args, orchestrator)
	case "/debug-plan":
		return a.handleDebugPlan(ctx, args, orchestrator)
	case "/review-response":
		return a.handleReviewResponse(ctx, args, orchestrator)
	default:
		return "", fmt.Errorf("unknown command: %s", cmd)
	}
}

// handleDecideAgent invokes the decision engine to analyze a query.
func (a *App) handleDecideAgent(ctx context.Context, query string, orchestrator *core.BasicOrchestrator) (string, error) {
	if query == "" {
		return "", fmt.Errorf("query required for /decide-agent")
	}

	// Classify the query first
	class, err := orchestrator.GetClassifier().Classify(ctx, routing.Query{
		Text: query,
	})
	if err != nil {
		return "", fmt.Errorf("classification failed: %w", err)
	}

	// Use decision engine if available
	de := orchestrator.GetDecisionEngine()
	if de == nil {
		return "", fmt.Errorf("decision engine not available")
	}

	// Get execution decision
	decision, err := de.Decide(ctx, routing.Query{Text: query}, class)
	if err != nil {
		return "", fmt.Errorf("decision failed: %w", err)
	}

	return formatDecisionOutput(query, class, decision), nil
}

// handlePlan forces the planner to generate an execution plan.
func (a *App) handlePlan(ctx context.Context, query string, orchestrator *core.BasicOrchestrator) (string, error) {
	if query == "" {
		return "", fmt.Errorf("query required for /plan")
	}

	// Classify the query
	class, err := orchestrator.GetClassifier().Classify(ctx, routing.Query{
		Text: query,
	})
	if err != nil {
		return "", fmt.Errorf("classification failed: %w", err)
	}

	// Get decision for the query
	de := orchestrator.GetDecisionEngine()
	if de == nil {
		return "", fmt.Errorf("decision engine not available")
	}

	decision, err := de.Decide(ctx, routing.Query{Text: query}, class)
	if err != nil {
		return "", fmt.Errorf("decision failed: %w", err)
	}

	// Get planner
	planner := orchestrator.GetPlanner()
	if planner == nil {
		return "", fmt.Errorf("planner not available")
	}

	// Create plan with thinking (deep path)
	planResult, err := planner.CreatePlanWithThinking(ctx, routing.Query{Text: query}, class, decision)
	if err != nil {
		return "", fmt.Errorf("plan creation failed: %w", err)
	}

	return formatPlanOutput(planResult), nil
}

// handleDebugPlan performs post-mortem deliberative analysis.
func (a *App) handleDebugPlan(ctx context.Context, query string, orchestrator *core.BasicOrchestrator) (string, error) {
	if query == "" {
		return "", fmt.Errorf("query required for /debug-plan")
	}

	// Classify the query
	class, err := orchestrator.GetClassifier().Classify(ctx, routing.Query{
		Text: query,
	})
	if err != nil {
		return "", fmt.Errorf("classification failed: %w", err)
	}

	// Get decision for the query
	de := orchestrator.GetDecisionEngine()
	if de == nil {
		return "", fmt.Errorf("decision engine not available")
	}

	decision, err := de.Decide(ctx, routing.Query{Text: query}, class)
	if err != nil {
		return "", fmt.Errorf("decision failed: %w", err)
	}

	// Get planner
	planner := orchestrator.GetPlanner()
	if planner == nil {
		return "", fmt.Errorf("planner not available")
	}

	// Create plan with thinking
	planResult, err := planner.CreatePlanWithThinking(ctx, routing.Query{Text: query}, class, decision)
	if err != nil {
		return "", fmt.Errorf("plan creation failed: %w", err)
	}

	// Analyze potential failure points
	analysis := analyzeFailurePoints(query, planResult)

	return analysis, nil
}

// handleReviewResponse requests the reviewer to evaluate an output.
func (a *App) handleReviewResponse(ctx context.Context, text string, orchestrator *core.BasicOrchestrator) (string, error) {
	if text == "" {
		return "", fmt.Errorf("text required for /review-response")
	}

	// Get reviewer
	reviewer := orchestrator.GetReviewer()
	if reviewer == nil {
		return "", fmt.Errorf("reviewer not available")
	}

	// Create a mock plan for review
	mockPlan := &plan.Plan{
		ID:           "review-" + fmt.Sprintf("%d", time.Now().UnixNano()),
		Query:        text,
		Objective:    "Review the provided response",
		Steps:        []plan.PlanStep{},
		Hypotheses:   []plan.Hypothesis{},
		Risks:        []plan.PlanRisk{},
		Fallbacks:    []plan.FallbackStrategy{},
		DoneCriteria: "response is acceptable",
		CreatedAt:    time.Now(),
		Metadata:     map[string]any{},
	}

	// Create a mock execution result
	mockResult := &plan.ExecutionResult{
		PlanID:         mockPlan.ID,
		Success:        true,
		CompletedSteps: []int{},
		Outputs:        map[string]any{"response": text},
		Handoffs:       []plan.HandoffRecord{},
		Metrics:        plan.ExecutionMetrics{},
	}

	// Review the response
	reviewResult, err := reviewer.Review(ctx, mockPlan, mockResult)
	if err != nil {
		return "", fmt.Errorf("review failed: %w", err)
	}

	return formatReviewOutput(reviewResult), nil
}

// formatDecisionOutput formats the decision output for display.
func formatDecisionOutput(query string, class routing.Classification, decision decision.ExecutionDecision) string {
	pathStr := "unknown"
	if decision.Path != "" {
		pathStr = string(decision.Path)
	}

	return fmt.Sprintf(
		"Decision Analysis for: %s\n"+
			"\n"+
			"  Intent: %s\n"+
			"  Domain: %s\n"+
			"  Complexity: %s (score: %d)\n"+
			"  Risk: score: %d\n"+
			"  Path: %s\n"+
			"  Trigger: UseDeepPath=%v\n"+
			"  Confidence: %.2f\n"+
			"\n"+
			"  Explanation: %s",
		query,
		class.Intent,
		class.Domain,
		class.Complexity,
		decision.Complexity.Value,
		decision.Risk.Value,
		pathStr,
		decision.Trigger.UseDeepPath,
		class.Confidence,
		decision.Explanation,
	)
}

// formatPlanOutput formats the plan output for display.
func formatPlanOutput(plan *plan.Plan) string {
	var sb strings.Builder

	sb.WriteString("Execution Plan\n")
	sb.WriteString("==============\n\n")
	sb.WriteString(fmt.Sprintf("ID: %s\n", plan.ID))
	sb.WriteString(fmt.Sprintf("Objective: %s\n\n", plan.Objective))

	sb.WriteString("Steps:\n")
	for i, step := range plan.Steps {
		sb.WriteString(fmt.Sprintf("  %d. [%s] %s -> %s (timeout: %v)\n",
			i, step.Action, step.Target, formatExpectedOut(step.ExpectedOut), step.Timeout))
	}

	sb.WriteString("\nHypotheses:\n")
	for _, h := range plan.Hypotheses {
		sb.WriteString(fmt.Sprintf("  • %s (confidence: %.2f)\n", h.Description, h.Confidence))
	}

	sb.WriteString("\nRisks:\n")
	for _, r := range plan.Risks {
		sb.WriteString(fmt.Sprintf("  • %s (prob: %.2f, impact: %s)\n", r.Description, r.Probability, r.Impact))
	}

	sb.WriteString("\nFallbacks:\n")
	for _, f := range plan.Fallbacks {
		sb.WriteString(fmt.Sprintf("  • If %s -> %s (%s)\n", f.Condition, f.Action, f.Target))
	}

	sb.WriteString(fmt.Sprintf("\nDone Criteria: %s\n", plan.DoneCriteria))

	return sb.String()
}

// formatReviewOutput formats the review output for display.
func formatReviewOutput(review *plan.ReviewResult) string {
	var sb strings.Builder

	sb.WriteString("Review Result\n")
	sb.WriteString("=============\n\n")
	sb.WriteString(fmt.Sprintf("  Score: %.2f\n", review.Score))
	sb.WriteString(fmt.Sprintf("  Passed: %v\n", review.Passed))
	sb.WriteString(fmt.Sprintf("  Verdict: %s\n\n", review.Verdict))

	sb.WriteString("Acceptance Criteria:\n")
	for _, c := range review.Criteria {
		status := "✓"
		if !c.Passed {
			status = "✗"
		}
		sb.WriteString(fmt.Sprintf("  %s %s (weight: %.2f)\n", status, c.Name, c.Weight))
		sb.WriteString(fmt.Sprintf("      Evidence: %s\n", c.Evidence))
	}

	sb.WriteString(fmt.Sprintf("\nFeedback: %s\n", review.Feedback))

	return sb.String()
}

// formatExpectedOut formats expected output map for display.
func formatExpectedOut(out map[string]any) string {
	if len(out) == 0 {
		return "{}"
	}
	var parts []string
	for k, v := range out {
		parts = append(parts, fmt.Sprintf("%s=%v", k, v))
	}
	return strings.Join(parts, ", ")
}

// analyzeFailurePoints analyzes potential failure points in a plan.
func analyzeFailurePoints(query string, plan *plan.Plan) string {
	var sb strings.Builder

	sb.WriteString("Debug Plan Analysis\n")
	sb.WriteString("====================\n\n")
	sb.WriteString(fmt.Sprintf("Query: %s\n\n", query))

	sb.WriteString("Potential Failure Points:\n")

	hasRisks := false
	for _, risk := range plan.Risks {
		if risk.Probability > 0.15 {
			hasRisks = true
			sb.WriteString(fmt.Sprintf("  ⚠ %s\n", risk.Description))
			sb.WriteString(fmt.Sprintf("    Probability: %.0f%%, Impact: %s\n", risk.Probability*100, risk.Impact))
			sb.WriteString(fmt.Sprintf("    Mitigation: %s\n\n", risk.Mitigation))
		}
	}

	if !hasRisks {
		sb.WriteString("  No high-probability risks identified.\n\n")
	}

	sb.WriteString("Recommendations:\n")
	if len(plan.Fallbacks) > 0 {
		sb.WriteString("  • Fallback strategies are defined\n")
	} else {
		sb.WriteString("  • No fallback strategies defined - consider adding some\n")
	}

	if len(plan.Steps) > 5 {
		sb.WriteString("  • Complex plan with many steps - ensure proper error handling\n")
	}

	sb.WriteString("  • Verify all step timeouts are appropriate\n")
	sb.WriteString("  • Ensure context is preserved across handoffs\n")

	return sb.String()
}

// Shutdown performs a clean shutdown of the application
func (app *App) Shutdown() {
	// Cancel all watcher goroutines
	app.cancelFuncsMutex.Lock()
	for _, cancel := range app.watcherCancelFuncs {
		cancel()
	}
	app.cancelFuncsMutex.Unlock()
	app.watcherWG.Wait()

	// Perform additional cleanup for LSP clients
	app.clientsMutex.RLock()
	clients := make(map[string]*lsp.Client, len(app.LSPClients))
	maps.Copy(clients, app.LSPClients)
	app.clientsMutex.RUnlock()

	for name, client := range clients {
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		if err := client.Shutdown(shutdownCtx); err != nil {
			logging.Error("Failed to shutdown LSP client", "name", name, "error", err)
		}
		cancel()
	}

	// Shutdown ARIA scheduler components
	if app.ARIA != nil {
		if app.ARIA.Dispatcher != nil {
			app.ARIA.Dispatcher.Stop()
		}
		if app.ARIA.Worker != nil {
			app.ARIA.Worker.Stop()
		}
		if app.ARIA.RecurringPlanner != nil {
			app.ARIA.RecurringPlanner.Stop()
		}
		if app.ARIA.SchedulerService != nil {
			app.ARIA.SchedulerService.Shutdown()
		}
	}
}
