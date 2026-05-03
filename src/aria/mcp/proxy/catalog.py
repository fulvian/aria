"""Load .aria/config/mcp_catalog.yaml and build the FastMCP backends config.

Schema reference: docs/llm_wiki/wiki/mcp-refoundation.md.

This module deliberately knows nothing about credentials — it produces
spec objects with placeholder env vars (${VAR}). The CredentialInjector
expands them later.
"""

from __future__ import annotations

import hashlib
import shlex
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import yaml

CATALOG_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BackendSpec:
    """Materialised view of a single enabled MCP server from the catalog."""

    name: str
    domain: str
    owner_agent: str
    transport: str
    command: str
    args: tuple[str, ...]
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    expected_tools: tuple[str, ...] = ()
    notes: str = ""

    def to_mcp_entry(self) -> dict[str, Any]:
        """Render to FastMCP-compatible mcpServers entry.

        For HTTP/SSE backends, produces ``{"url": ..., "transport": ...}``
        with optional ``headers`` dict.
        For stdio backends, produces ``{"command": ..., "args": [...]}``.
        """
        if self.url and self.transport in ("http", "sse"):
            result: dict[str, Any] = {"url": self.url, "transport": self.transport}
            if self.headers:
                result["headers"] = dict(self.headers)
            return result
        result = {"command": self.command, "args": list(self.args)}
        if self.env:
            result["env"] = dict(self.env)
        return result


def load_backends(catalog_path: Path) -> list[BackendSpec]:
    """Parse the YAML catalog and return enabled, lifecycle-active backends."""
    if not catalog_path.exists():
        raise FileNotFoundError(f"catalog not found: {catalog_path}")
    data = yaml.safe_load(catalog_path.read_text()) or {}
    raw_servers = data.get("servers", []) or []
    backends: list[BackendSpec] = []
    for entry in raw_servers:
        if not isinstance(entry, dict):
            continue
        if entry.get("lifecycle") != "enabled":
            continue
        spec = _parse_entry(entry)
        if spec is not None:
            backends.append(spec)
    return backends


def catalog_hash(catalog_path: Path) -> str:
    """sha256 of the canonical bytes (used to invalidate the embedding cache)."""
    data = catalog_path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _parse_entry(entry: dict[str, Any]) -> BackendSpec | None:
    name = str(entry.get("name", "")).strip()
    if not name:
        return None
    source = str(entry.get("source_of_truth", "")).strip()
    if not source:
        return None
    transport = str(entry.get("transport", "stdio"))

    # For HTTP/SSE backends, source_of_truth may be a URL
    url = ""
    if transport in ("http", "sse"):
        url = str(entry.get("url", "")).strip() or ""
        if not url and source.startswith("http"):
            url = source

    if url:
        command = ""
        args: tuple[str, ...] = ()
    else:
        parts = shlex.split(source)
        if not parts:
            return None
        command = parts[0]
        args = tuple(parts[1:])

    return BackendSpec(
        name=name,
        domain=str(entry.get("domain", "")),
        owner_agent=str(entry.get("owner_agent", "")),
        transport=transport,
        command=command,
        args=args,
        url=url,
        headers={k: str(v) for k, v in entry.get("headers", {}).items()},
        env={k: str(v) for k, v in entry.get("env", {}).items()},
        expected_tools=tuple(str(t) for t in entry.get("expected_tools", [])),
        notes=str(entry.get("notes", "")),
    )
