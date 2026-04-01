// Package startup provides a comprehensive health check and auto-recovery system
// for ARIA's startup process.
//
// # Universal Startup System
//
// The startup system coordinates initialization of all ARIA services across
// multiple phases, providing health checking, circuit breaking, and graceful
// degradation for optional services.
//
// # Phases
//
// Phase 0 (PRE-FLIGHT): Critical services with 30s timeout
//
//   - Config Loader (priority 10)
//   - Data Directory (priority 20)
//   - SQLite Connection (priority 30)
//   - Schema Migration (priority 40)
//
// Phase 1 (CORE SERVICES): Important services with 60s timeout
//
//   - Session Service (priority 110)
//   - Message Service (priority 120)
//   - History Service (priority 130)
//   - Permission Service (priority 140)
//   - LLM Provider Config (priority 150)
//
// Phase 2 (ARIA COMPONENTS): Core ARIA services with 90s timeout
//
//   - Skill Registry (priority 210)
//   - Memory Service (priority 220)
//   - Development Agency (priority 230)
//   - Knowledge Agency (priority 240)
//   - Weather/Nutrition Agency (priority 250)
//   - Orchestrator (priority 260)
//   - Scheduler/Workers (priority 270)
//   - Guardrail/Permission (priority 280)
//
// Phase 3 (OPTIONAL SERVICES): Background services, non-blocking
//
//   - LSP Clients (priority 310) - continue if fails
//   - MCP Tools (priority 320) - continue if fails
//   - Embedding Worker (priority 330) - continue if fails
//
// # Usage
//
//	checkers := []startup.Checker{
//	    &configChecker{},
//	    &databaseChecker{},
//	}
//	manager := startup.NewBootstrapManager(checkers)
//	if err := manager.Bootstrap(context.Background()); err != nil {
//	    // handle error
//	}
package startup
