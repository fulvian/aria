package app

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"maps"
	"sync"
	"time"

	"github.com/fulvian/aria/internal/aria/core"
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
}
