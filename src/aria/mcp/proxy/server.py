"""Wire FastMCP, the catalog loader, the search transform, and the middleware
into a runnable proxy server.

`build_proxy()` returns a fully configured `FastMCP` instance. Callers run
it via `await proxy.run_async(transport="stdio")`.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from aria.agents.coordination.registry import YamlCapabilityRegistry
from aria.mcp.proxy.catalog import BackendSpec, load_backends
from aria.mcp.proxy.config import ProxyConfig
from aria.mcp.proxy.credential import CredentialInjector
from aria.mcp.proxy.middleware import CapabilityMatrixMiddleware
from aria.mcp.proxy.provider import TimeoutProxyProvider
from aria.mcp.proxy.transforms.hybrid import HybridSearchTransform
from aria.mcp.proxy.transforms.lmstudio_embedder import LMStudioEmbedder
from aria.utils.logging import get_logger

try:
    fastmcp_proxy_provider: Any | None = importlib.import_module("fastmcp.server.providers.proxy")
except ImportError:
    fastmcp_proxy_provider = None  # pragma: no cover

logger = get_logger("aria.mcp.proxy.server")

DEFAULT_CATALOG = Path(".aria/config/mcp_catalog.yaml")
DEFAULT_PROXY_CONFIG = Path(".aria/config/proxy.yaml")
PROXY_NAME = "aria-mcp-proxy"
BOOT_CALLER_ENV = "ARIA_PROXY_BOOT_CALLER_ID"
LEGACY_CALLER_ENV = "ARIA_CALLER_ID"
ALLOW_LEGACY_CALLER_ENV = "ARIA_PROXY_ALLOW_LEGACY_CALLER_ENV"
DIRECT_SERVER_ALLOWLIST = frozenset({"spawn-subagent"})
SEPARATE_SERVERS = frozenset({"aria-memory"})


def build_proxy(
    *,
    catalog_path: Path | None = None,
    proxy_config_path: Path | None = None,
    strict: bool = False,
) -> FastMCP:
    catalog_path = catalog_path or DEFAULT_CATALOG
    proxy_config_path = proxy_config_path or DEFAULT_PROXY_CONFIG

    cfg = ProxyConfig.load(proxy_config_path)
    registry = YamlCapabilityRegistry()
    caller = _proxy_caller()
    backends = _load_backends(catalog_path, strict=strict, registry=registry, caller=caller)
    if os.environ.get("ARIA_PROXY_DISABLE_BACKENDS") == "1":
        backends = []

    composite = FastMCP(name=PROXY_NAME)
    if backends and fastmcp_proxy_provider is not None:
        client_factory = fastmcp_proxy_provider._create_client_factory(
            {"mcpServers": {b.name: b.to_mcp_entry() for b in backends}}
        )
        composite.add_provider(TimeoutProxyProvider(client_factory, list_timeout_s=30.0))

    composite.add_transform(_build_transform(cfg))
    composite.add_middleware(CapabilityMatrixMiddleware(registry))
    return composite


def _proxy_caller() -> str | None:
    caller = os.environ.get(BOOT_CALLER_ENV, "").strip()
    if caller:
        return caller

    if os.environ.get(ALLOW_LEGACY_CALLER_ENV) == "1":
        legacy_caller = os.environ.get(LEGACY_CALLER_ENV, "").strip()
        return legacy_caller or None

    return None


def _load_backends(
    catalog_path: Path,
    *,
    strict: bool,
    registry: YamlCapabilityRegistry | None = None,
    caller: str | None = None,
) -> list[BackendSpec]:  # noqa: ANN202
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
