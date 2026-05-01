"""Wire FastMCP, the catalog loader, the search transform, and the middleware
into a runnable proxy server.

`build_proxy()` returns a fully configured `FastMCP` instance. Callers run
it via `await proxy.run_async(transport="stdio")`.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server import create_proxy

from aria.agents.coordination.registry import YamlCapabilityRegistry
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


def build_proxy(
    *,
    catalog_path: Path | None = None,
    proxy_config_path: Path | None = None,
    strict: bool = False,
) -> FastMCP:
    catalog_path = catalog_path or DEFAULT_CATALOG
    proxy_config_path = proxy_config_path or DEFAULT_PROXY_CONFIG

    cfg = ProxyConfig.load(proxy_config_path)
    backends = _load_backends(catalog_path, strict=strict)
    if os.environ.get("ARIA_PROXY_DISABLE_BACKENDS") == "1":
        # used in unit tests to avoid stdio spawn
        backends = []

    if backends:
        composite = create_proxy(
            {"mcpServers": {b.name: b.to_mcp_entry() for b in backends}},
            name=PROXY_NAME,
        )
    else:
        composite = FastMCP(name=PROXY_NAME)

    composite.add_transform(_build_transform(cfg))
    composite.add_middleware(CapabilityMatrixMiddleware(YamlCapabilityRegistry()))
    return composite


def _load_backends(catalog_path: Path, *, strict: bool) -> list[BackendSpec]:
    if not catalog_path.exists():
        logger.warning(
            "catalog_missing",
            extra={"path": str(catalog_path)},
        )
        return []
    try:
        from aria.credentials.manager import CredentialManager  # type: ignore
        manager = CredentialManager()
    except Exception:  # pragma: no cover — keep proxy bootable without creds
        manager = None
    raw = load_backends(catalog_path)
    injector = CredentialInjector(manager=manager)
    return injector.inject_all(raw, strict=strict)


def _build_transform(cfg: ProxyConfig):
    if cfg.search.transform == "regex":
        try:
            from fastmcp.server.transforms.search.regex import RegexSearchTransform
        except ImportError:
            from fastmcp.server.transforms.search import RegexSearchTransform  # type: ignore[no-redef]
        return RegexSearchTransform()
    if cfg.search.transform == "bm25":
        try:
            from fastmcp.server.transforms.search.bm25 import BM25SearchTransform
        except ImportError:
            from fastmcp.server.transforms.search import BM25SearchTransform  # type: ignore[no-redef]
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
