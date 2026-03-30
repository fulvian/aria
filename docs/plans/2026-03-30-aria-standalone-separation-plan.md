# ARIA Standalone Separation Plan

**Date:** 2026-03-30
**Author:** General Manager
**Status:** EXECUTIVE APPROVAL REQUIRED (HitL Milestone)
**Objective:** Split ARIA into a completely standalone application, separate from OpenCode

---

## 1. Problem Statement

Currently ARIA is integrated into OpenCode as a component:
- Single entry point via `opencode` command
- Shared configuration via `.opencode.json`
- Interleaved packages (`internal/aria/` and `internal/llm/`)

**User Requirement:** ARIA must be completely autonomous:
- Invoked via `aria` command
- No shared configuration files
- Fully isolated from OpenCode

---

## 2. Target Architecture

```
aria/                          # Standalone ARIA CLI application
├── main.go                    # Entry point (or main_aria.go)
├── cmd/aria/
│   └── root.go                # 'aria' CLI command
├── cmd/opencode/              # Existing OpenCode CLI (renamed from cmd/)
│   └── root.go
├── internal/
│   ├── aria/                  # ARIA core (autonomous)
│   │   ├── config/           # ARIA config (env vars + aria.json)
│   │   ├── core/             # Orchestrator, Planner, Executor, Reviewer
│   │   ├── agency/           # DevelopmentAgency, WeatherAgency
│   │   ├── skill/            # Skills
│   │   ├── routing/          # Router, PolicyRouter
│   │   ├── memory/           # Memory service
│   │   ├── scheduler/        # Task scheduler
│   │   ├── guardrail/        # Guardrails
│   │   └── contracts/        # Shared types
│   │
│   ├── opencode/              # OpenCode core (autonomous, NEW)
│   │   ├── llm/              # LLM providers, agents, tools
│   │   ├── tui/              # Bubble Tea UI
│   │   └── ...other opencode-specific packages
│   │
│   └── shared/                # Shared infrastructure (NEW)
│       ├── db/                # SQLite + sqlc
│       ├── logging/           # slog-based logging
│       ├── pubsub/            # Event broker
│       ├── session/           # Session service
│       ├── message/           # Message service
│       └── ...other truly shared utilities
```

---

## 3. Separation Strategy

### 3.1 Package Structure Changes

| Current Location | Target Location | Notes |
|-----------------|-----------------|-------|
| `cmd/` | `cmd/opencode/` | Rename entire directory |
| `internal/llm/` | `internal/opencode/llm/` | Move into new opencode package |
| `internal/tui/` | `internal/opencode/tui/` | Move into new opencode package |
| `internal/config/` | `internal/opencode/config/` | Move into new opencode package |
| `cmd/orchestrator_commands.go` | `cmd/aria/` | ARIA gets its own commands |
| `internal/app/app.go` | Split: `internal/opencode/app.go` + `internal/aria/app.go` | |
| `internal/app/aria_integration.go` | `internal/aria/` | Already ARIA's concern |
| `main.go` | Split: `main_aria.go` + `main_opencode.go` | Or use build tags |

### 3.2 Configuration Separation

**ARIA Config:**
- Environment variables (`ARIA_*`) - already working
- Optional `aria.json` file in `~/.config/aria/` or project root
- NO `.opencode.json` dependency

**OpenCode Config:**
- Keep `.opencode.json` (removes `aria` section)
- Keep `internal/opencode/config/`

### 3.3 Shared Infrastructure

Packages that are truly shared and have no ARIA/OpenCode specific logic:
- `internal/shared/db/` - Database connection and migrations
- `internal/shared/logging/` - Logging utilities
- `internal/shared/pubsub/` - Event broker
- `internal/shared/format/` - Output formatting
- `internal/shared/version/` - Version info
- `internal/shared/diff/` - Diff utilities
- `internal/shared/history/` - File history
- `internal/shared/permission/` - Permission service (may need interface refinement)

---

## 4. Implementation Phases

### Phase S1: Prepare Directory Structure
**Tasks:**
1. Create `cmd/aria/` directory with `root.go`
2. Create `internal/opencode/` directory structure
3. Create `internal/shared/` directory structure
4. Move packages systematically

**Deliverable:** Clear package boundaries without code changes

### Phase S2: Create ARIA CLI Entry Point
**Tasks:**
1. Create `cmd/aria/root.go` with `aria` command
2. Create `main_aria.go` entry point
3. Wire ARIA components (Orchestrator, Agencies, etc.)
4. Remove ARIA wiring from OpenCode cmd

**Deliverable:** `aria` command works standalone

### Phase S3: Configuration Separation
**Tasks:**
1. Remove `aria` section from `.opencode.json`
2. Create `aria.json` schema and loader (optional config file)
3. Ensure ARIA config uses ONLY env vars and own config file
4. Ensure OpenCode config does not reference ARIA

**Deliverable:** No shared config files

### Phase S4: ARIA Splash Screen (ASCII Art Logo)
**Tasks:**
1. Design a beautiful, colorful ASCII art logo for ARIA
2. Create `internal/aria/ui/splash.go` with the ARIA logo rendering
3. Implement the splash screen in the ARIA startup flow
4. Use lipgloss for colors (cyan/blue primary, accent colors)
5. Add version information and tagline
6. Create `internal/aria/ui/icons.go` for ARIA-specific icons (ARIA icon replaces OpenCode icon)

**Design Requirements:**
- Large, visually impressive ASCII art spelling "ARIA"
- Color scheme: Cyan/blue primary with accent colors (gold, magenta)
- Include tagline: "Autonomous Reasoning & Intelligent Assistant"
- Display version information
- Show repository URL: `https://github.com/fulvian/aria`

**Splash Screen Content (Example):**
```
██████╗ ███████╗███████╗██╗   ██╗███╗   ███╗███████╗
██╔══██╗██╔════╝██╔════╝██║   ██║████╗ ████║██╔════╝
██████╔╝█████╗  ███████╗██║   ██║██╔████╔██║█████╗  
██╔═══╝ ██╔══╝  ╚════██║██║   ██║██║╚██╔╝██║██╔══╝  
██║     ███████╗███████║╚██████╔╝██║ ╚═╝ ██║███████╗
╚═╝     ╚══════╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝
                                                       
      Autonomous Reasoning & Intelligent Assistant
                          v1.0.0
              https://github.com/fulvian/aria
```

**Color Mapping (lipgloss):**
- Title "ARIA": Cyan (#00D9FF) - Bold, large
- Tagline: Blue (#0088FF) - Italic
- Version: Gold (#FFD700)
- URL: Magenta (#FF00FF)

**Deliverable:** Beautiful splash screen appears on ARIA startup

### Phase S5: Shared Infrastructure Refinement
**Tasks:**
1. Move truly shared packages to `internal/shared/`
2. Update import paths
3. Verify build for both `aria` and `opencode` commands

**Deliverable:** Clean separation with shared module

### Phase S6: Verification
**Tasks:**
1. `go build -o aria ./main_aria.go` succeeds
2. `go build -o opencode ./main_opencode.go` succeeds
3. `aria` command runs independently with splash screen
4. `opencode` command runs independently
5. All tests pass for both

**Deliverable:** Both commands work standalone

---

## 5. File-Level Changes

### New Files
```
cmd/aria/root.go                              # ARIA CLI command
main_aria.go                                  # ARIA entry point
internal/opencode/                            # New directory for OpenCode
internal/shared/                             # New directory for shared code
aria.json                                     # Optional ARIA config file
aria-schema.json                              # ARIA config schema
```

### Files to Move/Rename
```
cmd/              -> cmd/opencode/
internal/llm/     -> internal/opencode/llm/
internal/tui/     -> internal/opencode/tui/
internal/config/  -> internal/opencode/config/
internal/app/app.go -> internal/opencode/app.go
```

### Files to Delete/Modify
```
cmd/orchestrator_commands.go     # Move relevant parts to cmd/aria/
internal/app/aria_integration.go # Move to internal/aria/
.opencode.json                   # Remove aria section
.main.go (main.go rename)        # Split into main_aria.go + main_opencode.go
```

---

## 6. Backward Compatibility

- **ARIA existing features:** Fully preserved
- **OpenCode existing features:** Fully preserved
- **Environment variables:** `ARIA_*` already used, no change needed
- **Build process:** Both commands must build successfully

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing `go build` | Use build tags or separate entry points |
| Import cycle creation | Careful package dependency analysis before moving |
| Test breakage | Update test imports after package moves |
| Double maintenance of shared code | Clear ownership boundaries |

---

## 8. ARIA Splash Screen Design

### 8.1 Logo Concept
The ARIA splash screen replaces the simple `⌬ OpenCode` text logo with a bold, colorful ASCII art logo that fills the terminal and establishes ARIA's identity as a sophisticated AI assistant.

### 8.2 Implementation Details

**New Files:**
```
internal/aria/ui/splash.go      # Splash screen rendering
internal/aria/ui/icons.go      # ARIA icons (ARIAIcon replaces OpenCodeIcon)
internal/aria/ui/styles.go     # ARIA-specific lipgloss styles
```

**Modified Files:**
```
cmd/aria/root.go                # Add splash screen to startup
internal/aria/app.go            # Add splash screen to ARIA initialization
internal/tui/components/chat/chat.go  # Remove OpenCode logo (ARIA has own)
```

### 8.3 Color Palette (lipgloss AdaptiveColors)
| Element | Color | Hex |
|---------|-------|-----|
| ARIA Title | Cyan | #00D9FF |
| Tagline | Blue | #0088FF |
| Version | Gold | #FFD700 |
| URL | Magenta | #FF00FF |
| Border/Accent | White | #FFFFFF |

### 8.4 Animation (Optional Enhancement)
- Simple fade-in effect using lipgloss opacity transitions
- Or static display (acceptable for v1)

---

## 9. Next Steps (HitL Required)

1. **Approve this plan** - User must approve before implementation
2. **Phase S1 implementation** - Create directory structure
3. **Phase S2 implementation** - Create ARIA CLI
4. **Phase S3 implementation** - Separate configurations
5. **Phase S4 implementation** - Create ARIA splash screen
6. **Phase S5 implementation** - Refine shared infrastructure
7. **Phase S6 verification** - Build and test both commands

---

## 10. Acceptance Criteria

### General Separation
- [ ] `aria` command is available and works standalone
- [ ] `opencode` command works without any ARIA code
- [ ] No shared configuration files
- [ ] ARIA has its own config system (env vars + optional aria.json)
- [ ] Both commands build successfully
- [ ] All existing tests pass
- [ ] No circular dependencies between ARIA and OpenCode packages

### ARIA Splash Screen
- [ ] Beautiful ASCII art "ARIA" logo displays on startup
- [ ] Logo uses cyan/blue color scheme with accent colors
- [ ] Tagline "Autonomous Reasoning & Intelligent Assistant" is displayed
- [ ] Version number is shown
- [ ] Repository URL is displayed
- [ ] Splash screen appears before interactive TUI starts
- [ ] OpenCode logo is NOT shown in ARIA's UI
- [ ] ARIA has its own icon (`⌬` or custom)
