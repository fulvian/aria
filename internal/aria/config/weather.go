// Package config provides weather-specific configuration.
package config

import (
	"os"
)

// WeatherConfig holds Weather Agency configuration.
type WeatherConfig struct {
	// Provider specifies the weather API provider (openweathermap, tomorrowio).
	Provider string

	// APIKey is the API key for the weather service.
	APIKey string

	// DefaultUnits specifies default units (metric, imperial, kelvin).
	DefaultUnits string

	// DefaultLocation is the default location if none specified.
	DefaultLocation string
}

// DefaultWeatherConfig returns default weather configuration.
func DefaultWeatherConfig() WeatherConfig {
	return WeatherConfig{
		Provider:        getEnv("ARIA_WEATHER_PROVIDER", "openweathermap"),
		APIKey:          os.Getenv("ARIA_WEATHER_API_KEY"),
		DefaultUnits:    getEnv("ARIA_WEATHER_DEFAULT_UNITS", "metric"),
		DefaultLocation: getEnv("ARIA_WEATHER_DEFAULT_LOCATION", ""),
	}
}

// IsConfigured returns true if weather is properly configured.
func (c WeatherConfig) IsConfigured() bool {
	return c.APIKey != "" && c.Provider != ""
}
