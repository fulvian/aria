---
adr: ADR-0009
title: Kilo agent frontmatter schema + MCP npx bin resolution
status: accepted
date_created: 2026-04-21
date_accepted: 2026-04-21
author: ARIA Chief Architect
project: ARIA - Autonomous Reasoning & Intelligent Assistant
context: Phase 1 MVP — REPL delegation bug; conductor invoked built-in websearch instead of search-agent
---

# ADR-0009: Kilo Agent Frontmatter + MCP npx Bin Resolution

## Status

**Accepted** — 2026-04-21

## Context

During Phase 1 REPL verification, user query "quali sono le migliori serie tv crime uscite nel 2026?" triggered direct invocation of Kilo's built-in `websearch` tool (Exa provider) by the ARIA-Conductor agent, instead of delegation to `search-agent` via the `task` tool. This violated:

- **P8 — Tool Priority Ladder** (MCP > Skill > Python): built-in `websearch` bypassed ARIA's provider MCP servers (Tavily, Exa, Firecrawl, SearXNG, Brave).
- **P9 — Scoped Toolsets**: conductor must not perform operational work directly.

Root-cause investigation (systematic-debugging, 4 phases) revealed **two independent bugs** in the Kilo integration:

### Bug 1 — Invalid Kilo config fields silently ignored

Committed `.aria/kilocode/kilo.json` used fields from an earlier custom schema (`mcp_config`, `agents_dir`, `skills_dir`, `modes_dir`, `sessions_dir`, `model.provider`, `model.id`, `hooks.{Pre,Post}ToolUse`, `hooks.UserPromptSubmit`, `hooks.Stop`). None are valid Kilo CLI v7 config keys. Kilo silently discarded them. Result: **zero MCP servers started** at REPL launch. Conductor inherited only built-in tools, so LLM's next-best tool for a web-search intent was `websearch`.

Separate file `.aria/kilocode/mcp.json` used Claude-Desktop schema (`mcpServers.<name>.{command, args, env}`). Kilo reads MCP config from the inline `mcp:` block in `kilo.json`; the standalone file was never consulted.

### Bug 2 — Agent markdown frontmatter used non-Kilo keys

All three agent files (`aria-conductor.md`, `search-agent.md`, `workspace-agent.md`) declared:

```yaml
allowed-tools: [tavily-mcp/search, aria-memory/remember, ...]
required-skills: [deep-research]
mcp-dependencies: [tavily-mcp, ...]
category: research
type: subagent
```

Kilo's `AgentConfig` (SDK `types.gen.d.ts`) accepts only:

```ts
{
  mode: "primary" | "subagent" | "all",
  tools?: { [key: string]: boolean },   // true=allow, false=deny
  permission?: {
    edit?: "ask"|"allow"|"deny",
    bash?: "ask"|"allow"|"deny"|{[pattern]: action},
    webfetch?: "ask"|"allow"|"deny",
    doom_loop?: "ask"|"allow"|"deny",
    external_directory?: "ask"|"allow"|"deny"
  },
  description?, color?, temperature?, prompt?, model?, maxSteps?, disable?
}
```

Unknown keys were discarded. Conductor therefore had **unrestricted access to all built-in tools** including `websearch`, `webfetch`, `codesearch`. The LLM's tool-selection heuristic picked `websearch` for the user query.

### Bug 3 — npx bin resolution for scoped packages with non-matching bin names

Four MCP servers mandated by blueprint §10.3 failed to start with `sh: 1: @<scope>/<name>: not found`:

- `@modelcontextprotocol/server-filesystem` — bin `mcp-server-filesystem`
- `@modelcontextprotocol/server-github` — bin `mcp-server-github`
- `@modelcontextprotocol/server-sequential-thinking` — bin `mcp-server-sequential-thinking`
- `@brave/brave-search-mcp-server` — bin `brave-search-mcp-server`

`npx -y <scoped-pkg>` resolves the executable by stripping the scope and looking up that name in the package's `bin` map. When pkg name (minus scope) does not match any bin entry, recent `npx` versions fall back to executing the package specifier literally, producing the `sh: 1:` error. This affects every MCP server whose bin name differs from the unscoped package name.

## Decision

### 1. Agent frontmatter — only Kilo-valid keys

Rewrite all three agent markdown files using the `AgentConfig` schema:

- `mode: primary` (aria-conductor) or `mode: subagent` (search-agent, workspace-agent)
- `tools: { <tool>: false }` to deny a specific tool (translates to `permission.<tool> = "deny"` at load time)
- `permission: { edit: deny, bash: deny, webfetch: deny }` for category-level denials
- Agent system prompt lives in the markdown body

**Delegation enforcement** — on the primary `aria-conductor`:

```yaml
tools:
  websearch: false
  codesearch: false
  webfetch: false
```

With built-in web-tools removed, the LLM must use `task` to delegate, satisfying P8/P9.

**Sub-agent isolation** — on subagents:

```yaml
tools:
  task: false       # no recursive delegation
  websearch: false
  webfetch: false
  write: false
  edit: false
  patch: false
  multiedit: false
  bash: false
  codesearch: false
permission:
  edit: deny
  bash: deny
  webfetch: deny
```

MCP tools remain accessible (not in the deny list).

### 2. Single MCP registry

- Inline all MCP servers in `.aria/kilocode/kilo.json` under the `mcp:` block using `{ type: "local", command: [...], environment?: {...}, enabled?: bool }`.
- Delete `.aria/kilocode/mcp.json` (Claude-Desktop format, unused by Kilo).
- Env substitution syntax is `{env:VAR_NAME}`, not `${VAR}`.

### 3. npx bin resolution for MCP servers

For any MCP server installed as a scoped npm package whose bin name differs from the unscoped package basename, use the explicit form:

```json
["npx", "-y", "--package=<@scope/pkg>", "<bin-name>", "<args...>"]
```

This bypasses npx's heuristic resolution and invokes the named bin directly.

### 4. Wrapper scripts for secret-requiring servers

MCP servers that require API tokens (`brave-mcp`, `github`) launch via wrapper scripts in `scripts/wrappers/`:

- `brave-wrapper.sh` — decrypts `api-keys.enc.yaml` via SOPS, extracts `providers.brave[0].key`, exports `BRAVE_API_KEY`, execs npx with `--package=@brave/brave-search-mcp-server brave-search-mcp-server`.
- `github-wrapper.sh` — decrypts SOPS, extracts `github.token`, exports `GITHUB_PERSONAL_ACCESS_TOKEN`, execs npx with `--package=@modelcontextprotocol/server-github mcp-server-github`.

Pattern mirrors existing `tavily-wrapper.sh` / `firecrawl-wrapper.sh` / `exa-wrapper.sh` / `searxng-wrapper.sh` (P4 — Local-First, Privacy-First: secrets never enter plain env files).

### 5. MCP tool ID namespacing (reference)

Kilo exposes MCP tools to the LLM as `<sanitize(serverKey)>_<sanitize(toolName)>` where `sanitize = s => s.replace(/[^a-zA-Z0-9_-]/g, "_")` (hyphens preserved). Examples: `tavily-mcp_search`, `aria-memory_remember`, `google_workspace_send_gmail_message`. Agent prompts reference tools using this exact form.

## Consequences

### Positive

- Conductor physically cannot invoke built-in web tools → delegation to sub-agents is the only path → P8/P9 restored.
- All 12 blueprint-mandated MCP servers connect successfully on REPL start (total tool surface: 197 tools across 12 servers; previously 0).
- Agent configuration is now schema-validated by Kilo (typo keys are now detectable in principle, though Kilo still does not warn about them — see Follow-up).
- Secret handling for brave/github aligns with existing provider wrappers; no plaintext secrets in `.env` or config files.

### Negative

- Agent frontmatter ties ARIA to Kilo's specific `AgentConfig` schema. If Kilo evolves the schema (e.g. renames `tools` to `permissions_map`), all three files must be migrated. Mitigated by `scripts/validate_agents.py` (future) and by the upstream-invariance principle (P2) — upgrades are deliberate, not automatic.
- The explicit `--package=<pkg> <bin>` form is more verbose than the shorthand and must be maintained as blueprint §10.3 evolves.

### Follow-up

1. Write `scripts/validate_agents.py` that parses each agent `.md` frontmatter and asserts only Kilo-accepted keys are present; run as part of `make quality`.
2. Add systemd override or pre-start check ensuring SOPS age key is readable by wrapper scripts (current wrappers error with clear message if missing, but should surface earlier).
3. Document the MCP tool ID namespacing rule (`<server>_<tool>`) in `docs/foundation/aria_foundation_blueprint.md` §10, so that agent prompts reference the correct IDs without re-deriving from Kilo source.

## References

- Blueprint: `docs/foundation/aria_foundation_blueprint.md` §10.3 (MCP servers MVP), §11 (search-agent), §12 (workspace-agent), §16 (Ten Commandments).
- Kilo SDK: `.aria/kilocode/node_modules/@kilocode/sdk/dist/gen/types.gen.d.ts` lines 835–877 (`AgentConfig`).
- Kilo MCP tool naming: binary `@kilocode/cli-linux-x64/bin/kilo`, symbol `convertMcpTool` + local `sanitize`.
- Session log: `.aria/kilo-home/.local/share/kilo/log/2026-04-21T190104.log` (12 MCP servers connected, 0 failures).
