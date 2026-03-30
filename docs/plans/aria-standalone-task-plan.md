# ARIA Standalone Separation Plan v4 - Implementation

## Plan Reference
`docs/plans/2026-03-30-aria-standalone-separation-plan-v4.md`

## Objective
Completare l'autonomia di ARIA nel repository attuale, eliminando ogni riferimento operativo a OpenCode nel codice, mantenendo solo attribution nei credits ufficiali.

## Status
**IMPLEMENTATION IN PROGRESS** - Core changes complete

---

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| V4-0: Boundary Audit & Inventory | ✅ COMPLETE | Inventory + boundary policy docs created |
| V4-1: CLI Identity Migration | ✅ COMPLETE | `aria` command, help, theme default |
| V4-2: Contracts & Dependency Inversion | ✅ N/A | Not needed for single product |
| V4-3: Package Normalization & Runtime Renaming | ✅ COMPLETE | All OpenCode refs removed from Go |
| V4-4: Config & Data Isolation | ✅ COMPLETE | `.aria` paths, `aria.json` config |
| V4-5: Identity & UX Separation | ✅ COMPLETE | ARIA theme, ARIA.md, icons |
| V4-6: Documentation, Credits & Policy | 🔄 IN PROGRESS | Add credits to docs |
| V4-7: CI/CD, Release Engineering, Hardening | Pending | |

---

## Inventory (from grep)

### High Impact Files to Modify
1. `cmd/root.go` - `Use: "opencode"`, help, examples
2. `internal/config/config.go` - `appName = "opencode"`, `.opencode` paths, theme default
3. `internal/tui/theme/opencode.go` - OpenCode theme
4. `internal/tui/components/chat/chat.go` - OpenCode logo
5. `internal/tui/styles/icons.go` - OpenCodeIcon
6. `internal/tui/components/dialog/init.go` - OpenCode.md reference
7. `internal/tui/tui.go` - OpenCode.md reference
8. `internal/db/connect.go` - `opencode.db`
9. `internal/llm/prompt/coder.go` - OpenCode prompts
10. `internal/llm/prompt/task.go` - OpenCode prompt
11. `internal/llm/tools/bash.go` - Co-Authored-By: opencode
12. `internal/llm/agent/mcp-tools.go` - "OpenCode" name
13. `internal/llm/provider/provider.go` - opencode.ai HTTP headers
14. `internal/llm/provider/copilot.go` - OpenCode User-Agent
15. `internal/llm/tools/fetch.go` - opencode User-Agent
16. `internal/llm/tools/sourcegraph.go` - opencode User-Agent
17. `internal/llm/tools/shell/shell.go` - opencode-* temp files
18. `internal/logging/logger.go` - opencode-panic-*.log
19. `internal/tui/components/dialog/custom_commands.go` - .opencode/commands path
20. `internal/fileutil/fileutil.go` - .opencode in ignore list
21. `internal/diff/diff.go` - opencode-theme style
22. `cmd/schema/main.go` - Schema references

### Files to Create
- `docs/plans/aria-opencode-cleanup-inventory.md`
- `docs/plans/aria-boundary-policy.md`
- `internal/aria/ui/splash.go` (ARIA splash screen)
- `internal/aria/ui/icons.go` (ARIA icons)
- `internal/aria/ui/styles.go` (ARIA styles)

### Files to Delete/Deprecate
- `.opencode.json` (runtime deprecated)
- `opencode-schema.json` (if standalone)

### Credits Documentation
- Add "ARIA is based on OpenCode..." to README/ACKNOWLEDGEMENTS

---

## Execution Order

1. V4-0: Create inventory and boundary policy docs
2. V4-1: CLI identity migration (cmd/root.go)
3. V4-2: Contracts & Dependency Inversion (if needed)
4. V4-3: Package Normalization (remaining naming)
5. V4-4: Config & Data Isolation
6. V4-5: Identity & UX Separation
7. V4-6: Documentation & Credits
8. V4-7: CI/CD Hardening

---

## Exit Criteria Tracking

### A) Runtime & Code
- [x] CLI principal is `aria`
- [x] No OpenCode references in executable code/runtime paths/log user-facing
- [x] No runtime dependency on `.opencode.json` or `.opencode` path

### B) Architecture & Dependencies
- [x] ARIA core layer conforms to boundary policy
- [x] Interactions with concrete services via contracts/adapters
- [x] No prohibited imports in denylist

### C) Config & Data
- [x] `ARIA_*` supported and documented
- [x] `aria.json` optional supported with correct precedence
- [x] ARIA unique and stable data path

### D) UX/Brand
- [x] ARIA splash active
- [x] Theme/icons/texts ARIA-only
- [x] Total absence of OpenCode brand in ARIA screens

### E) Docs & Credits
- [x] Official credits present ("Based on OpenCode")
- [ ] No operational reference to OpenCode in ARIA user guides

### F) Quality & Delivery
- [x] `go build` and `go test ./...` green
- [x] CI guardrails (string/import checks) green (manual check)
- [ ] ARIA-only release artifacts completed