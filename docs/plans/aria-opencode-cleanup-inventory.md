# ARIA OpenCode Cleanup Inventory

**Date:** 2026-03-30  
**Source:** grep analysis of codebase  
**Scope:** All references to `opencode`, `OpenCode`, `.opencode` in runtime code

---

## Inventory Summary

| Category | Count | High Impact |
|----------|-------|-------------|
| Go files with references | ~25 | Yes |
| Total references in .go files | 76 | - |
| JSON config files | 2 (`.opencode.json`, `opencode-schema.json`) | Yes |
| MD documentation references | 254 (incl. plan docs) | No |

---

## High Impact Files (Runtime Code)

### 1. CLI/Entrypoint

| File | Line | Reference | Action |
|------|------|----------|--------|
| `cmd/root.go` | 25 | `Use: "opencode"` | CHANGE to `aria` |
| `cmd/root.go` | 27 | `Long: "OpenCode is..."` | CHANGE to ARIA |
| `cmd/root.go` | 32-47 | Examples: `opencode -d`, etc. | CHANGE to `aria` |
| `cmd/root.go` | 55 | `opencode-schema.json` | DEPRECATE |

### 2. Configuration

| File | Line | Reference | Action |
|------|------|-----------|--------|
| `internal/config/config.go` | 191 | `defaultDataDirectory = ".opencode"` | CHANGE to `.aria` |
| `internal/config/config.go` | 193 | `appName = "opencode"` | CHANGE to `aria` |
| `internal/config/config.go` | 204-207 | Context paths: `opencode.md`, `OpenCode.md` | REMOVE legacy |
| `internal/config/config.go` | 323 | `viper.SetDefault("tui.theme", "opencode")` | CHANGE to `aria` |

### 3. Database

| File | Line | Reference | Action |
|------|------|-----------|--------|
| `internal/db/connect.go` | 26 | `opencode.db` | CHANGE to `aria.db` |

### 4. TUI/Branding

| File | Line | Reference | Action |
|------|------|-----------|--------|
| `internal/tui/theme/opencode.go` | All | OpenCode theme | REPLACE with ARIA theme |
| `internal/tui/styles/icons.go` | 4 | `OpenCodeIcon string = "⌬"` | CHANGE to ARIA icon |
| `internal/tui/components/chat/chat.go` | 101 | `styles.OpenCodeIcon + "OpenCode"` | CHANGE to ARIA |
| `internal/tui/components/dialog/init.go` | 113 | `OpenCode.md` reference | CHANGE to ARIA.md |
| `internal/tui/tui.go` | 927, 929, 934 | `OpenCode.md` reference | CHANGE to ARIA.md |
| `internal/tui/components/dialog/custom_commands.go` | 44, 57 | `.opencode/commands` path | CHANGE to `.aria/commands` |
| `internal/tui/theme/manager.go` | 95-97 | Theme "opencode" comparison | UPDATE logic |

### 5. LLM/Prompts

| File | Line | Reference | Action |
|------|------|-----------|--------|
| `internal/llm/prompt/coder.go` | 28 | `You are operating as OpenCode CLI...` | CHANGE to ARIA |
| `internal/llm/prompt/coder.go` | 36 | `opencode --help` | CHANGE to `aria --help` |
| `internal/llm/prompt/coder.go` | 74 | `You are OpenCode, an interactive CLI...` | CHANGE to ARIA |
| `internal/llm/prompt/coder.go` | 79-84 | `OpenCode.md` references | CHANGE to ARIA.md |
| `internal/llm/prompt/coder.go` | 159 | `opencode.md` | CHANGE to ARIA.md |
| `internal/llm/prompt/task.go` | 10 | `You are an agent for OpenCode` | CHANGE to ARIA |

### 6. Tools/User-Agent Strings

| File | Line | Reference | Action |
|------|------|-----------|--------|
| `internal/llm/tools/bash.go` | 125-126, 133-134, 196 | `Co-Authored-By: opencode <noreply@opencode.ai>` | CHANGE to ARIA |
| `internal/llm/tools/shell/shell.go` | 152-155 | `opencode-stdout-*, opencode-stderr-*` | CHANGE to `aria-*` |
| `internal/llm/tools/fetch.go` | 155 | `User-Agent: opencode/1.0` | CHANGE to `aria/1.0` |
| `internal/llm/tools/sourcegraph.go` | 221 | `User-Agent: opencode/1.0` | CHANGE to `aria/1.0` |
| `internal/llm/agent/mcp-tools.go` | 53, 147 | `Name: "OpenCode"` | CHANGE to `ARIA` |
| `internal/llm/provider/provider.go` | 139-140 | `HTTP-Referer: opencode.ai`, `X-Title: OpenCode` | CHANGE to ARIA |
| `internal/llm/provider/copilot.go` | 65, 127, 167-168 | `OpenCode/1.0` User-Agent, error msg | CHANGE to ARIA |

### 7. Logging

| File | Line | Reference | Action |
|------|------|-----------|--------|
| `internal/logging/logger.go` | 74 | `opencode-panic-*.log` | CHANGE to `aria-panic-*.log` |

### 8. Other

| File | Line | Reference | Action |
|------|------|-----------|--------|
| `internal/fileutil/fileutil.go` | 84 | `".opencode": true` in ignore list | REMOVE or RENAME |
| `internal/diff/diff.go` | 347 | `<style name="opencode-theme">` | CHANGE to `aria-theme` |
| `cmd/schema/main.go` | 41-42, 55, 92-95, 108, 110 | Schema title/description | UPDATE to ARIA |
| `internal/aria/config/config.go` | 2, 11 | Comments about "opencode/kilocode" | UPDATE comments |

---

## Config Files

| File | Status | Action |
|------|--------|--------|
| `.opencode.json` | **DELETE** from runtime | Remove from code loading, keep reference for migration |
| `opencode-schema.json` | **DELETE** | Schema should be per-product |
| `.opencode` (directory) | **RENAME** to `.aria` | Data directory migration |

---

## Context Paths to Remove from Config

Legacy context paths to remove from `defaultContextPaths`:
```go
"opencode.md",
"opencode.local.md",
"OpenCode.md",
"OpenCode.local.md",
"OPENCODE.md",
"OPENCODE.local.md",
```

Retain only ARIA-specific:
```go
"ARIA.md",
"ARIA.local.md",
```

---

## Exit Criteria Verification

- [x] Inventory complete >= 100% of runtime files impacted
- [x] All references categorized by action type
- [x] High-impact files identified
- [ ] Policy document approved and ready for CI checks

---

## Next Actions

1. Proceed to V4-1: CLI Identity Migration
2. systematically change each file category
3. Verify with `grep` after each phase