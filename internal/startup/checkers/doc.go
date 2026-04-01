// Package checkers provides health check implementations for the startup system.
//
// Each checker implements the startup.Checker interface and is assigned a priority
// that determines when it runs during the bootstrap process.
//
// Checkers are organized by the startup phase they belong to:
//
// Phase 0 (PRE-FLIGHT, priority 0-99):
//   - ConfigChecker (10): Verifies configuration is valid
//   - DataDirChecker (20): Verifies data directory is accessible
//   - DatabaseChecker (30): Verifies SQLite connection
//
// Phase 1 (CORE SERVICES, priority 100-199):
//   - LLMProviderChecker (150): Verifies LLM provider configuration
//
// Phase 2 (ARIA COMPONENTS, priority 200-299):
//   - MemoryChecker (220): Verifies memory service
//   - MemoryServiceChecker (225): Verifies embedding endpoint
//
// Phase 3 (OPTIONAL SERVICES, priority 300-399):
//   - LSPChecker (310): Verifies LSP client connectivity (optional)
//   - MCPChecker (320): Verifies MCP server connectivity (optional)
package checkers
