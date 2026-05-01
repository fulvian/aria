"""Unit tests for the proxy wiring helper."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from aria.mcp.proxy.server import build_proxy


def test_package_importable() -> None:
    import aria.mcp.proxy

    assert hasattr(aria.mcp.proxy, "build_proxy")


def test_build_proxy_uses_supplied_paths(
    minimal_catalog: Path, tmp_path: Path, monkeypatch
) -> None:
    proxy_yaml = tmp_path / "proxy.yaml"
    proxy_yaml.write_text("search:\n  transform: bm25\n")

    monkeypatch.setenv("ARIA_PROXY_DISABLE_BACKENDS", "1")  # avoid stdio spawn
    proxy = build_proxy(catalog_path=minimal_catalog, proxy_config_path=proxy_yaml)

    assert proxy is not None
    assert proxy.name == "aria-mcp-proxy"


def test_build_proxy_skips_missing_catalog(tmp_path: Path) -> None:
    with patch.dict("os.environ", {"ARIA_PROXY_DISABLE_BACKENDS": "1"}):
        proxy = build_proxy(
            catalog_path=tmp_path / "missing.yaml",
            proxy_config_path=tmp_path / "missing-proxy.yaml",
            strict=False,
        )
        assert proxy is not None
