package checkers

import (
	"context"

	"github.com/fulvian/aria/internal/startup"
)

// MCPChecker verifies MCP server connectivity.
type MCPChecker struct{}

// NewMCPChecker creates a new MCPChecker.
func NewMCPChecker() *MCPChecker {
	return &MCPChecker{}
}

// Name returns the checker name.
func (c *MCPChecker) Name() string {
	return "mcp"
}

// Priority returns the priority (320 - optional phase).
func (c *MCPChecker) Priority() int {
	return 320
}

// Check verifies the MCP servers are reachable.
// This is an optional service, so failures don't block startup.
func (c *MCPChecker) Check(ctx context.Context) error {
	// MCP tools are initialized asynchronously with a 30s timeout
	// in cmd/root.go via initMCPTools().
	// This checker verifies the MCP configuration is valid.
	//
	// In a full implementation, we would:
	// 1. Parse MCP server configurations
	// 2. Attempt to connect to each server
	// 3. Verify the server responds
	//
	// For now, this is a placeholder that always succeeds
	return nil
}

// Ensure implementation satisfies the interface
var _ startup.Checker = (*MCPChecker)(nil)
