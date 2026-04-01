# AGENTS.md

Guide for agentic coding agents working in this repository.

## Project Overview

ARIA is a terminal-based AI coding assistant written in Go, featuring a TUI built with
Bubble Tea, supports multiple LLM providers (Anthropic, OpenAI, Gemini, Copilot, Bedrock,
Azure, VertexAI, OpenRouter, Groq, XAI), and uses SQLite for persistence via sqlc-generated
query code.

## ARIA Agency Architecture

ARIA implements a hierarchical multi-agent architecture:

```
Orchestrator (Core)
├── Development Agency (coding, devops, testing)
├── Weather Agency (meteo, alerts)
├── Nutrition Agency (recipes, nutrition, meal plans)
└── Knowledge Agency (web search, research, synthesis)
    ├── SemanticRouter (cosine similarity routing)
    ├── TaskRouter (keyword + semantic fallback)
    ├── Agents (web-search, academic, news, code, historical)
    └── ResultSynthesizer (quality gates, citation validation)
```

### Knowledge Agency

The Knowledge Agency provides intelligent web search and research capabilities:

- **Semantic Routing**: Uses embeddings for intelligent task classification
- **Multi-provider Chain**: Tavily, Brave, DuckDuckGo, Wikipedia, arXiv, PubMed, Semantic Scholar, etc.
- **Quality Gates**: Citation validation, contradiction detection
- **Memory Integration**: Learns from previous searches

## Build, Lint, and Test Commands

### Build

```bash
go build -o aria ./main.go
```

### Run

```bash
./aria              # Interactive TUI mode
./aria -d           # Debug mode
./aria -p "prompt"  # Non-interactive mode
```

### Test

```bash
go test ./...                              # Run all tests
go test ./internal/llm/tools/...           # Run tests for a specific package
go test -run TestLsTool_Run ./internal/llm/tools/  # Run a single test
go test -v ./internal/tui/theme/           # Verbose output
```

### Lint / Vet

```bash
go vet ./...
```

There is no Makefile. CI uses `go mod download` then goreleaser for builds.

### Code Generation (sqlc)

If you modify SQL queries in `internal/db/sql/` or migrations in `internal/db/migrations/`,
regenerate the Go code:

```bash
sqlc generate
```

## Project Structure

```
main.go                  # Entry point; calls cmd.Execute()
cmd/                     # Cobra CLI commands (root.go)
internal/
  app/                   # App initialization, LSP, shutdown
  aria/                   # ARIA Agency Architecture
    agency/              # Agency implementations (knowledge, development, weather, nutrition)
    config/              # ARIA-specific configuration
    core/                # Orchestrator, pipeline, routing
    memory/               # Working, episodic, semantic, procedural memory
    routing/             # Query classification, policy routing, capability registry
    scheduler/           # Task scheduling and dispatching
    skill/               # Skill registry and implementations
    guardrail/           # Safety guardrails
    permission/           # Permission service
    analysis/            # Self-analysis service
    toolgovernance/      # Tool governance with Allow/Ask/Deny policies
  config/                # Main configuration loading (Viper + JSON + env vars)
  db/                    # SQLite connection, sqlc-generated code, migrations
  diff/                  # Diff utilities
  fileutil/              # File utilities
  format/                # Output formatting (text, JSON)
  history/               # File history/versioning service
  llm/
    agent/               # Agent orchestration (coder, summarizer, title agents)
    models/              # Model definitions and supported model registry
    prompt/              # System prompts for each agent type
    provider/            # LLM provider implementations (Anthropic, OpenAI, etc.)
    tools/               # Tool implementations (bash, file edit, grep, glob, etc.)
  logging/               # Structured logging (slog-based) + panic recovery
  lsp/                   # Language Server Protocol client management
  message/               # Message domain model and service
  permission/            # Permission service for tool execution approval
  pubsub/                # Generic pub/sub broker for events
  session/               # Session domain model and service
  tui/                   # Terminal UI (Bubble Tea)
    components/          # Reusable UI components
    layout/              # Layout management
    page/                # Page-level views
    styles/              # Shared style definitions
    theme/               # Theme system (catppuccin, gruvbox, monokai, etc.)
    util/                # TUI utilities
  version/               # Version info (set at build time via ldflags)
scripts/                 # Release and utility shell scripts
sqlc.yaml                # sqlc configuration
.env                     # Environment variables (API keys, etc.)
ARIA.md                  # ARIA memory guidance file
```

## Code Style Guidelines

### Imports

- Group imports into three sections separated by blank lines:
  1. Standard library packages
  2. Third-party packages
  3. Internal packages (`github.com/fulvian/aria/internal/...`)
- Use import aliases consistently: `tea "github.com/charmbracelet/bubbletea"`,
  `zone "github.com/lrstanley/bubblezone"`

### Formatting

- Use `gofmt` standard formatting (tabs for indentation).
- Use `0o` octal prefix for file permissions: `0o755`, `0o644`, `0o700`.

### Types and Structs

- Use Go's `string` type for enums (e.g., `type AgentName string`,
  `type EventType string`).
- Use `type` aliases for domain identifiers: `type ModelID string`.
- Prefer value receivers for struct types; use pointer receivers when mutation is needed.
- Use `sql.NullString` / `sql.NullInt64` for nullable database columns.
- Define parameter and response structs for tools (e.g., `BashParams`,
  `ToolResponse`).
- Add `json` tags to all config and database model structs.

### Naming Conventions

- Package names: lowercase, single word, no underscores (e.g., `pubsub`, `fileutil`).
- Exported constants: `CamelCase` (e.g., `AgentCoder`, `EventContentDelta`).
- Unexported helpers: `camelCase` (e.g., `createAgentProvider`, `setProviderDefaults`).
- Interface names: single-method interfaces end in `-er` or descriptive nouns
  (e.g., `Service`, `BaseTool`, `Provider`).
- Tool name constants: PascalCase (e.g., `BashToolName = "bash"`).
- Test function names: `TestXxx` with subtests using `t.Run("description", ...)`.

### Error Handling

- Wrap errors with context using `fmt.Errorf("verb: %w", err)`.
- Return `nil` for non-critical errors when appropriate (e.g., config file not found).
- Use `errors.Is()` for error comparison (e.g., `errors.Is(err, context.Canceled)`).
- Use `logging.RecoverPanic("name", cleanupFunc)` in goroutines for panic recovery.
- Log errors with `logging.Error()` or `logging.ErrorPersist()` for critical issues.
- Tool implementations return `ToolResponse` with `IsError: true` rather than
  Go errors for expected failure cases.

### Concurrency

- Use `sync.Map` for concurrent-safe maps (e.g., `activeRequests`).
- Use `sync.RWMutex` for read-heavy concurrent access (e.g., LSP client map).
- Always use `defer logging.RecoverPanic(...)` in goroutines.
- Use channels with `select`/`context` for goroutine cancellation.
- Provide timeout-based fallbacks when waiting on goroutines.

### Testing

- Place test files alongside the code they test (`*_test.go` in the same package).
- Use `testing.T` directly for simple tests; use `testify/assert` and
  `testify/require` for assertions.
- Use `t.Parallel()` where tests are safe to parallelize.
- Use `t.TempDir()` for filesystem-dependent tests.
- Use `t.Helper()` in test helper functions.
- Use table-driven tests with `t.Run()` for multiple cases.

### Architecture Patterns

- **Service pattern**: Domain packages expose a `Service` interface and a
  `NewService()` constructor (e.g., `session.NewService(q)`).
- **Pub/Sub**: Components communicate via `pubsub.Broker[T]` — subscribe to
  typed events through a `Subscribe(ctx) <-chan Event[T]` method.
- **Tool interface**: All LLM tools implement `BaseTool` with `Info()` and
  `Run(ctx, ToolCall) (ToolResponse, error)`.
- **Provider pattern**: LLM providers implement the `Provider` interface with
  `SendMessages` and `StreamResponse` methods. A generic `baseProvider[C]`
  wraps provider-specific clients.
- **Configuration**: Global singleton via `config.Load()` / `config.Get()`.
- **Functional options**: Provider configuration uses the functional options
  pattern (`WithAPIKey()`, `WithModel()`, etc.).

### Database

- Migrations live in `internal/db/migrations/` and are applied via goose.
- SQL queries live in `internal/db/sql/*.sql` using sqlc annotation format.
- Never edit generated Go files (`*sql.go`, `models.go`, `querier.go`) directly.
- Run `sqlc generate` after modifying SQL files or migrations.

---

## ARIA Project Implementation Rules

This project is governed by `docs/foundation/BLUEPRINT.md` — the foundation blueprint
document that defines the ARIA (Autonomous Reasoning & Intelligent Assistant) architecture.
**All implementation work MUST align with this document until it reaches completion.**

### Core Principle: BLUEPRINT.md as North Star

The BLUEPRINT.md document is the **single source of truth** for:
- Architecture decisions and design patterns
- Phase ordering and progression criteria
- Deliverable definitions and acceptance criteria
- Entity definitions (Agencies, Agents, Skills, Tools)

**Until the document status changes from `FOUNDATIONAL` to `COMPLETED`, every
implementation decision must be traceable to a specific section in BLUEPRINT.md.**

### Phase Progression Rules

1. **Sequential Phase Enforcement**: Implementation MUST proceed in phase order
   (FASE 0 → FASE 1 → FASE 2 → ... → FASE 6). Do not begin work on a later phase
   until the current phase's deliverables are complete and verified.

2. **Phase Gate Verification**: Before closing a phase, verify:
   - [ ] All deliverables in the phase's checklist are implemented
   - [ ] All interfaces defined in BLUEPRINT.md are implemented
   - [ ] Tests exist for core functionality
   - [ ] Documentation reflects actual implementation

3. **Blocking Issues**: If implementation reveals architectural changes are needed,
   update BLUEPRINT.md first via the version control process below. Do not silently
   deviate from the blueprint.

### Document Update Requirements

**When making significant progress or changes, you MUST update BLUEPRINT.md:**

1. **Progress Updates**: After completing any deliverable, update the phase's progress
   indicator in the roadmap (Section 8.1) to reflect actual completion percentage.

2. **Version Bumping**: Follow semantic versioning for the blueprint:
   - `MAJOR.MINOR.PATCH-DRAFT` for incomplete work (e.g., `1.0.0-DRAFT` → `1.1.0-DRAFT`)
   - `MAJOR.MINOR.PATCH` when a phase is fully completed
   - Major: Architectural changes to core entities (Orchestrator, Agency, Agent)
   - Minor: New entities, skills, or significant feature additions
   - Patch: Bug fixes, documentation updates, small refinements

3. **Change Log Maintenance**: Every version bump requires a Change Log entry documenting:
   - What changed
   - Why it changed
   - Which implementation work necessitated the change

4. **Status Transitions**: Update document status at these milestones:
   - `FOUNDATIONAL` → `IN_PROGRESS` when FASE 0 begins
   - `IN_PROGRESS` → `EVOLVING` after first phase completion
   - Eventually → `COMPLETED` when all phases finished

### Implementation Traceability

Every code change related to ARIA should be traceable to a blueprint element:

| Code Location | Blueprint Reference |
|---------------|---------------------|
| `internal/aria/core/` | Parte II: Orchestrator (Section 2.2.1) |
| `internal/aria/agency/` | Parte II: Agency System (Section 2.2.2) |
| `internal/aria/agent/` | Parte II: Agent (Section 2.2.3) |
| `internal/aria/skill/` | Parte II: Skill (Section 2.2.4) |
| `internal/aria/routing/` | Parte II: Routing System (Section 2.3) |
| `internal/aria/memory/` | Parte III: Memory System (Section 3.1-3.3) |
| `internal/aria/scheduler/` | Parte IV: Task Scheduling (Section 4.1-4.3) |
| `internal/aria/permission/` | Parte V: Permission System (Section 5.1) |
| `internal/aria/guardrail/` | Parte V: Guardrails (Section 5.2) |
| `internal/aria/analysis/` | Parte VI: Self-Analysis (Section 6.1) |

### Reference: Current Project State

From BLUEPRINT.md (as of last update):
- **Version**: 1.0.0-DRAFT
- **Status**: FOUNDATIONAL
- **Current Phase**: FASE 0 (Foundation) — estimated 40% complete
- **Target**: Transform OpenCode CLI into ARIA via 6 implementation phases
- **Next Milestone**: Complete FASE 0 deliverables before proceeding to FASE 1
