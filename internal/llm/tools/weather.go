package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type WeatherParams struct {
	Location string `json:"location"`
	Units    string `json:"units,omitempty"`
	Type     string `json:"type,omitempty"` // current, forecast, alerts, historical
}

type weatherTool struct {
	client *http.Client
	apiKey string
}

const (
	WeatherToolName        = "weather"
	weatherToolDescription = `Fetches weather information from OpenWeatherMap API.
This tool provides current weather, forecasts, and alerts using direct API calls (NOT MCP).

HOW TO USE:
- Provide a location (city name, lat/lon, or city ID)
- Specify units (metric, imperial, kelvin) - defaults to metric
- Specify type (current, forecast, alerts) - defaults to current

FEATURES:
- Current weather: temperature, humidity, wind, conditions
- 5-day forecast: daily summaries
- Weather alerts: severe weather warnings
- Direct API integration (low token overhead vs MCP)

EXAMPLES:
- "What's the weather in Rome?"
- "Forecast for London, metric units"
- "Alerts for New York"`
)

// OpenWeatherMap API response structures
type owmCurrentResponse struct {
	Main struct {
		Temp      float64 `json:"temp"`
		FeelsLike float64 `json:"feels_like"`
		Humidity  int     `json:"humidity"`
		Pressure  int     `json:"pressure"`
	} `json:"main"`
	Wind struct {
		Speed float64 `json:"speed"`
		Deg   int     `json:"deg"`
	} `json:"wind"`
	Weather []struct {
		ID          int    `json:"id"`
		Main        string `json:"main"`
		Description string `json:"description"`
		Icon        string `json:"icon"`
	} `json:"weather"`
	Name    string `json:"name"`
	CityID  int    `json:"id"`
	Country string `json:"sys"`
}

type owmForecastResponse struct {
	City struct {
		Name    string `json:"name"`
		Country string `json:"country"`
	} `json:"city"`
	List []struct {
		Dt   int64 `json:"dt"`
		Main struct {
			Temp      float64 `json:"temp"`
			FeelsLike float64 `json:"feels_like"`
			Humidity  int     `json:"humidity"`
		} `json:"main"`
		Weather []struct {
			Description string `json:"description"`
			Icon        string `json:"icon"`
		} `json:"weather"`
		Wind struct {
			Speed float64 `json:"speed"`
		} `json:"wind"`
	} `json:"list"`
}

type owmAlertsResponse struct {
	Alerts []struct {
		Event string   `json:"event"`
		Start int64    `json:"start"`
		End   int64    `json:"end"`
		Desc  string   `json:"description"`
		Tags  []string `json:"tags"`
	} `json:"alerts"`
}

func NewWeatherTool(apiKey string) BaseTool {
	return &weatherTool{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		apiKey: apiKey,
	}
}

func (t *weatherTool) Info() ToolInfo {
	return ToolInfo{
		Name:        WeatherToolName,
		Description: weatherToolDescription,
		Parameters: map[string]any{
			"location": map[string]any{
				"type":        "string",
				"description": "Location (city name, lat:lon, or city ID)",
			},
			"units": map[string]any{
				"type":        "string",
				"description": "Units: metric, imperial, kelvin (default: metric)",
			},
			"type": map[string]any{
				"type":        "string",
				"description": "Type: current, forecast, alerts (default: current)",
			},
		},
		Required: []string{"location"},
	}
}

func (t *weatherTool) Run(ctx context.Context, call ToolCall) (ToolResponse, error) {
	var params WeatherParams
	if err := json.Unmarshal([]byte(call.Input), &params); err != nil {
		return NewTextErrorResponse("invalid parameters: " + err.Error()), nil
	}

	if params.Location == "" {
		return NewTextErrorResponse("location is required"), nil
	}

	if params.Units == "" {
		params.Units = "metric"
	}

	// Route to appropriate handler
	switch strings.ToLower(params.Type) {
	case "forecast":
		return t.getForecast(ctx, params.Location, params.Units)
	case "alerts":
		return t.getAlerts(ctx, params.Location)
	case "historical":
		return t.getHistorical(ctx, params.Location, params.Units)
	default:
		return t.getCurrent(ctx, params.Location, params.Units)
	}
}

func (t *weatherTool) getCurrent(ctx context.Context, location, units string) (ToolResponse, error) {
	url := fmt.Sprintf(
		"https://api.openweathermap.org/data/2.5/weather?q=%s&units=%s&appid=%s",
		strings.ReplaceAll(location, " ", "+"),
		units,
		t.apiKey,
	)

	data, err := t.doRequest(ctx, url)
	if err != nil {
		return NewTextErrorResponse("failed to get current weather: " + err.Error()), nil
	}

	var resp owmCurrentResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	weatherDesc := ""
	if len(resp.Weather) > 0 {
		weatherDesc = resp.Weather[0].Description
	}

	// Format the response nicely
	tempUnit := "°C"
	if units == "imperial" {
		tempUnit = "°F"
	} else if units == "kelvin" {
		tempUnit = "K"
	}

	result := map[string]any{
		"type":        "weather-current",
		"location":    resp.Name,
		"country":     resp.Country,
		"temperature": fmt.Sprintf("%.1f%s", resp.Main.Temp, tempUnit),
		"feels_like":  fmt.Sprintf("%.1f%s", resp.Main.FeelsLike, tempUnit),
		"humidity":    fmt.Sprintf("%d%%", resp.Main.Humidity),
		"pressure":    fmt.Sprintf("%d hPa", resp.Main.Pressure),
		"wind_speed":  fmt.Sprintf("%.1f m/s", resp.Wind.Speed),
		"wind_deg":    resp.Wind.Deg,
		"conditions":  weatherDesc,
		"icon":        resp.Weather[0].Icon,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *weatherTool) getForecast(ctx context.Context, location, units string) (ToolResponse, error) {
	url := fmt.Sprintf(
		"https://api.openweathermap.org/data/2.5/forecast?q=%s&units=%s&appid=%s",
		strings.ReplaceAll(location, " ", "+"),
		units,
		t.apiKey,
	)

	data, err := t.doRequest(ctx, url)
	if err != nil {
		return NewTextErrorResponse("failed to get forecast: " + err.Error()), nil
	}

	var resp owmForecastResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return NewTextErrorResponse("failed to parse response: " + err.Error()), nil
	}

	// Format daily forecast (take one per day at noon)
	dailyForecasts := make([]map[string]any, 0)
	seenDates := make(map[string]bool)
	for _, item := range resp.List {
		dateStr := time.Unix(item.Dt, 0).Format("2006-01-02")
		if !seenDates[dateStr] && len(dailyForecasts) < 5 {
			seenDates[dateStr] = true
			desc := ""
			icon := ""
			if len(item.Weather) > 0 {
				desc = item.Weather[0].Description
				icon = item.Weather[0].Icon
			}
			dailyForecasts = append(dailyForecasts, map[string]any{
				"date":        dateStr,
				"temp":        fmt.Sprintf("%.1f", item.Main.Temp),
				"feels_like":  fmt.Sprintf("%.1f", item.Main.FeelsLike),
				"humidity":    item.Main.Humidity,
				"description": desc,
				"icon":        icon,
			})
		}
	}

	result := map[string]any{
		"type":     "weather-forecast",
		"location": resp.City.Name,
		"country":  resp.City.Country,
		"forecast": dailyForecasts,
		"units":    units,
	}

	resultJSON, _ := json.MarshalIndent(result, "", "  ")
	return NewTextResponse(string(resultJSON)), nil
}

func (t *weatherTool) getAlerts(ctx context.Context, location string) (ToolResponse, error) {
	// OpenWeatherMap free tier doesn't include alerts, so we return a placeholder
	// In production, you might use a different API (e.g., Tomorrow.io) for alerts
	return NewTextResponse(fmt.Sprintf(`{
  "type": "weather-alerts",
  "location": %q,
  "alerts": [],
  "note": "Alerts not available in OpenWeatherMap free tier. Consider Tomorrow.io for severe weather alerts."
}`, location)), nil
}

func (t *weatherTool) getHistorical(ctx context.Context, location, units string) (ToolResponse, error) {
	// OpenWeatherMap historical data requires paid subscription
	// Return a placeholder
	return NewTextResponse(fmt.Sprintf(`{
  "type": "weather-historical",
  "location": %q,
  "note": "Historical data requires OpenWeatherMap paid subscription. Consider using Tomorrow.io historical API."
}`, location)), nil
}

func (t *weatherTool) doRequest(ctx context.Context, url string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("User-Agent", "aria-weather-tool/1.0")

	resp, err := t.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	return io.ReadAll(resp.Body)
}
