========================================================================
  ARIA Drift Audit Report  |  Mode: baseline
  ARIA_HOME: /home/fulvio/coding/aria
========================================================================

  [P1] WARNING — 21 issue(s)
  --------------------------------------------------------------------
    • [dep_tool_mismatch] Agent 'aria-conductor' uses MCP server 'sequential-thinking' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_aria-conductor.template.md
    • [dep_tool_mismatch] Agent 'blueprint-keeper' uses MCP server 'aria-memory' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_system/blueprint-keeper.md
    • [dep_tool_mismatch] Agent 'blueprint-keeper' uses MCP server 'filesystem' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_system/blueprint-keeper.md
    • [dep_tool_mismatch] Agent 'blueprint-keeper' uses MCP server 'git' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_system/blueprint-keeper.md
    • [dep_tool_mismatch] Agent 'blueprint-keeper' uses MCP server 'github' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_system/blueprint-keeper.md
    • [dep_tool_mismatch] Agent 'compaction-agent' uses MCP server 'aria-memory' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_system/compaction-agent.md
    • [dep_tool_mismatch] Agent 'memory-curator' uses MCP server 'aria-memory' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_system/memory-curator.md
    • [dep_tool_mismatch] Agent 'security-auditor' uses MCP server 'aria-memory' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_system/security-auditor.md
    • [dep_tool_mismatch] Agent 'security-auditor' uses MCP server 'filesystem' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_system/security-auditor.md
    • [dep_tool_mismatch] Agent 'security-auditor' uses MCP server 'git' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_system/security-auditor.md
    • [dep_tool_mismatch] Agent 'security-auditor' uses MCP server 'github' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_system/security-auditor.md
    • [dep_tool_mismatch] Agent 'summary-agent' uses MCP server 'aria-memory' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/_system/summary-agent.md
    • [dep_tool_mismatch] Agent 'aria-conductor' uses MCP server 'sequential-thinking' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/aria-conductor.md
    • [dep_tool_mismatch] Agent 'productivity-agent' uses MCP server 'fetch' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/productivity-agent.md
    • [dep_tool_mismatch] Agent 'productivity-agent' uses MCP server 'sequential-thinking' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/productivity-agent.md
    • [dep_tool_mismatch] Agent 'search-agent' uses MCP server 'aria-memory' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/search-agent.md
    • [dep_tool_mismatch] Agent 'search-agent' uses MCP server 'fetch' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/search-agent.md
    • [dep_tool_mismatch] Agent 'workspace-agent' uses MCP server 'aria-memory' in tools but lacks it in mcp-dependencies
      Source: .aria/kilocode/agents/workspace-agent.md
    • [wiki_index_fs_mismatch] Wiki file 'aria-kilo-freeze-rca.md' exists but is not listed in wiki index
      Source: docs/llm_wiki/wiki/index.md
    • [wiki_index_fs_mismatch] Wiki file 'productivity-agent.md' exists but is not listed in wiki index
      Source: docs/llm_wiki/wiki/index.md
    • [router_code_mismatch] Router defines provider 'webfetch' but search-agent has no tool/dependency
      Source: src/aria/agents/search/router.py

  [P2] INFO — 2 issue(s)
  --------------------------------------------------------------------
    • [removed_tool_reference] 'mcp.json' contains reference to removed tool 'pubmed' (removed 2026-04-30: covered by scientific-papers-mcp source='europepmc')
      Source: .aria/kilocode/mcp.json
    • [removed_tool_reference] 'wiki index' contains reference to removed tool 'pubmed' (removed 2026-04-30: covered by scientific-papers-mcp source='europepmc')
      Source: docs/llm_wiki/wiki/index.md

  ====================================================================
  Summary: 23 issue(s) — P0: 0  P1: 21  P2: 2
  ====================================================================
