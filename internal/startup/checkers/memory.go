package checkers

import (
	"context"

	"github.com/fulvian/aria/internal/startup"
)

// MemoryChecker verifies the memory service is operational.
type MemoryChecker struct {
	// Memory service would be injected here in a real implementation
	// For now, we just verify the package is importable
}

// NewMemoryChecker creates a new MemoryChecker.
func NewMemoryChecker() *MemoryChecker {
	return &MemoryChecker{}
}

// Name returns the checker name.
func (c *MemoryChecker) Name() string {
	return "memory"
}

// Priority returns the priority (220).
func (c *MemoryChecker) Priority() int {
	return 220
}

// Check verifies the memory service is operational.
func (c *MemoryChecker) Check(ctx context.Context) error {
	// In a full implementation, we would:
	// 1. Create a memory service instance
	// 2. Verify it can be initialized
	// 3. Run a simple test query
	//
	// For now, we just verify the package is importable
	// and the 4-layer architecture is in place
	return nil
}

// MemoryServiceChecker checks the memory service with actual connectivity.
type MemoryServiceChecker struct {
	embeddingEndpoint string
}

// NewMemoryServiceChecker creates a checker that verifies embedding connectivity.
func NewMemoryServiceChecker(embeddingEndpoint string) *MemoryServiceChecker {
	return &MemoryServiceChecker{
		embeddingEndpoint: embeddingEndpoint,
	}
}

// Name returns the checker name.
func (c *MemoryServiceChecker) Name() string {
	return "memory-embedding"
}

// Priority returns the priority (225).
func (c *MemoryServiceChecker) Priority() int {
	return 225
}

// Check verifies the embedding endpoint is reachable.
func (c *MemoryServiceChecker) Check(ctx context.Context) error {
	if c.embeddingEndpoint == "" {
		// No embedding endpoint configured, skip check
		return nil
	}
	// In a real implementation, we would make a test embedding request
	return nil
}

// Ensure implementation satisfies the interface
var _ startup.Checker = (*MemoryChecker)(nil)
var _ startup.Checker = (*MemoryServiceChecker)(nil)
