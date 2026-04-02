package cmd

import (
	"context"
	"fmt"
	"os"
	"sync"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/fulvian/aria/internal/app"
	"github.com/fulvian/aria/internal/config"
	"github.com/fulvian/aria/internal/db"
	"github.com/fulvian/aria/internal/format"
	"github.com/fulvian/aria/internal/llm/agent"
	"github.com/fulvian/aria/internal/logging"
	"github.com/fulvian/aria/internal/pubsub"
	"github.com/fulvian/aria/internal/startup"
	"github.com/fulvian/aria/internal/startup/checkers"
	"github.com/fulvian/aria/internal/tui"
	"github.com/fulvian/aria/internal/version"
	"github.com/joho/godotenv"
	zone "github.com/lrstanley/bubblezone"
	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "aria",
	Short: "ARIA - Autonomous Reasoning & Intelligent Assistant",
	Long: `ARIA is a powerful terminal-based AI assistant that helps with software development tasks.
It provides an interactive chat interface with AI capabilities, code analysis, and LSP integration
to assist developers in writing, debugging, and understanding code directly from the terminal.`,
	Example: `
  # Run in interactive mode
  aria

  # Run with debug logging
  aria -d

  # Run with debug logging in a specific directory
  aria -d -c /path/to/project

  # Print version
  aria -v

  # Run a single non-interactive prompt
  aria -p "Explain the use of context in Go"

  # Run a single non-interactive prompt with JSON output format
  aria -p "Explain the use of context in Go" -f json
  `,
	RunE: func(cmd *cobra.Command, args []string) error {
		// If the help flag is set, show the help message
		if cmd.Flag("help").Changed {
			cmd.Help()
			return nil
		}
		if cmd.Flag("version").Changed {
			fmt.Println(version.Version)
			return nil
		}

		// Load the config
		debug, _ := cmd.Flags().GetBool("debug")
		startupDebug, _ := cmd.Flags().GetBool("startup-debug")
		logging.Info("DEBUG: Starting initialization")
		cwd, _ := cmd.Flags().GetString("cwd")
		prompt, _ := cmd.Flags().GetString("prompt")
		outputFormat, _ := cmd.Flags().GetString("output-format")
		quiet, _ := cmd.Flags().GetBool("quiet")

		// Validate format option
		if !format.IsValid(outputFormat) {
			return fmt.Errorf("invalid format option: %s\n%s", outputFormat, format.GetHelpText())
		}

		if cwd != "" {
			err := os.Chdir(cwd)
			if err != nil {
				return fmt.Errorf("failed to change directory: %v", err)
			}
		}
		if cwd == "" {
			c, err := os.Getwd()
			if err != nil {
				return fmt.Errorf("failed to get current working directory: %v", err)
			}
			cwd = c
		}

		// Load .env file automatically if present
		if err := godotenv.Load(); err != nil {
			// .env not found is not an error, just continue
			logging.Debug("DEBUG: .env file not found, using environment variables")
		} else {
			logging.Debug("DEBUG: .env file loaded successfully")
		}

		logging.Info("DEBUG: About to load config", "cwd", cwd, "debug", debug)
		cfg, err := config.Load(cwd, debug)
		if err != nil {
			logging.Error("DEBUG: Config load failed", "error", err)
			return err
		}
		logging.Info("DEBUG: Config loaded successfully", "dataDir", cfg.Data.Directory)

		// Run bootstrap health checks if startup-debug is enabled
		var statusTracker *startup.StatusTracker
		if startupDebug {
			statusTracker, err = runBootstrap(context.Background(), cwd, debug)
			if err != nil {
				logging.Error("Startup health checks failed", "error", err)
			} else {
				view := startup.NewStartupStatusView(statusTracker)
				fmt.Fprintf(os.Stderr, "\n=== ARIA Startup Status ===\n%s\n======================\n\n", view.Render())
			}
		}

		// Connect DB, this will also run migrations
		fmt.Fprintf(os.Stderr, "DEBUG: About to connect to database...\n")
		conn, err := db.Connect()
		if err != nil {
			return err
		}
		logging.Info("DEBUG: Database connected successfully")

		// Create main context for the application
		ctx, cancel := context.WithCancel(context.Background())
		defer cancel()

		logging.Info("DEBUG: About to create app")
		app, err := app.New(ctx, conn)
		if err != nil {
			logging.Error("Failed to create app: %v", err)
			return err
		}
		logging.Info("DEBUG: App created successfully")
		// Defer shutdown here so it runs for both interactive and non-interactive modes
		defer app.Shutdown()

		// Initialize MCP tools early for both modes
		logging.Info("DEBUG: About to init MCP tools")
		initMCPTools(ctx, app)

		// Non-interactive mode
		if prompt != "" {
			// Run non-interactive flow using the App method
			logging.Info("DEBUG: Running in non-interactive mode")
			return app.RunNonInteractive(ctx, prompt, outputFormat, quiet)
		}

		// Interactive mode
		// Set up the TUI
		fmt.Fprintf(os.Stderr, "DEBUG: About to setup TUI - logging.Info call incoming\n")
		logging.Info("DEBUG: About to setup TUI")
		fmt.Fprintf(os.Stderr, "DEBUG: About to setup TUI - calling zone.NewGlobal()\n")
		zone.NewGlobal()
		fmt.Fprintf(os.Stderr, "DEBUG: zone.NewGlobal done - about to create tea.NewProgram\n")
		program := tea.NewProgram(
			tui.New(app),
			tea.WithAltScreen(),
		)
		fmt.Fprintf(os.Stderr, "DEBUG: tea.NewProgram created, about to setup subscriptions\n")

		// Setup the subscriptions, this will send services events to the TUI
		logging.Info("DEBUG: About to setup subscriptions")
		ch, cancelSubs := setupSubscriptions(app, ctx)
		logging.Info("DEBUG: Subscriptions setup complete")

		// Create a context for the TUI message handler
		tuiCtx, tuiCancel := context.WithCancel(ctx)
		var tuiWg sync.WaitGroup
		tuiWg.Add(1)

		// Set up message handling for the TUI
		go func() {
			defer tuiWg.Done()
			defer logging.RecoverPanic("TUI-message-handler", func() {
				attemptTUIRecovery(program)
			})

			for {
				select {
				case <-tuiCtx.Done():
					logging.Info("TUI message handler shutting down")
					return
				case msg, ok := <-ch:
					if !ok {
						logging.Info("TUI message channel closed")
						return
					}
					program.Send(msg)
				}
			}
		}()

		// Cleanup function for when the program exits
		cleanup := func() {
			// Shutdown the app
			app.Shutdown()

			// Cancel subscriptions first
			cancelSubs()

			// Then cancel TUI message handler
			tuiCancel()

			// Wait for TUI message handler to finish
			tuiWg.Wait()

			logging.Info("All goroutines cleaned up")
		}

		// Run the TUI
		logging.Info("DEBUG: About to run TUI program")
		fmt.Fprintf(os.Stderr, "DEBUG: About to call program.Run()\n")
		result, err := program.Run()
		fmt.Fprintf(os.Stderr, "DEBUG: program.Run() returned, result=%v err=%v\n", result, err)
		cleanup()
		logging.Info("DEBUG: Cleanup done, TUI exited")

		if err != nil {
			logging.Error("TUI error: %v", err)
			return fmt.Errorf("TUI error: %v", err)
		}

		logging.Info("TUI exited with result: %v", result)
		return nil
	},
}

// attemptTUIRecovery tries to recover the TUI after a panic
func attemptTUIRecovery(program *tea.Program) {
	logging.Info("Attempting to recover TUI after panic")

	// We could try to restart the TUI or gracefully exit
	// For now, we'll just quit the program to avoid further issues
	program.Quit()
}

func initMCPTools(ctx context.Context, app *app.App) {
	logging.Info("DEBUG: initMCPTools starting")
	go func() {
		defer logging.RecoverPanic("MCP-goroutine", nil)

		// Create a context with timeout for the initial MCP tools fetch
		ctxWithTimeout, cancel := context.WithTimeout(ctx, 30*time.Second)
		defer cancel()

		// Set this up once with proper error handling
		logging.Info("DEBUG: initMCPTools about to call GetMcpTools")
		agent.GetMcpTools(ctxWithTimeout, app.Permissions)
		logging.Info("DEBUG: initMCPTools GetMcpTools completed")
		logging.Info("MCP message handling goroutine exiting")
	}()
	logging.Info("DEBUG: initMCPTools goroutine started")
}

func setupSubscriber[T any](
	ctx context.Context,
	wg *sync.WaitGroup,
	name string,
	subscriber func(context.Context) <-chan pubsub.Event[T],
	outputCh chan<- tea.Msg,
) {
	wg.Add(1)
	go func() {
		defer wg.Done()
		defer logging.RecoverPanic(fmt.Sprintf("subscription-%s", name), nil)

		subCh := subscriber(ctx)

		for {
			select {
			case event, ok := <-subCh:
				if !ok {
					logging.Info("subscription channel closed", "name", name)
					return
				}

				var msg tea.Msg = event

				select {
				case outputCh <- msg:
				case <-time.After(2 * time.Second):
					logging.Warn("message dropped due to slow consumer", "name", name)
				case <-ctx.Done():
					logging.Info("subscription cancelled", "name", name)
					return
				}
			case <-ctx.Done():
				logging.Info("subscription cancelled", "name", name)
				return
			}
		}
	}()
}

func setupSubscriptions(app *app.App, parentCtx context.Context) (chan tea.Msg, func()) {
	ch := make(chan tea.Msg, 100)

	wg := sync.WaitGroup{}
	ctx, cancel := context.WithCancel(parentCtx) // Inherit from parent context

	setupSubscriber(ctx, &wg, "logging", logging.Subscribe, ch)
	setupSubscriber(ctx, &wg, "sessions", app.Sessions.Subscribe, ch)
	setupSubscriber(ctx, &wg, "messages", app.Messages.Subscribe, ch)
	setupSubscriber(ctx, &wg, "permissions", app.Permissions.Subscribe, ch)
	setupSubscriber(ctx, &wg, "coderAgent", app.CoderAgent.Subscribe, ch)

	cleanupFunc := func() {
		logging.Info("Cancelling all subscriptions")
		cancel() // Signal all goroutines to stop

		waitCh := make(chan struct{})
		go func() {
			defer logging.RecoverPanic("subscription-cleanup", nil)
			wg.Wait()
			close(waitCh)
		}()

		select {
		case <-waitCh:
			logging.Info("All subscription goroutines completed successfully")
			close(ch) // Only close after all writers are confirmed done
		case <-time.After(5 * time.Second):
			logging.Warn("Timed out waiting for some subscription goroutines to complete")
			close(ch)
		}
	}
	return ch, cleanupFunc
}

// runBootstrap runs the startup health checks using BootstrapManager.
// Returns the StatusTracker for UI integration.
func runBootstrap(ctx context.Context, cwd string, debug bool) (*startup.StatusTracker, error) {
	// Create checkers for each service
	checkersList := []startup.Checker{
		checkers.NewConfigChecker(cwd, debug),
		checkers.NewDataDirChecker(cwd, debug),
		checkers.NewDatabaseChecker(),
		checkers.NewLLMProviderChecker(cwd, debug),
		checkers.NewMemoryChecker(),
		checkers.NewLSPChecker(),
		checkers.NewMCPChecker(),
	}

	// Create and configure the bootstrap manager
	manager := startup.NewBootstrapManager(checkersList)

	// Create a cancellable context for bootstrap
	bootstrapCtx, cancel := context.WithTimeout(ctx, 120*time.Second)
	defer cancel()

	// Run bootstrap
	if err := manager.Bootstrap(bootstrapCtx); err != nil {
		return manager.StatusTracker(), fmt.Errorf("bootstrap failed: %w", err)
	}

	logging.Info("Bootstrap completed successfully")
	return manager.StatusTracker(), nil
}

func Execute() {
	err := rootCmd.Execute()
	if err != nil {
		os.Exit(1)
	}
}

func init() {
	rootCmd.Flags().BoolP("help", "h", false, "Help")
	rootCmd.Flags().BoolP("version", "v", false, "Version")
	rootCmd.Flags().BoolP("debug", "d", false, "Debug")
	rootCmd.Flags().StringP("cwd", "c", "", "Current working directory")
	rootCmd.Flags().StringP("prompt", "p", "", "Prompt to run in non-interactive mode")

	// Add format flag with validation logic
	rootCmd.Flags().StringP("output-format", "f", format.Text.String(),
		"Output format for non-interactive mode (text, json)")

	// Add quiet flag to hide spinner in non-interactive mode
	rootCmd.Flags().BoolP("quiet", "q", false, "Hide spinner in non-interactive mode")

	// Add startup-debug flag to show detailed startup status
	rootCmd.Flags().Bool("startup-debug", false, "Show detailed startup status")

	// Register custom validation for the format flag
	rootCmd.RegisterFlagCompletionFunc("output-format", func(cmd *cobra.Command, args []string, toComplete string) ([]string, cobra.ShellCompDirective) {
		return format.SupportedFormats, cobra.ShellCompDirectiveNoFileComp
	})
}
