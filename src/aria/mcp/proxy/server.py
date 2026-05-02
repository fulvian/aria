"""Wire FastMCP, the catalog loader, the search transform, and the middleware
into a runnable proxy server.

`build_proxy()` returns a fully configured `FastMCP` instance.  Callers run
it via ``await proxy.run_async(transport="stdio")``.

Architecture
------------
The proxy uses a **catalog-driven** approach for tool discovery and a
**lazy backend broker** for tool invocation:

* ``search_tools`` — indexes catalog metadata (``expected_tools`` from
  ``mcp_catalog.yaml``) via the configured search transform (BM25 / hybrid).
  No live backend sessions are created during search.
* ``call_tool`` — resolves the target backend from the tool name and
  creates a single-backend proxy on demand via
  :class:`~aria.mcp.proxy.broker.LazyBackendBroker`.  Only the requested
  backend is contacted.
* :class:`~aria.mcp.proxy.middleware.CapabilityMatrixMiddleware` enforces
  per-agent tool allow-lists at runtime.

This design avoids the latency and stdout noise from booting unrelated
backends (e.g. ``google_workspace``, ``filesystem``) during
``search_tools`` for domain-specific agents like ``trader-agent``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool

from aria.agents.coordination.registry import YamlCapabilityRegistry
from aria.mcp.proxy.broker import LazyBackendBroker
from aria.mcp.proxy.catalog import BackendSpec, load_backends
from aria.mcp.proxy.config import ProxyConfig
from aria.mcp.proxy.credential import CredentialInjector
from aria.mcp.proxy.middleware import CapabilityMatrixMiddleware
from aria.mcp.proxy.transforms.hybrid import HybridSearchTransform
from aria.mcp.proxy.transforms.lmstudio_embedder import LMStudioEmbedder
from aria.utils.logging import get_logger

logger = get_logger("aria.mcp.proxy.server")

DEFAULT_CATALOG = Path(".aria/config/mcp_catalog.yaml")
DEFAULT_PROXY_CONFIG = Path(".aria/config/proxy.yaml")
PROXY_NAME = "aria-mcp-proxy"
CALLER_ENV = "ARIA_CALLER_ID"
DIRECT_SERVER_ALLOWLIST = frozenset({"spawn-subagent"})
SEPARATE_SERVERS = frozenset({"aria-memory"})


def build_proxy(
    *,
    catalog_path: Path | None = None,
    proxy_config_path: Path | None = None,
    strict: bool = False,
) -> FastMCP:
    """Build and return a fully configured proxy ``FastMCP`` server.

    Uses catalog-driven tool discovery and lazy backend invocation
    instead of eagerly connecting to all backends at boot time.
    """
    catalog_path = catalog_path or DEFAULT_CATALOG
    proxy_config_path = proxy_config_path or DEFAULT_PROXY_CONFIG

    cfg = ProxyConfig.load(proxy_config_path)
    registry = YamlCapabilityRegistry()
    caller = _proxy_caller()
    backends = _load_backends(catalog_path, strict=strict, registry=registry, caller=caller)
    if os.environ.get("ARIA_PROXY_DISABLE_BACKENDS") == "1":
        backends = []

    broker = LazyBackendBroker(backends) if backends else None
    server = FastMCP(name=PROXY_NAME)

    _register_proxy_tools(server, broker, cfg)
    server.add_middleware(CapabilityMatrixMiddleware(registry))
    return server


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def _register_proxy_tools(
    server: FastMCP,
    broker: LazyBackendBroker | None,
    cfg: ProxyConfig,
) -> None:
    """Register ``search_tools`` and ``call_tool`` on the proxy server."""
    transform = _build_transform(cfg)
    catalog = broker.catalog_tools() if broker else []

    async def _search_tools(query: str) -> str:
        """Search available tools by natural language query."""
        if not catalog:
            return json.dumps([])
        results = await transform._search(catalog, query)
        return json.dumps(
            [
                {
                    "name": t.name,
                    "description": getattr(t, "description", ""),
                }
                for t in results
            ]
        )

    async def _call_tool(name: str, arguments: dict | None = None) -> Any:  # noqa: ANN401
        """Call a backend tool by name with the given arguments."""
        if broker is None:
            raise ToolError("No backends configured")
        resolved = broker.resolve_tool(name)
        if resolved is None:
            raise ToolError(f"Cannot resolve backend for tool: {name}")
        server_name, tool_name = resolved
        # Strip _caller_id from nested arguments (re-injected by middleware
        # for the original two-pass proxy architecture).  Since we route
        # directly through the broker (single-pass), it must be removed.
        clean_args = _strip_caller_id(arguments or {})
        return await broker.call(server_name, tool_name, clean_args)

    # Register both tools on the server
    server.add_tool(
        Tool.from_function(
            _search_tools,
            name="search_tools",
            description="Search available MCP tools by natural language query.",
        )
    )
    server.add_tool(
        Tool.from_function(
            _call_tool,
            name="call_tool",
            description="Call an MCP tool by namespaced name.",
        )
    )


def _strip_caller_id(arguments: dict) -> dict:
    """Remove ``_caller_id`` from arguments dict (and nested dicts)."""
    cleaned = {k: v for k, v in arguments.items() if k != "_caller_id"}
    # Also strip from nested "arguments" dict if present
    nested = cleaned.get("arguments")
    if isinstance(nested, dict):
        cleaned["arguments"] = {k: v for k, v in nested.items() if k != "_caller_id"}
    return cleaned


# ---------------------------------------------------------------------------
# Backend loading helpers (unchanged)
# ---------------------------------------------------------------------------


def _proxy_caller() -> str | None:
    caller = os.environ.get(CALLER_ENV, "").strip()
    return caller or None


def _load_backends(
    catalog_path: Path,
    *,
    strict: bool,
    registry: YamlCapabilityRegistry | None = None,
    caller: str | None = None,
) -> list[BackendSpec]:
    if not catalog_path.exists():
        logger.warning(
            "catalog_missing",
            extra={"path": str(catalog_path)},
        )
        return []
    try:
        from aria.credentials.manager import CredentialManager

        manager: Any = CredentialManager()
    except Exception:  # pragma: no cover
        manager = None
    raw = load_backends(catalog_path)
    injector = CredentialInjector(manager=manager)
    backends = injector.inject_all(raw, strict=strict)
    return _filter_backends_for_caller(backends, registry=registry, caller=caller)


def _filter_backends_for_caller(
    backends: list[BackendSpec],
    *,
    registry: YamlCapabilityRegistry | None,
    caller: str | None,
) -> list[BackendSpec]:
    allowed_server_names = _allowed_server_names(registry, caller)
    filtered: list[BackendSpec] = []
    for backend in backends:
        if backend.name in SEPARATE_SERVERS:
            continue
        if allowed_server_names is not None and backend.name not in allowed_server_names:
            continue
        filtered.append(backend)
    return filtered


def _allowed_server_names(
    registry: YamlCapabilityRegistry | None,
    caller: str | None,
) -> set[str] | None:
    if registry is None or not caller:
        return None

    allowed_tools = registry.get_allowed_tools(caller)
    if not allowed_tools:
        return set()

    server_names: set[str] = set()
    for tool_name in allowed_tools:
        server_name = _tool_server_name(tool_name)
        if server_name is not None:
            server_names.add(server_name)
    return server_names


def _tool_server_name(tool_name: str) -> str | None:
    cleaned = tool_name.strip()
    if not cleaned or cleaned in DIRECT_SERVER_ALLOWLIST:
        return None
    if "__" in cleaned:
        return cleaned.split("__", 1)[0] or None
    if "/" in cleaned:
        return cleaned.split("/", 1)[0] or None
    return None


def _build_transform(cfg: ProxyConfig) -> Any:  # noqa: ANN401
    if cfg.search.transform == "regex":
        try:
            from fastmcp.server.transforms.search.regex import RegexSearchTransform
        except ImportError:
            from fastmcp.server.transforms.search import RegexSearchTransform

        return RegexSearchTransform()
    if cfg.search.transform == "bm25":
        try:
            from fastmcp.server.transforms.search.bm25 import BM25SearchTransform
        except ImportError:
            from fastmcp.server.transforms.search import BM25SearchTransform

        return BM25SearchTransform()
    embedder = LMStudioEmbedder(
        endpoint=cfg.search.embedding.endpoint,
        model=cfg.search.embedding.model,
        dim=cfg.search.embedding.dim,
        timeout_s=cfg.search.embedding.timeout_s,
    )
    return HybridSearchTransform(
        embedder=embedder,
        blend=cfg.search.blend,
    )
