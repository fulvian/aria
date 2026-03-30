# ARIA Boundary Policy

**Date:** 2026-03-30  
**Status:** APPROVED  
**Enforcement:** CI guardrails + manual review

---

## 1. Purpose

This policy defines the architectural boundaries for ARIA, ensuring complete separation from OpenCode at runtime. The policy is **binding** for all code merged into the repository.

---

## 2. Single Product Policy

**Rule:** The repository produces exactly ONE product: **ARIA**.

- Single binary: `aria`
- Single config namespace: `ARIA_*` environment variables
- Single config file: `aria.json` (optional)
- Single data directory: `.aria` (or `~/.local/share/aria`)
- Single theme: `aria` (default)

---

## 3. String Denylist (Runtime Code)

The following strings are **PROHIBITED** in runtime code (CLI, TUI, config, logs, user-facing paths):

| Denied String | Reason | Examples |
|---------------|--------|----------|
| `opencode` | Product name | CLI commands, paths |
| `OpenCode` | Product branding | UI labels, prompts |
| `.opencode` | Config/data paths | Directory names |
| `opencode.json` | Config file | File references |
| `opencode.md` | Context file | Auto-added context |
| `OpenCode.md` | Context file | Auto-added context |
| `OPENCODE.md` | Context file | Auto-added context |

**Allowed Locations:**
- `docs/credits/` - Attribution documents
- `ACKNOWLEDGEMENTS` - Acknowledgment files
- License files - Legal attribution
- `README.md` - Only in credits section

---

## 4. Import Denylist (Package Boundaries)

**Rule:** ARIA core packages (`internal/aria/*`) MUST NOT import:

| Prohibited Import | Rationale |
|-------------------|-----------|
| `internal/config` (OpenCode config) | Legacy, uses `appName="opencode"` |
| `internal/tui/theme/opencode.go` | Legacy theme |
| Any package with `opencode` in path | Naming contamination |

**Allowed Dependencies:**
- `internal/aria/*` (internal contracts)
- `internal/platform/*` (shared infrastructure)
- `internal/pubsub/*` (event broker)
- `internal/db/*` (persistence)
- `stdlib` and `third-party` packages

---

## 5. User-Agent Policy

**Rule:** All outbound HTTP requests MUST identify as ARIA:

| Allowed | Forbidden |
|---------|-----------|
| `User-Agent: aria/1.0` | `User-Agent: opencode/1.0` |
| `aria.ai` referrer | `opencode.ai` referrer |
| `X-Title: ARIA` | `X-Title: OpenCode` |

---

## 6. Co-Author Policy

**Rule:** Git commit co-authorship MUST identify as ARIA:

| Allowed | Forbidden |
|---------|-----------|
| `Co-Authored-By: ARIA <noreply@aria.ai>` | `Co-Authored-By: opencode <noreply@opencode.ai>` |

---

## 7. Temp File Naming

**Rule:** Temporary files MUST use `aria-*` prefix:

| Allowed | Forbidden |
|---------|-----------|
| `aria-stdout-{pid}` | `opencode-stdout-{pid}` |
| `aria-stderr-{pid}` | `opencode-stderr-{pid}` |
| `aria-status-{pid}` | `opencode-status-{pid}` |

---

## 8. Panic Log Naming

**Rule:** Panic logs MUST use `aria-panic-*` pattern:

| Allowed | Forbidden |
|---------|-----------|
| `aria-panic-{name}-{timestamp}.log` | `opencode-panic-{name}-{timestamp}.log` |

---

## 9. Context File Guidance

**Legacy context files (REMOVE from auto-add):**
- `opencode.md`
- `opencode.local.md`
- `OpenCode.md`
- `OpenCode.local.md`
- `OPENCODE.md`
- `OPENCODE.local.md`

**ARIA context files (ADD to auto-add):**
- `ARIA.md`
- `ARIA.local.md`

---

## 10. CI Enforcement

### Required Checks

1. **String Check (pre-commit/CI)**
   ```bash
   # Must return empty for runtime code
   grep -r "opencode\|OpenCode\|.opencode" \
     --include="*.go" \
     --exclude-dir=".git" \
     internal/ cmd/ main.go
   ```

2. **Import Check (CI)**
   ```bash
   # ARIA packages must not import legacy
   go list -f '{{.ImportPath}} -> {{.Imports}}' ./internal/aria/... \
     | grep -E "(config|tui/theme/opencode)"
   ```

3. **Config File Check (CI)**
   ```bash
   # No .opencode.json references in runtime
   grep -r "\.opencode\.json\|appName.*opencode" \
     --include="*.go" \
     internal/
   ```

---

## 11. Exceptions

**NONE** for runtime code. All exceptions require:
1. Documented justification
2. Security/compliance review
3. Explicit approval in PR

---

## 12. Violations

| Severity | Action |
|----------|--------|
| Critical (runtime string) | PR blocked, must fix |
| High (import violation) | PR blocked, must refactor |
| Medium (UI label) | Fix in next sprint |
| Low (comment) | Fix when touching file |

---

## 13. Graceful Migration

For existing user data:

- **Migration path:** `.opencode` → `.aria` (one-time migrator)
- **Config:** `.opencode.json` → `aria.json` (automatic on first run if exists)
- **No backward compatibility** maintained after migration period

---

## 14. Verification

Before closing any PR, verify:
- [ ] `grep -r "opencode" internal/ cmd/ main.go` returns empty
- [ ] `grep -r "OpenCode" internal/ cmd/ main.go` returns empty (except comments about origin)
- [ ] No import violations
- [ ] Tests pass with new naming

---

**Policy History:**
- 2026-03-30: Initial version (derived from plan v4)