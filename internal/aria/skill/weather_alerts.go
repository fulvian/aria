package skill

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/llm/tools"
)

// WeatherAlertsSkill provides weather alerts and warnings.
type WeatherAlertsSkill struct {
	weatherTool tools.BaseTool
}

// NewWeatherAlertsSkill creates a new weather alerts skill.
func NewWeatherAlertsSkill(apiKey string) *WeatherAlertsSkill {
	return &WeatherAlertsSkill{
		weatherTool: tools.NewWeatherTool(apiKey),
	}
}

// Name returns the skill name.
func (s *WeatherAlertsSkill) Name() SkillName {
	return SkillWeatherAlerts
}

// Description returns the skill description.
func (s *WeatherAlertsSkill) Description() string {
	return "Fetches weather alerts and severe weather warnings for a location"
}

// RequiredTools returns the tools required by this skill.
func (s *WeatherAlertsSkill) RequiredTools() []ToolName {
	return []ToolName{"weather"}
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *WeatherAlertsSkill) RequiredMCPs() []MCPName {
	return []MCPName{} // Direct API, no MCP needed
}

// Execute fetches weather alerts.
func (s *WeatherAlertsSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
	start := time.Now()

	steps := []SkillStep{
		{Name: "validate_params", Description: "Validating parameters", Status: "in_progress", DurationMs: 0},
	}

	// Extract location from input
	location, ok := params.Input["location"].(string)
	if !ok || location == "" {
		location, ok = params.Context["location"].(string)
		if !ok || location == "" {
			steps[0].Status = "failed"
			return SkillResult{
				Success: false,
				Error:   "location is required",
				Steps:   steps,
			}, fmt.Errorf("location is required")
		}
	}

	steps[0].Status = "completed"

	// Step 1: Fetch alerts data
	steps = append(steps, SkillStep{
		Name:        "fetch_alerts",
		Description: fmt.Sprintf("Fetching weather alerts for %s", location),
		Status:      "in_progress",
		DurationMs:  0,
	})

	result, err := s.weatherTool.Run(ctx, tools.ToolCall{
		ID:   params.TaskID,
		Name: "weather",
		Input: toJSONAny(tools.WeatherParams{
			Location: location,
			Type:     "alerts",
		}),
	})

	steps[1].DurationMs = time.Since(start).Milliseconds()

	if err != nil {
		steps[1].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      err.Error(),
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, err
	}

	if result.IsError {
		steps[1].Status = "failed"
		return SkillResult{
			Success:    false,
			Error:      result.Content,
			DurationMs: time.Since(start).Milliseconds(),
			Steps:      steps,
		}, fmt.Errorf("weather tool error: %s", result.Content)
	}

	steps[1].Status = "completed"

	// Step 2: Parse result
	steps = append(steps, SkillStep{
		Name:        "parse_result",
		Description: "Parsing alerts data",
		Status:      "completed",
		DurationMs:  time.Since(start).Milliseconds(),
	})

	// Parse the JSON response
	var alertsData map[string]any
	if err := json.Unmarshal([]byte(result.Content), &alertsData); err != nil {
		// If parsing fails, return raw content
		alertsData = map[string]any{
			"raw_response": result.Content,
		}
	}

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"task_id":  params.TaskID,
			"location": location,
			"alerts":   alertsData,
			"summary":  formatAlertsSummary(alertsData),
		},
		DurationMs: time.Since(start).Milliseconds(),
		Steps:      steps,
	}, nil
}

// CanExecute checks if the skill can execute.
func (s *WeatherAlertsSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, "Weather alerts skill is ready"
}

// formatAlertsSummary creates a human-readable summary of alerts.
func formatAlertsSummary(data map[string]any) string {
	if data == nil {
		return "No alerts data available"
	}

	alerts, ok := data["alerts"].([]any)
	if !ok || len(alerts) == 0 {
		return "No active weather alerts for this location"
	}

	alertTypes := make([]string, 0)
	for _, a := range alerts {
		if amap, ok := a.(map[string]any); ok {
			if event, ok := amap["event"].(string); ok {
				alertTypes = append(alertTypes, event)
			}
		}
	}

	if len(alertTypes) == 0 {
		return fmt.Sprintf("%d alert(s) found", len(alerts))
	}

	return fmt.Sprintf("Active alerts: %s", joinStrings(alertTypes, ", "))
}
