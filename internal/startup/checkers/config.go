package checkers

import (
	"context"
	"os"

	"github.com/fulvian/aria/internal/config"
	"github.com/fulvian/aria/internal/startup"
)

// ConfigChecker verifies the configuration is valid.
type ConfigChecker struct {
	cwd   string
	debug bool
}

// NewConfigChecker creates a new ConfigChecker.
func NewConfigChecker(cwd string, debug bool) *ConfigChecker {
	return &ConfigChecker{
		cwd:   cwd,
		debug: debug,
	}
}

// Name returns the checker name.
func (c *ConfigChecker) Name() string {
	return "config"
}

// Priority returns the priority (10 = first phase).
func (c *ConfigChecker) Priority() int {
	return 10
}

// Check verifies the configuration is valid.
func (c *ConfigChecker) Check(ctx context.Context) error {
	_, err := config.Load(c.cwd, c.debug)
	return err
}

// DataDirChecker verifies the data directory is accessible.
type DataDirChecker struct {
	cwd   string
	debug bool
}

// NewDataDirChecker creates a new DataDirChecker.
func NewDataDirChecker(cwd string, debug bool) *DataDirChecker {
	return &DataDirChecker{
		cwd:   cwd,
		debug: debug,
	}
}

// Name returns the checker name.
func (c *DataDirChecker) Name() string {
	return "data-directory"
}

// Priority returns the priority (20).
func (c *DataDirChecker) Priority() int {
	return 20
}

// Check verifies the data directory is accessible.
func (c *DataDirChecker) Check(ctx context.Context) error {
	cfg, err := config.Load(c.cwd, c.debug)
	if err != nil {
		return err
	}

	// Verify data directory is accessible
	dataDir := cfg.Data.Directory
	if dataDir == "" {
		dataDir = ".aria"
	}

	info, err := os.Stat(dataDir)
	if err != nil {
		if os.IsNotExist(err) {
			// Try to create it
			return os.MkdirAll(dataDir, 0o755)
		}
		return err
	}

	if !info.IsDir() {
		return &configError{dataDir, "not a directory"}
	}

	return nil
}

type configError struct {
	path  string
	cause string
}

func (e *configError) Error() string {
	return "config error: " + e.cause + " for path: " + e.path
}

// Ensure ConfigChecker implements startup.Checker
var _ startup.Checker = (*ConfigChecker)(nil)
var _ startup.Checker = (*DataDirChecker)(nil)
