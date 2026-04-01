package checkers

import (
	"context"

	"github.com/fulvian/aria/internal/startup"
)

// LSPChecker verifies LSP client connectivity.
type LSPChecker struct{}

// NewLSPChecker creates a new LSPChecker.
func NewLSPChecker() *LSPChecker {
	return &LSPChecker{}
}

// Name returns the checker name.
func (c *LSPChecker) Name() string {
	return "lsp"
}

// Priority returns the priority (310 - optional phase).
func (c *LSPChecker) Priority() int {
	return 310
}

// Check verifies the LSP client is operational.
// This is an optional service, so failures don't block startup.
func (c *LSPChecker) Check(ctx context.Context) error {
	// In a full implementation, we would:
	// 1. Check if any LSP servers are configured
	// 2. Attempt to connect to each configured server
	// 3. Verify the server responds to initialize request
	//
	// For now, this is a placeholder that always succeeds
	// since LSP initialization is handled asynchronously in the app
	return nil
}

// Ensure implementation satisfies the interface
var _ startup.Checker = (*LSPChecker)(nil)
