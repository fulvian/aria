package telemetry

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestTelemetryConfig_Default(t *testing.T) {
	t.Parallel()

	cfg := DefaultTelemetryConfig()

	assert.True(t, cfg.Enabled)
	assert.Equal(t, 5000, cfg.FlushIntervalMs)
	assert.Equal(t, 1000, cfg.MaxEvents)
}

func TestTelemetryConfig_FlushInterval(t *testing.T) {
	t.Parallel()

	cfg := TelemetryConfig{
		FlushIntervalMs: 10000,
	}

	interval := cfg.FlushInterval()
	assert.Equal(t, 10*time.Second, interval)
}

func TestTelemetryConfig_Validate(t *testing.T) {
	t.Parallel()

	t.Run("valid config", func(t *testing.T) {
		cfg := TelemetryConfig{
			Enabled:         true,
			FlushIntervalMs: 5000,
			MaxEvents:       1000,
		}

		err := cfg.Validate()
		require.NoError(t, err)
	})

	t.Run("negative flush interval", func(t *testing.T) {
		cfg := TelemetryConfig{
			FlushIntervalMs: -1,
		}

		err := cfg.Validate()
		require.Error(t, err)
		assert.Contains(t, err.Error(), "FlushIntervalMs must be non-negative")
	})

	t.Run("negative max events", func(t *testing.T) {
		cfg := TelemetryConfig{
			MaxEvents: -1,
		}

		err := cfg.Validate()
		require.Error(t, err)
		assert.Contains(t, err.Error(), "MaxEvents must be non-negative")
	})
}

func TestNewTelemetryServiceWithConfig(t *testing.T) {
	t.Parallel()

	t.Run("valid config", func(t *testing.T) {
		cfg := DefaultTelemetryConfig()
		svc, err := NewTelemetryServiceWithConfig(cfg)
		require.NoError(t, err)
		require.NotNil(t, svc)
	})

	t.Run("invalid config", func(t *testing.T) {
		cfg := TelemetryConfig{
			FlushIntervalMs: -1,
		}

		svc, err := NewTelemetryServiceWithConfig(cfg)
		require.Error(t, err)
		require.Nil(t, svc)
		assert.Contains(t, err.Error(), "invalid telemetry config")
	})
}

func TestTelemetryConfig_ZeroValues(t *testing.T) {
	t.Parallel()

	cfg := TelemetryConfig{}

	assert.False(t, cfg.Enabled)
	assert.Equal(t, 0, cfg.FlushIntervalMs)
	assert.Equal(t, 0, cfg.MaxEvents)

	err := cfg.Validate()
	require.NoError(t, err)
}
