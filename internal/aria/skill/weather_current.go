package skill

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/fulvian/aria/internal/llm/tools"
)

// WeatherCurrentSkill provides current weather information.
type WeatherCurrentSkill struct {
	weatherTool tools.BaseTool
}

// NewWeatherCurrentSkill creates a new weather current skill.
func NewWeatherCurrentSkill(apiKey string) *WeatherCurrentSkill {
	return &WeatherCurrentSkill{
		weatherTool: tools.NewWeatherTool(apiKey),
	}
}

// Name returns the skill name.
func (s *WeatherCurrentSkill) Name() SkillName {
	return SkillWeatherCurrent
}

// Description returns the skill description.
func (s *WeatherCurrentSkill) Description() string {
	return "Fetches current weather conditions for a location including temperature, humidity, wind, and weather conditions"
}

// RequiredTools returns the tools required by this skill.
func (s *WeatherCurrentSkill) RequiredTools() []ToolName {
	return []ToolName{"weather"}
}

// RequiredMCPs returns the MCPs required by this skill.
func (s *WeatherCurrentSkill) RequiredMCPs() []MCPName {
	return []MCPName{} // Direct API, no MCP needed
}

// Execute fetches current weather.
func (s *WeatherCurrentSkill) Execute(ctx context.Context, params SkillParams) (SkillResult, error) {
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

	// Step 1: Fetch weather data
	steps = append(steps, SkillStep{
		Name:        "fetch_weather",
		Description: fmt.Sprintf("Fetching current weather for %s", location),
		Status:      "in_progress",
		DurationMs:  0,
	})

	result, err := s.weatherTool.Run(ctx, tools.ToolCall{
		ID:   params.TaskID,
		Name: "weather",
		Input: toJSONAny(tools.WeatherParams{
			Location: location,
			Units:    units,
			Type:     "current",
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
		Description: "Parsing weather data",
		Status:      "completed",
		DurationMs:  time.Since(start).Milliseconds(),
	})

	// Parse the JSON response
	var weatherData map[string]any
	if err := json.Unmarshal([]byte(result.Content), &weatherData); err != nil {
		// If parsing fails, return raw content
		weatherData = map[string]any{
			"raw_response": result.Content,
		}
	}

	return SkillResult{
		Success: true,
		Output: map[string]any{
			"task_id":  params.TaskID,
			"location": location,
			"units":    units,
			"weather":  weatherData,
			"summary":  formatWeatherSummary(weatherData),
		},
		DurationMs: time.Since(start).Milliseconds(),
		Steps:      steps,
	}, nil
}

// CanExecute checks if the skill can execute.
func (s *WeatherCurrentSkill) CanExecute(ctx context.Context) (bool, string) {
	return true, "Weather current skill is ready"
}

// formatWeatherSummary creates a human-readable summary.
func formatWeatherSummary(data map[string]any) string {
	if data == nil {
		return "No weather data available"
	}

	parts := []string{}

	if temp, ok := data["temperature"].(string); ok {
		parts = append(parts, fmt.Sprintf("Temperature: %s", temp))
	}
	if conditions, ok := data["conditions"].(string); ok && conditions != "" {
		parts = append(parts, fmt.Sprintf("Conditions: %s", conditions))
	}
	if humidity, ok := data["humidity"].(string); ok {
		parts = append(parts, fmt.Sprintf("Humidity: %s", humidity))
	}
	if wind, ok := data["wind_speed"].(string); ok {
		parts = append(parts, fmt.Sprintf("Wind: %s", wind))
	}

	if len(parts) == 0 {
		return "Weather data retrieved"
	}

	return joinStrings(parts, ", ")
}

// joinStrings joins strings with a separator.
func joinStrings(parts []string, sep string) string {
	if len(parts) == 0 {
		return ""
	}
	result := parts[0]
	for i := 1; i < len(parts); i++ {
		result += sep + parts[i]
	}
	return result
}

// toJSONAny converts any value to JSON string.
func toJSONAny(m any) string {
	b, _ := json.Marshal(m)
	return string(b)
}
