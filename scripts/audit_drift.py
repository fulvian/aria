#!/usr/bin/env python3
"""Audit drift between MCP config, agent prompts, wiki index, and router code.

Detects inconsistencies across the ARIA system per stabilization plan F1:
  - Allowed tools in agent prompts vs MCP server definitions
  - Wiki index entries vs actual wiki files on disk
  - References to removed tools (pubmed, firecrawl)
  - Router code vs search-agent allowed-tools
  - Agent mcp-dependencies vs allowed-tools coverage

Modes:
  --shadow:         Warning only, exit 0 regardless of findings
  --enforce:        Exit 1 on ANY drift (P0/P1/P2)
  --baseline-mode:  Exit 0 if P0 count < 5 (baseline tolerance)

Usage:
    python scripts/audit_drift.py
    python scripts/audit_drift.py --shadow
    python scripts/audit_drift.py --enforce
    python scripts/audit_drift.py --baseline-mode
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ARIA_HOME = Path(__file__).resolve().parent.parent

MCP_CONFIG_PATH = ARIA_HOME / ".aria" / "kilocode" / "mcp.json"
AGENTS_DIR_PATH = ARIA_HOME / ".aria" / "kilocode" / "agents"
WIKI_DIR_PATH = ARIA_HOME / "docs" / "llm_wiki" / "wiki"
WIKI_INDEX_PATH = WIKI_DIR_PATH / "index.md"
ROUTER_PATH = ARIA_HOME / "src" / "aria" / "agents" / "search" / "router.py"

REMOVED_TOOLS: dict[str, str] = {
    "pubmed": "removed 2026-04-30: covered by scientific-papers-mcp source='europepmc'",
    "firecrawl": "removed 2026-04-27: all 6 accounts exhausted lifetime credits",
}

BUILTIN_TOOLS: frozenset[str] = frozenset(
    {
        "spawn-subagent",
        "hitl-queue",
    }
)

P0 = "P0"
P1 = "P1"
P2 = "P2"


@dataclass
class DriftIssue:
    severity: str
    category: str
    message: str
    source: str
    details: str = ""


@dataclass
class AgentConfig:
    name: str
    file_path: Path
    allowed_tools: list[str] = field(default_factory=list)
    mcp_dependencies: list[str] = field(default_factory=list)


@dataclass
class McpServer:
    name: str
    enabled: bool


@dataclass
class DriftReport:
    issues: list[DriftIssue] = field(default_factory=list)

    def add(
        self,
        severity: str,
        category: str,
        message: str,
        source: str,
        details: str = "",
    ) -> None:
        self.issues.append(DriftIssue(severity, category, message, source, details))

    @property
    def by_severity(self) -> dict[str, list[DriftIssue]]:
        result: dict[str, list[DriftIssue]] = {P0: [], P1: [], P2: []}
        for issue in self.issues:
            result.setdefault(issue.severity, []).append(issue)
        return result

    @property
    def total(self) -> int:
        return len(self.issues)

    @property
    def p0_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == P0)


def _parse_yaml_frontmatter(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return result
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return result
    front = lines[1:end_idx]
    current_key: str | None = None
    list_buffer: list[str] = []
    for line in front:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            list_buffer.append(stripped[2:].strip())
            continue
        if list_buffer and current_key is not None:
            result[current_key] = list(list_buffer)
            list_buffer = []
            current_key = None
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            current_key = key.strip()
            value = value.strip()
            if value:
                result[current_key] = value
            else:
                result[current_key] = []
                list_buffer = []
    if list_buffer and current_key is not None:
        result[current_key] = list(list_buffer)
    for key, value in list(result.items()):
        if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                items = [item.strip().strip("'\"") for item in inner.split(",")]
                result[key] = items
    return result


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str):
        return [value] if value else []
    return []


def load_mcp_servers(path: Path) -> dict[str, McpServer]:
    servers: dict[str, McpServer] = {}
    if not path.exists():
        return servers
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return servers
    for name, config in data.get("mcpServers", {}).items():
        enabled = config.get("disabled", False) is False
        servers[name] = McpServer(name=name, enabled=enabled)
    return servers


def load_agents(dir_path: Path) -> list[AgentConfig]:
    agents: list[AgentConfig] = []
    if not dir_path.exists():
        return agents
    for fpath in sorted(dir_path.rglob("*.md")):
        try:
            text = fpath.read_text(encoding="utf-8")
        except OSError:
            continue
        front = _parse_yaml_frontmatter(text)
        if "name" not in front:
            continue
        agent = AgentConfig(
            name=str(front["name"]),
            file_path=fpath,
            allowed_tools=_normalize_list(front.get("allowed-tools", [])),
            mcp_dependencies=_normalize_list(front.get("mcp-dependencies", [])),
        )
        agents.append(agent)
    return agents


def extract_tool_server(tool: str) -> str | None:
    parts = tool.split("/", 1)
    server = parts[0]
    if server in BUILTIN_TOOLS:
        return None
    return server


def load_wiki_index_pages(path: Path) -> set[str]:
    pages: set[str] = set()
    if not path.exists():
        return pages
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return pages
    for m in re.finditer(r"\[\[([^\]]+)\]\]", text):
        pages.add(m.group(1))
    return pages


def get_actual_wiki_pages(dir_path: Path) -> set[str]:
    pages: set[str] = set()
    if not dir_path.exists():
        return pages
    for fpath in dir_path.glob("*.md"):
        if fpath.name == "index.md":
            continue
        if ".obsidian" in str(fpath):
            continue
        pages.add(fpath.stem)
    return pages


def load_router_providers(path: Path) -> list[str]:
    providers: list[str] = []
    if not path.exists():
        return providers
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return providers
    in_enum = False
    in_multiline = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("class Provider(StrEnum):"):
            in_enum = True
            continue
        if in_enum:
            if stripped.startswith("class "):
                break
            if not stripped or stripped.startswith("#") or stripped.startswith('"""'):
                continue
            if in_multiline:
                m = re.search(r'"([^"]+)"', stripped)
                if m:
                    providers.append(m.group(1).lower())
                    in_multiline = False
                continue
            m = re.match(r'^\s*(\w+)\s*=\s*"([^"]+)"', stripped)
            if m:
                providers.append(m.group(2).lower())
                continue
            if re.match(r"^\s*\w+\s*=\s*\(", stripped):
                in_multiline = True
            if stripped.startswith("class FailureReason"):
                break
    return providers


def _check_agent_tool_mcp_mismatch(
    report: DriftReport,
    agents: list[AgentConfig],
    mcp_servers: dict[str, McpServer],
) -> None:
    enabled_servers = {n for n, s in mcp_servers.items() if s.enabled}
    all_servers = set(mcp_servers.keys())

    for agent in agents:
        for tool in agent.allowed_tools:
            server = extract_tool_server(tool)
            if server is None:
                continue
            if server not in all_servers:
                report.add(
                    P0,
                    "tool_mcp_mismatch",
                    f"Agent '{agent.name}' tool '{tool}' references unknown MCP server '{server}'",
                    str(agent.file_path.relative_to(ARIA_HOME)),
                )
            elif server not in enabled_servers:
                report.add(
                    P1,
                    "tool_mcp_mismatch",
                    f"Agent '{agent.name}' tool '{tool}' references disabled MCP server '{server}'",
                    str(agent.file_path.relative_to(ARIA_HOME)),
                )


def _check_agent_dep_vs_tools(
    report: DriftReport,
    agents: list[AgentConfig],
) -> None:
    for agent in agents:
        tool_servers: set[str] = set()
        for tool in agent.allowed_tools:
            server = extract_tool_server(tool)
            if server is not None:
                tool_servers.add(server)
        for dep in agent.mcp_dependencies:
            if dep not in tool_servers:
                report.add(
                    P1,
                    "dep_tool_mismatch",
                    f"Agent '{agent.name}' declares mcp-dependency '{dep}' but no allowed-tool references it",
                    str(agent.file_path.relative_to(ARIA_HOME)),
                )
        for server in sorted(tool_servers):
            if server not in agent.mcp_dependencies:
                report.add(
                    P1,
                    "dep_tool_mismatch",
                    f"Agent '{agent.name}' uses MCP server '{server}' in tools but lacks it in mcp-dependencies",
                    str(agent.file_path.relative_to(ARIA_HOME)),
                )


def _check_wiki_index_vs_files(report: DriftReport) -> None:
    indexed = load_wiki_index_pages(WIKI_INDEX_PATH)
    actual = get_actual_wiki_pages(WIKI_DIR_PATH)

    missing = indexed - actual
    for page in sorted(missing):
        msg = f"Wiki index references page '{page}' but no matching file exists in wiki/"
        report.add(P0, "wiki_index_fs_mismatch", msg, str(WIKI_INDEX_PATH.relative_to(ARIA_HOME)))

    extra = actual - indexed
    for page in sorted(extra):
        msg = f"Wiki file '{page}.md' exists but is not listed in wiki index"
        report.add(P1, "wiki_index_fs_mismatch", msg, str(WIKI_INDEX_PATH.relative_to(ARIA_HOME)))


def _check_removed_tools(report: DriftReport) -> None:
    search_targets: list[tuple[str, Path]] = [
        ("mcp.json", MCP_CONFIG_PATH),
        ("wiki index", WIKI_INDEX_PATH),
    ]

    # Agent YAML frontmatter: scan allowed-tools and mcp-dependencies for removed refs
    agents = load_agents(AGENTS_DIR_PATH)
    for agent in agents:
        all_refs = agent.allowed_tools + agent.mcp_dependencies
        for ref in all_refs:
            for tool, reason in REMOVED_TOOLS.items():
                if tool in ref.lower():
                    report.add(
                        P0,
                        "removed_tool_reference",
                        f"Agent '{agent.name}' references removed tool '{tool}' in YAML frontmatter",
                        str(agent.file_path.relative_to(ARIA_HOME)),
                    )

    # MCP config: check for removed server entries still present
    for source_name, path in search_targets:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for tool, reason in REMOVED_TOOLS.items():
            if re.search(rf"\b{re.escape(tool)}\b", text, re.IGNORECASE):
                report.add(
                    P2,
                    "removed_tool_reference",
                    f"'{source_name}' contains reference to removed tool '{tool}' ({reason})",
                    str(path.relative_to(ARIA_HOME)),
                )


def _check_router_code_consistency(
    report: DriftReport,
    agents: list[AgentConfig],
) -> None:
    search_agent = next((a for a in agents if a.name == "search-agent"), None)
    if search_agent is None:
        report.add(
            P0, "router_code_mismatch", "search-agent definition not found", str(AGENTS_DIR_PATH)
        )
        return

    router_providers_raw = load_router_providers(ROUTER_PATH)
    router_providers = set(router_providers_raw)

    agent_tool_servers: set[str] = set()
    for tool in search_agent.allowed_tools:
        server = extract_tool_server(tool)
        if server is not None:
            agent_tool_servers.add(server)

    mcp_to_provider: dict[str, str] = {
        "searxng-script": "searxng",
        "tavily-mcp": "tavily",
        "exa-script": "exa",
        "brave-mcp": "brave",
        "scientific-papers-mcp": "scientific_papers",
        "reddit-search": "reddit",
        "fetch": "fetch",
    }

    agent_providers = {mcp_to_provider.get(s, s) for s in agent_tool_servers}
    skip_router_providers = {"arxiv"}

    missing_in_router = (
        agent_providers - router_providers - {"filesystem", "aria-memory", "markitdown-mcp"}
    )
    for prov in sorted(missing_in_router):
        report.add(
            P1,
            "router_code_mismatch",
            f"Search-agent references '{prov}' but router Provider enum lacks it",
            str(ROUTER_PATH.relative_to(ARIA_HOME)),
        )

    extra_in_router = router_providers - agent_providers - skip_router_providers
    for prov in sorted(extra_in_router):
        report.add(
            P1,
            "router_code_mismatch",
            f"Router defines provider '{prov}' but search-agent has no tool/dependency",
            str(ROUTER_PATH.relative_to(ARIA_HOME)),
        )


def _print_report(report: DriftReport, mode: str) -> None:
    print("=" * 72)
    print(f"  ARIA Drift Audit Report  |  Mode: {mode}")
    print(f"  ARIA_HOME: {ARIA_HOME}")
    print("=" * 72)

    by_sev = report.by_severity
    labels = {P0: "CRITICAL", P1: "WARNING", P2: "INFO"}

    found_any = False
    for severity in (P0, P1, P2):
        issues = by_sev.get(severity, [])
        if not issues:
            continue
        found_any = True
        label = labels.get(severity, severity)
        print(f"\n  [{severity}] {label} — {len(issues)} issue(s)")
        print(f"  {'-' * 68}")
        for issue in issues:
            print(f"    • [{issue.category}] {issue.message}")
            print(f"      Source: {issue.source}")

    if not found_any:
        print("\n  ✅ No drift detected.")
        print()

    print(f"\n  {'=' * 68}")
    p1_count = len(by_sev.get(P1, []))
    p2_count = len(by_sev.get(P2, []))
    print(
        f"  Summary: {report.total} issue(s) — P0: {report.p0_count}  P1: {p1_count}  P2: {p2_count}"
    )
    print(f"  {'=' * 68}")


def main() -> int:
    args = set(sys.argv[1:])
    if "--shadow" in args:
        mode = "shadow"
    elif "--enforce" in args:
        mode = "enforce"
    elif "--baseline-mode" in args:
        mode = "baseline"
    else:
        mode = "standard"

    report = DriftReport()

    mcp_servers = load_mcp_servers(MCP_CONFIG_PATH)
    agents = load_agents(AGENTS_DIR_PATH)

    if not mcp_servers:
        report.add(P0, "load_error", "MCP config not found or empty", str(MCP_CONFIG_PATH))

    if not agents:
        report.add(P0, "load_error", "No agent prompts found", str(AGENTS_DIR_PATH))

    _check_agent_tool_mcp_mismatch(report, agents, mcp_servers)
    _check_agent_dep_vs_tools(report, agents)
    _check_wiki_index_vs_files(report)
    _check_removed_tools(report)
    _check_router_code_consistency(report, agents)

    _print_report(report, mode)

    if mode == "shadow":
        return 0

    if mode == "enforce":
        return 1 if report.total > 0 else 0

    if mode == "baseline":
        return 0 if report.p0_count < 5 else 1

    return 1 if report.p0_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
