# ARIA Launcher CLI Compatibility

**Last Updated**: 2026-04-25
**Status**: FIXED (v4)
**Scope**: `bin/aria` launcher compatibility + hard isolation + MCP restoration

## Problem

`bin/aria repl` failed with:

```
Error: Failed to change directory to /home/fulvio/coding/aria/chat
```

## Root Cause (Deep)

Two independent regressions were active:

1. Legacy invocation mismatch:
   - launcher invoked `npx --yes kilocode chat`
   - current CLI parses positional argument as project path (`kilo [project]`)
   - result: `chat` interpreted as directory, causing `.../aria/chat` chdir failure

2. Isolation variable mismatch:
   - launcher exported legacy vars (`KILOCODE_CONFIG_DIR`, `KILOCODE_STATE_DIR`)
   - current CLI resolved config/data from XDG/HOME (`~/.config/kilo`, `~/.local/share/kilo`)
   - result: ARIA session used global Kilo environment instead of ARIA-isolated runtime

3. MCP schema drift after isolation move:
   - ARIA MCP inventory lived in legacy `.aria/kilocode/mcp.json` (`mcpServers` format)
   - current Kilo runtime reads MCP from modern config key `mcp` in `kilo.jsonc`
   - result: after isolation fix, MCP list became empty (`No MCP servers configured`)

## Evidence

- Reproduction A: `bin/aria repl` returned `Failed to change directory to /home/fulvio/coding/aria/chat`.
- Reproduction B: `bin/aria repl --print-logs` showed global paths:
  - `/home/fulvio/.config/kilo/...`
  - `/home/fulvio/.local/share/kilo/kilo.db`
- Local CLI help output shows:
  - `kilo [project]` (default TUI command)
  - `kilo run [message..]`
  - no `chat` subcommand.
- Context7 docs for `/kilo-org/kilocode` confirm modern syntax (`kilo`, `kilo run ...`).
- `kilo debug paths` confirms isolation is controlled by HOME/XDG in current CLI.
- `kilo mcp list` initially reported: `No MCP servers configured`.

## Fix Implemented

`bin/aria` now enforces ARIA-only runtime and modern/legacy compatibility:

1. Hard isolation (no global Kilo contamination):
   - `HOME="$ARIA_HOME/.aria/kilo-home"`
   - exports `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`, `XDG_CACHE_HOME`
   - keeps `KILOCODE_CONFIG_DIR` as ARIA source-of-truth
   - sets `KILO_DISABLE_EXTERNAL_SKILLS=true`

2. Modern runtime path sync:
   - copies ARIA agents/skills from `.aria/kilocode/` to isolated `$HOME/.kilo/{agents,skills}`

3. Resolves executable:
   - prefer `kilo` if installed
   - fallback to `npx --yes kilocode`

4. Detects CLI flavor via `--help`:
   - `modern` if `kilo [project]` or `run [message..]` is present
   - `legacy` if `chat` subcommand is present

5. Routes subcommands by detected flavor:
    - `repl`:
      - modern: `<kilo_cmd> "$ARIA_HOME" --agent aria-conductor` (default)
      - legacy: `<kilo_cmd> chat`
    - `run`:
      - modern: `<kilo_cmd> run --agent aria-conductor --auto`
      - legacy: `<kilo_cmd> chat --auto`
    - `mode`:
      - modern: `<kilo_cmd> "$ARIA_HOME" --agent`
      - legacy: `<kilo_cmd> chat --mode`

6. MCP migration bridge added in launcher bootstrap:
   - on each `bin/aria` invocation, convert `.aria/kilocode/mcp.json` -> isolated `kilo.jsonc` `mcp` schema
   - preserve enable/disable state, command vector, and environment mapping
   - preserve `${ENV_VAR}` placeholders to avoid writing secrets in local config files

## Why This Is Robust

- Prevents any read/write to global `~/.config/kilo` and `~/.local/share/kilo`.
- Preserves ARIA-specific agents/skills (`aria-conductor`, `workspace-agent`, `search-agent`).
- Backward-compatible with both old and new CLI command surfaces.
- Fails fast with explicit errors if CLI/runtime prerequisites are missing.

## Validation

- `bash -n bin/aria` -> pass.
- `bin/aria repl --print-logs` now loads only isolated paths under `.aria/kilo-home`.
- TUI starts with `Aria-Conductor` selected by default.
- `bin/aria run ... --print-logs` shows `> aria-conductor · ...` and isolated DB path.
- `kilo mcp list` now shows 12 active ARIA-managed servers after cleanup of deprecated disabled profiles:
  - connected: `filesystem`, `git`, `github`, `sequential-thinking`, `fetch`, `aria-memory`, `google_workspace`, `tavily-mcp`, `firecrawl-mcp`, `brave-mcp`, `exa-script`, `searxng-script`
- removed (deprecated): `google_workspace_readonly`, `playwright`
- `firecrawl-mcp` startup regression resolved by pinning wrapper package version in `scripts/wrappers/firecrawl-wrapper.sh` to `firecrawl-mcp@3.10.3` (avoids broken transient npx artifact observed under isolated HOME cache).

## Provenance

- Source: `bin/aria` (updated: 2026-04-25)
- Source: local command output `npx --yes kilocode --help` (queried: 2026-04-25)
- Source: local command output `npx --yes kilocode debug paths` (queried: 2026-04-25)
- Source: local command output `bin/aria repl` (queried: 2026-04-25)
- Source: local command output `bin/aria repl --print-logs` (queried: 2026-04-25)
- Source: local command output `npx --yes kilocode mcp list` (queried: 2026-04-25)
- Source: local command output `HOME=... XDG_*=... kilo mcp list` (queried: 2026-04-25)
- Source: local runtime log `.aria/kilo-home/.local/share/kilo/log/2026-04-25T203602.log` (queried: 2026-04-25)
- Source: `scripts/wrappers/firecrawl-wrapper.sh` (updated: 2026-04-25)
- Source: Context7 `/kilo-org/kilocode` (queried: 2026-04-25)
