// Package agency provides the Weather Agency implementation.
// This agency demonstrates the specialized agency architecture with direct API integration.
package agency

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"time"

	ariaConfig "github.com/fulvian/aria/internal/aria/config"
	"github.com/fulvian/aria/internal/aria/contracts"
	"github.com/fulvian/aria/internal/llm/tools"
)

// WeatherAgency is the weather-focused agency for weather information tasks.
type WeatherAgency struct {
	name        contracts.AgencyName
	domain      string
	description string
	state       AgencyState
	memory      *AgencyMemory

	// Lifecycle state
	status    AgencyStatus
	startTime time.Time
	pauseTime time.Time

	// Weather agent bridge
	weatherBridge WeatherAgentBridge

	// subscribed events
	sub *AgencyEventBroker
}

// NewWeatherAgency creates a new weather agency.
func NewWeatherAgency(cfg ariaConfig.WeatherConfig) *WeatherAgency {
	return &WeatherAgency{
		name:        contracts.AgencyName("weather"),
		domain:      "weather",
		description: "Weather information, forecasts, alerts, and historical weather data",
		state: AgencyState{
			AgencyID: contracts.AgencyName("weather"),
			Status:   "active",
			Metrics:  make(map[string]any),
		},
		memory:        NewAgencyMemory("weather"),
		sub:           NewAgencyEventBroker(),
		weatherBridge: NewWeatherBridge(cfg.APIKey),
	}
}

// Name returns the agency name.
func (a *WeatherAgency) Name() contracts.AgencyName {
	return a.name
}

// Domain returns the domain.
func (a *WeatherAgency) Domain() string {
	return a.domain
}

// Description returns the description.
func (a *WeatherAgency) Description() string {
	return a.description
}

// Agents returns the list of agent names.
func (a *WeatherAgency) Agents() []contracts.AgentName {
	return []contracts.AgentName{"weather"}
}

// GetAgent returns an agent by name.
func (a *WeatherAgency) GetAgent(name contracts.AgentName) (interface{}, error) {
	switch name {
	case "weather":
		return a.weatherBridge, nil
	default:
		return nil, fmt.Errorf("agent not found: %s", name)
	}
}

// Execute executes a task in the weather agency.
func (a *WeatherAgency) Execute(ctx context.Context, task contracts.Task) (contracts.Result, error) {
	start := time.Now()

	// Emit task started event
	a.sub.Publish(contracts.AgencyEvent{
		AgencyID: a.name,
		Type:     "task_started",
		Payload: map[string]any{
			"task_id":   task.ID,
			"task_name": task.Name,
		},
	})

	// Determine which skill to use based on task
	skillName := "weather-current" // default
	if len(task.Skills) > 0 {
		skillName = string(task.Skills[0])
	}

	// Execute the task via weather bridge
	result, err := a.weatherBridge.GetWeather(ctx, task, skillName)
	if err != nil {
		// Emit task failed event
		a.sub.Publish(contracts.AgencyEvent{
			AgencyID: a.name,
			Type:     "task_failed",
			Payload: map[string]any{
				"task_id": task.ID,
				"error":   err.Error(),
			},
		})
		return contracts.Result{
			TaskID:     task.ID,
			Success:    false,
			Error:      err.Error(),
			DurationMs: time.Since(start).Milliseconds(),
		}, err
	}

	// Emit task completed event
	a.sub.Publish(contracts.AgencyEvent{
		AgencyID: a.name,
		Type:     "task_completed",
		Payload: map[string]any{
			"task_id": task.ID,
			"result":  result,
		},
	})

	return contracts.Result{
		TaskID:     task.ID,
		Success:    true,
		Output:     result,
		DurationMs: time.Since(start).Milliseconds(),
	}, nil
}

// GetState returns the current state.
func (a *WeatherAgency) GetState() AgencyState {
	return a.state
}

// SaveState saves the agency state.
func (a *WeatherAgency) SaveState(state AgencyState) error {
	a.state = state
	return nil
}

// Memory returns the agency memory.
func (a *WeatherAgency) Memory() DomainMemory {
	return a.memory
}

// Subscribe returns a channel for receiving agency events.
func (a *WeatherAgency) Subscribe(ctx context.Context) <-chan contracts.AgencyEvent {
	return a.sub.Subscribe(ctx)
}

// Start starts the weather agency.
func (a *WeatherAgency) Start(ctx context.Context) error {
	switch a.status {
	case AgencyStatusRunning:
		return fmt.Errorf("agency already running")
	case AgencyStatusPaused:
		return fmt.Errorf("agency is paused, use Resume instead")
	}

	a.status = AgencyStatusRunning
	a.startTime = time.Now()

	a.sub.Publish(contracts.AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_started",
		Payload:   map[string]any{"start_time": a.startTime},
		Timestamp: time.Now(),
	})

	return nil
}

// Stop stops the weather agency.
func (a *WeatherAgency) Stop(ctx context.Context) error {
	if a.status == AgencyStatusStopped {
		return fmt.Errorf("agency already stopped")
	}

	a.status = AgencyStatusStopped
	a.pauseTime = time.Time{}

	a.sub.Publish(contracts.AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_stopped",
		Payload:   map[string]any{},
		Timestamp: time.Now(),
	})

	return nil
}

// Pause pauses the weather agency.
func (a *WeatherAgency) Pause(ctx context.Context) error {
	if a.status == AgencyStatusStopped {
		return fmt.Errorf("cannot pause stopped agency")
	}
	if a.status == AgencyStatusPaused {
		return fmt.Errorf("agency already paused")
	}

	a.status = AgencyStatusPaused
	a.pauseTime = time.Now()

	a.sub.Publish(contracts.AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_paused",
		Payload:   map[string]any{"pause_time": a.pauseTime},
		Timestamp: time.Now(),
	})

	return nil
}

// Resume resumes the weather agency.
func (a *WeatherAgency) Resume(ctx context.Context) error {
	if a.status == AgencyStatusStopped {
		return fmt.Errorf("cannot resume stopped agency, use Start instead")
	}
	if a.status == AgencyStatusRunning {
		return fmt.Errorf("agency already running")
	}

	a.status = AgencyStatusRunning
	a.pauseTime = time.Time{}

	a.sub.Publish(contracts.AgencyEvent{
		AgencyID:  a.name,
		Type:      "agency_resumed",
		Payload:   map[string]any{},
		Timestamp: time.Now(),
	})

	return nil
}

// Status returns the current agency status.
func (a *WeatherAgency) Status() AgencyStatus {
	return a.status
}

// WeatherAgentBridge defines the interface for weather agent operations.
type WeatherAgentBridge interface {
	GetWeather(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error)
}

// WeatherBridge implements WeatherAgentBridge using direct API calls.
type WeatherBridge struct {
	weatherTool tools.BaseTool
}

// NewWeatherBridge creates a new WeatherBridge with the given API key.
func NewWeatherBridge(apiKey string) *WeatherBridge {
	return &WeatherBridge{
		weatherTool: tools.NewWeatherTool(apiKey),
	}
}

// GetWeather handles weather-related tasks using direct API calls (NOT MCP).
func (b *WeatherBridge) GetWeather(ctx context.Context, task contracts.Task, skillName string) (map[string]any, error) {
	// Extract location from task parameters
	location, ok := task.Parameters["location"].(string)
	if !ok || location == "" {
		// Try to extract from description
		location = extractLocation(task.Description)
	}
	if location == "" {
		return nil, fmt.Errorf("location is required for weather tasks")
	}

	// Extract units from parameters (default: metric)
	units, _ := task.Parameters["units"].(string)
	if units == "" {
		units = "metric"
	}

	// Determine weather type based on skillName
	weatherType := "current"
	switch skillName {
	case "weather-forecast":
		weatherType = "forecast"
	case "weather-alerts":
		weatherType = "alerts"
	case "weather-historical":
		weatherType = "historical"
	}

	// Call weather tool
	result, err := b.weatherTool.Run(ctx, tools.ToolCall{
		ID:   task.ID,
		Name: "weather",
		Input: jsonConvert(tools.WeatherParams{
			Location: location,
			Units:    units,
			Type:     weatherType,
		}),
	})

	if err != nil {
		return nil, fmt.Errorf("weather tool error: %w", err)
	}

	if result.IsError {
		return nil, fmt.Errorf("weather error: %s", result.Content)
	}

	// Parse the JSON response
	var data map[string]any
	if err := json.Unmarshal([]byte(result.Content), &data); err != nil {
		return nil, fmt.Errorf("failed to parse weather response: %w", err)
	}

	data["skill"] = skillName
	data["api_source"] = "openweathermap"
	data["integration"] = "direct-api"

	return data, nil
}

// jsonConvert converts a value to JSON string.
func jsonConvert(m any) string {
	b, _ := json.Marshal(m)
	return string(b)
}

// extractLocation attempts to extract a location from a description string.
func extractLocation(description string) string {
	if description == "" {
		return ""
	}

	description = strings.TrimSpace(description)
	lowerDesc := strings.ToLower(description)

	// Pattern 1: "in/at/for [City], [State/Country]" or just "in/at/for [City]"
	// e.g., "weather in Tokyo", "temperature at New York, NY", "forecast for Paris"
	cityStatePattern := regexp.MustCompile(`(?i)(?:in|at|for|of|near|around)\s+([A-Za-z\s]+(?:,\s*[A-Z]{2}|[A-Za-z]+)?)`)
	if matches := cityStatePattern.FindStringSubmatch(description); len(matches) > 1 {
		location := strings.TrimSpace(matches[1])
		if location != "" && len(location) > 1 && len(location) < 50 {
			return location
		}
	}

	// Pattern 2: City, Country pattern - "City, Country"
	// e.g., "New York, USA", "London, UK", "Tokyo, Japan"
	cityCommaCountry := regexp.MustCompile(`(?i)^([A-Za-z\s]+),\s*([A-Za-z\s]+)$`)
	if matches := cityCommaCountry.FindStringSubmatch(description); len(matches) > 2 {
		return strings.TrimSpace(matches[1]) + ", " + strings.TrimSpace(matches[2])
	}

	// Pattern 3: ZIP/Postal code pattern - "12345" or "12345-6789"
	zipPattern := regexp.MustCompile(`\b(\d{5}(?:-\d{4})?)\b`)
	if matches := zipPattern.FindStringSubmatch(description); len(matches) > 1 {
		return "ZIP:" + matches[1]
	}

	// Pattern 4: Coordinate pattern - "37.7749° N, 122.4194° W" or similar
	coordPattern := regexp.MustCompile(`(?i)(-?\d+\.?\d*)\s*°?\s*[NS],\s*(-?\d+\.?\d*)\s*°?\s*[EW]`)
	if matches := coordPattern.FindStringSubmatch(description); len(matches) > 2 {
		return "coords:" + matches[1] + "," + matches[2]
	}

	// Pattern 5: "near [landmark/place]"
	// e.g., "near the Eiffel Tower", "near Central Park"
	nearPattern := regexp.MustCompile(`(?i)near\s+(?:the\s+)?([A-Za-z\s]+)`)
	if matches := nearPattern.FindStringSubmatch(description); len(matches) > 1 {
		nearLocation := strings.TrimSpace(matches[1])
		if nearLocation != "" && len(nearLocation) > 2 {
			return "near " + nearLocation
		}
	}

	// Pattern 6: Single city name that is well-known
	// Only use if description is short and looks like a city name
	commonCities := []string{
		"new york", "los angeles", "chicago", "houston", "phoenix",
		"philadelphia", "san antonio", "san diego", "dallas", "san jose",
		"london", "paris", "tokyo", "sydney", "berlin", "madrid", "rome",
		"amsterdam", "dubai", "singapore", "hong kong", "shanghai", "beijing",
		"mumbai", "delhi", "kolkata", "mumbai", "cairo", "johannesburg",
		"moscow", "istanbul", "bangkok", "jakarta", "manila", "seoul",
		"toronto", "vancouver", "montreal", "mexico city", "sao paulo",
		"buenos aires", "bogota", "lima", "santiago",
	}
	for _, city := range commonCities {
		if lowerDesc == city || strings.HasSuffix(lowerDesc, " "+city) ||
			strings.HasSuffix(lowerDesc, " in "+city) || strings.HasSuffix(lowerDesc, " at "+city) ||
			strings.HasSuffix(lowerDesc, " near "+city) || strings.HasSuffix(lowerDesc, " for "+city) {
			// Capitalize properly
			return strings.Title(city)
		}
	}

	// Pattern 7: If description is short and might be a city itself
	// e.g., user just types "Tokyo" or "London"
	if len(description) >= 3 && len(description) <= 30 {
		// Check if it looks like a city name (starts with capital, no spaces or single space)
		if strings.ToUpper(description[:1]) == description[:1] &&
			!strings.Contains(description, " ") || (strings.Count(description, " ") == 1 && strings.Contains(description, ",")) {
			return description
		}
	}

	return ""
}
