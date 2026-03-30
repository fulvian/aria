package plan

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/mark3labs/mcp-go/client"
	"github.com/mark3labs/mcp-go/mcp"
)

// SequentialThinkingConfig configurazione per sequential-thinking.
type SequentialThinkingConfig struct {
	Command     string
	Args        []string
	Env         []string
	TimeoutMs   int
	MaxThoughts int
}

// DefaultSequentialThinkingConfig config di default.
func DefaultSequentialThinkingConfig() SequentialThinkingConfig {
	return SequentialThinkingConfig{
		Command:     "npx",
		Args:        []string{"-y", "@modelcontextprotocol/server-sequential-thinking"},
		TimeoutMs:   12000,
		MaxThoughts: 12,
	}
}

// ThoughtRequest richiesta per un pensiero.
type ThoughtRequest struct {
	Thought           string `json:"thought"`
	NextThoughtNeeded bool   `json:"nextThoughtNeeded"`
}

// ThoughtResponse risposta da sequential-thinking.
type ThoughtResponse struct {
	Thought     string  `json:"thought"`
	Confidence  float64 `json:"confidence,omitempty"`
	Reasoning   string  `json:"reasoning,omitempty"`
	NextThought bool    `json:"nextThought"`
}

// DeliberationResult risultato della deliberazione.
type DeliberationResult struct {
	Objective    string
	Steps        []string
	Hypotheses   []string
	Risks        []string
	Fallbacks    []string
	DoneCriteria string
	Confidence   float64
}

// SequentialThinkingCaller chiama il tool MCP sequential-thinking.
type SequentialThinkingCaller struct {
	config SequentialThinkingConfig
}

// NewSequentialThinkingCaller crea un nuovo caller.
func NewSequentialThinkingCaller(config SequentialThinkingConfig) *SequentialThinkingCaller {
	return &SequentialThinkingCaller{config: config}
}

// Deliberate esegue la deliberazione usando sequential-thinking MCP.
func (s *SequentialThinkingCaller) Deliberate(ctx context.Context, query string, complexity int, risk int) (*DeliberationResult, error) {
	// 1. Crea client MCP stdio
	c, err := client.NewStdioMCPClient(
		s.config.Command,
		s.config.Env,
		s.config.Args...,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create MCP client: %w", err)
	}
	defer c.Close()

	// 2. Inizializza
	initReq := mcp.InitializeRequest{}
	initReq.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initReq.Params.ClientInfo = mcp.Implementation{
		Name:    "ARIA-Orchestrator",
		Version: "1.0.0",
	}

	ctx, cancel := context.WithTimeout(ctx, time.Duration(s.config.TimeoutMs)*time.Millisecond)
	defer cancel()

	_, err = c.Initialize(ctx, initReq)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize MCP: %w", err)
	}

	// 3. Lista tools per trovare sequential-thinking
	toolsResult, err := c.ListTools(ctx, mcp.ListToolsRequest{})
	if err != nil {
		return nil, fmt.Errorf("failed to list tools: %w", err)
	}

	// Trova il tool sequential-thinking
	var stTool mcp.Tool
	for _, t := range toolsResult.Tools {
		if t.Name == "sequentialthinking" || t.Name == "sequential_thinking" {
			stTool = t
			break
		}
	}

	if stTool.Name == "" {
		return nil, fmt.Errorf("sequential-thinking tool not found")
	}

	// 4. Esegui deliberazione multi-step
	thoughts := []string{}
	done := false
	step := 0

	// Costruisci prompt iniziale
	currentThought := buildInitialThought(query, complexity, risk)

	for !done && step < s.config.MaxThoughts {
		// Chiama sequential-thinking tool
		result, err := c.CallTool(ctx, mcp.CallToolRequest{
			Params: struct {
				Name      string                 `json:"name"`
				Arguments map[string]interface{} `json:"arguments,omitempty"`
				Meta      *struct {
					ProgressToken mcp.ProgressToken `json:"progressToken,omitempty"`
				} `json:"_meta,omitempty"`
			}{
				Name: stTool.Name,
				Arguments: map[string]interface{}{
					"thought":           currentThought,
					"nextThoughtNeeded": step < s.config.MaxThoughts-1,
				},
				Meta: nil,
			},
		})
		if err != nil {
			return nil, fmt.Errorf("sequential-thinking call failed: %w", err)
		}

		// Estrai risposta
		var response ThoughtResponse
		if len(result.Content) > 0 {
			if text, ok := result.Content[0].(mcp.TextContent); ok {
				if err := json.Unmarshal([]byte(text.Text), &response); err != nil {
					// Try parsing as plain text if JSON fails
					response.Thought = text.Text
					response.NextThought = false
				}
			}
		}

		thoughts = append(thoughts, response.Thought)

		if !response.NextThought {
			done = true
		}

		// Prepara prossimo pensiero
		currentThought = buildFollowUpThought(query, thoughts)
		step++
	}

	// 5. Costruisci DeliberationResult
	return buildDeliberationResult(thoughts), nil
}

// buildInitialThought costruisce il pensiero iniziale.
func buildInitialThought(query string, complexity int, risk int) string {
	return fmt.Sprintf(
		"Analyze this task for ARIA orchestrator planning:\n\nTask: %s\n\nComplexity: %d/100\nRisk: %d/100\n\nProvide: 1) Clear objective, 2) Key steps, 3) Risks, 4) Fallbacks, 5) Done criteria. Be concise.",
		query, complexity, risk)
}

// buildFollowUpThought costruisce un pensiero di follow-up.
func buildFollowUpThought(query string, previousThoughts []string) string {
	return fmt.Sprintf(
		"Continue analysis of: %s\n\nPrevious thoughts:\n%s\n\nProvide next refinement or conclude if complete.",
		query, strings.Join(previousThoughts, "\n---\n"))
}

// buildDeliberationResult costruisce il risultato dalla lista di pensieri.
func buildDeliberationResult(thoughts []string) *DeliberationResult {
	// Parser semplificato - estrae info dai pensieri
	// In una versione più avanzata, usare LLM per parsing
	result := &DeliberationResult{
		Steps:      []string{},
		Hypotheses: []string{},
		Risks:      []string{},
		Fallbacks:  []string{},
		Confidence: 0.7,
	}

	for _, thought := range thoughts {
		// Parser naive - cerca keywords
		if strings.Contains(strings.ToLower(thought), "step") ||
			strings.Contains(strings.ToLower(thought), "1)") ||
			strings.Contains(strings.ToLower(thought), "first") {
			result.Steps = append(result.Steps, thought)
		}
		if strings.Contains(strings.ToLower(thought), "risk") ||
			strings.Contains(strings.ToLower(thought), "danger") {
			result.Risks = append(result.Risks, thought)
		}
		if strings.Contains(strings.ToLower(thought), "fallback") ||
			strings.Contains(strings.ToLower(thought), "alternative") {
			result.Fallbacks = append(result.Fallbacks, thought)
		}
		if strings.Contains(strings.ToLower(thought), "done") ||
			strings.Contains(strings.ToLower(thought), "complete") {
			result.DoneCriteria = thought
		}
	}

	if len(result.Steps) == 0 && len(thoughts) > 0 {
		result.Steps = thoughts
	}

	return result
}
