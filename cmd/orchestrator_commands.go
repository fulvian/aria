package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

// Orchestrator command definitions for slash command support.
// These commands are invoked by users in the chat interface and processed
// through the orchestrator's Deep Path pipeline.

// NOTE: These are NOT cobra commands that can be run from the CLI.
// They are slash commands that users type in the chat (e.g., "/plan").
// The actual handling of these commands happens in the TUI/App layer.

var orchestratorCommands = map[string]CommandDefinition{
	"/plan": {
		Description: "Force planner to generate execution plan",
		Agent:       "orchestrator",
		Usage:       "/plan [query]",
	},
	"/decide-agent": {
		Description: "Invoke decision engine for query analysis",
		Agent:       "orchestrator",
		Usage:       "/decide-agent [query]",
	},
	"/debug-plan": {
		Description: "Post-mortem deliberative analysis",
		Agent:       "orchestrator",
		Usage:       "/debug-plan",
	},
	"/review-response": {
		Description: "Review output candidate with reviewer",
		Agent:       "orchestrator",
		Usage:       "/review-response [response]",
	},
}

// CommandDefinition defines a slash command's metadata.
type CommandDefinition struct {
	Description string
	Agent       string
	Usage       string
}

// GetOrchestratorCommands returns all registered orchestrator slash commands.
func GetOrchestratorCommands() map[string]CommandDefinition {
	return orchestratorCommands
}

// GetCommand returns a specific command definition.
func GetCommand(name string) (CommandDefinition, bool) {
	cmd, ok := orchestratorCommands[name]
	return cmd, ok
}

// registerOrchestratorCommands adds orchestrator commands to the CLI help.
// This is for documentation purposes only - these are chat commands, not CLI flags.
func registerOrchestratorCommands() {
	// Create a hidden command to document slash commands
	slashCmd := &cobra.Command{
		Use:   "slash-commands",
		Short: "Available slash commands in chat",
		Long: `Slash commands are available in the chat interface:

  /plan              - Force planner to generate execution plan
  /decide-agent      - Invoke decision engine for query analysis
  /debug-plan        - Post-mortem deliberative analysis
  /review-response   - Review output candidate with reviewer

These commands invoke the orchestrator's Deep Path pipeline.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			fmt.Println("Slash commands (use in chat interface):")
			for name, def := range orchestratorCommands {
				fmt.Printf("  %s - %s (agent: %s)\n", name, def.Description, def.Agent)
			}
			return nil
		},
	}
	// Don't add to rootCmd - these are chat commands, not CLI commands
	_ = slashCmd
}
