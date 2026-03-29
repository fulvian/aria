package skill

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/llm/tools"
)

// WeatherForecastSkill provides weather forecast information.
type WeatherForecastSkill struct {
	weatherTool tools.BaseTool
}

// NewWeatherForecastSkill creates a new weather forecast skill.
func NewWeatherForecastSkill(apiKey string) *WeatherForecastSkill {
	return &WeatherForecastSkill{
		weatherTool: tools.NewWeatherTool(apiKey),
	}
}

// Name returns the skill name.
func (s *WeatherForecastSkill) Name() SkillName {
	return SkillWeatherForecast
}

// Description returns the skill description.
func (s *WeatherForecastSkill) Description() string {
	return "Fetches 5-day weather forecast for a location including daily summaries and temperature ranges"
}

// RequiredTools returns the tools required by this skill.
func (s *WeatherForecastSkill) RequiredTools() []ToolName {
	return []ToolName{"weather"}
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *WeatherForecastSkill) RequiredMCPs() []MCPName {
	return []MCPName{} // Direct API, no MCP needed
}

// Execute fetches weather forecast.
func (s *WeatherForecastSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
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

	// Extract units (default: metric)
	units := "metric"
	if u, ok := params.Input["units"].(string); ok && u != "" {
		units = u
	}

	steps[0].Status = "completed"

	// Step 1: Fetch forecast data
	steps = append(steps, SkillStep{
		Name:        "fetch_forecast",
		Description: fmt.Sprintf("Fetching 5-day forecast for %s", location),
		Status:      "in_progress",
		DurationMs:  0,
	})

	result, err := s.weatherTool.Run(ctx, tools.ToolCall{
		ID:   params.TaskID,
		Name: "weather",
		Input: toJSONAny(tools.WeatherParams{
			Location: location,
			Units:    units,
			Type:     "forecast",
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
		Description: "Parsing forecast data",
		Status:      "completed",
		DurationMs:  time.Since(start).Milliseconds(),
	})

	// Parse the JSON response
	var forecastData map[string]any
	if err := json.Unmarshal([]byte(result.Content), &forecastData); err != nil {
		// If parsing fails, return raw content
		forecastData = map[string]any{
			"raw_response": result.Content,
		}
	}

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"task_id":  params.TaskID,
			"location": location,
			"units":    units,
			"forecast": forecastData,
			"summary":  formatForecastSummary(forecastData),
		},
		DurationMs: time.Since(start).Milliseconds(),
		Steps:      steps,
	}, nil
}

// CanExecute checks if the skill can execute.
func (s *WeatherForecastSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, "Weather forecast skill is ready"
}

// formatForecastSummary creates a human-readable summary of forecast.
func formatForecastSummary(data map[string]any) string {
	if data == nil {
		return "No forecast data available"
	}

	forecastList, ok := data["forecast"].([]any)
	if !ok || len(forecastList) == 0 {
		return "No forecast data available"
	}

	days := make([]string, 0, len(forecastList))
	for _, f := range forecastList {
		if fmap, ok := f.(map[string]any); ok {
			if date, ok := fmap["date"].(string); ok {
				days = append(days, date)
			}
		}
	}

	if len(days) == 0 {
		return "Forecast data retrieved"
	}

	return fmt.Sprintf("5-day forecast for %s: %s", data["location"], joinStrings(days, ", "))
}
