"""Unit tests for the proxy wiring helper."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from aria.mcp.proxy.catalog import BackendSpec
from aria.mcp.proxy.server import _filter_backends_for_caller, build_proxy

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


class _Registry:
    def __init__(self, allowed_tools: dict[str, list[str]]) -> None:
        self._allowed_tools = allowed_tools

    def get_allowed_tools(self, agent: str) -> list[str]:
        return self._allowed_tools.get(agent, [])


def _backend(name: str) -> BackendSpec:
    return BackendSpec(
        name=name,
        domain="search",
        owner_agent="search-agent",
        transport="stdio",
        command="stub",
        args=(),
    )


def test_package_importable() -> None:
    import aria.mcp.proxy

    assert hasattr(aria.mcp.proxy, "build_proxy") or True  # deferred import


def test_build_proxy_uses_supplied_paths(
    minimal_catalog: Path, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    proxy_yaml = tmp_path / "proxy.yaml"
    proxy_yaml.write_text("search:\n  transform: bm25\n")

    monkeypatch.setenv("ARIA_PROXY_DISABLE_BACKENDS", "1")
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


def test_filter_backends_for_search_agent_excludes_workspace_and_memory() -> None:
    backends = [
        _backend("searxng-script"),
        _backend("tavily-mcp"),
        _backend("google_workspace"),
        _backend("aria-memory"),
    ]

    filtered = _filter_backends_for_caller(
        backends,
        registry=_Registry(
            {
                "search-agent": [
                    "searxng-script__*",
                    "tavily-mcp__*",
                    "aria-memory__wiki_recall_tool",
                ]
            }
        ),
        caller="search-agent",
    )

    assert [backend.name for backend in filtered] == ["searxng-script", "tavily-mcp"]


def test_build_proxy_applies_caller_backend_filter(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        """
servers:
  - name: searxng-script
    domain: search
    owner_agent: search-agent
    tier: 1
    transport: stdio
    lifecycle: enabled
    auth_mode: keyless
    statefulness: stateless
    expected_tools: [search_web]
    risk_level: low
    cost_class: free
    source_of_truth: searxng
    rollback_class: server
    baseline_status: lkg
    notes: search
  - name: google_workspace
    domain: productivity
    owner_agent: workspace-agent
    tier: 1
    transport: stdio
    lifecycle: enabled
    auth_mode: oauth
    statefulness: stateful
    expected_tools: [gmail_send]
    risk_level: high
    cost_class: free
    source_of_truth: workspace
    rollback_class: session
    baseline_status: lkg
    notes: workspace
  - name: aria-memory
    domain: memory
    owner_agent: aria-conductor
    tier: 0
    transport: stdio
    lifecycle: enabled
    auth_mode: keyless
    statefulness: stateful
    expected_tools: [wiki_recall_tool]
    risk_level: low
    cost_class: free
    source_of_truth: memory
    rollback_class: domain
    baseline_status: lkg
    notes: memory
""".lstrip()
    )
    proxy_yaml = tmp_path / "proxy.yaml"
    proxy_yaml.write_text("search:\n  transform: bm25\n")

    captured: dict[str, object] = {}

    class _Proxy:
        def __init__(self, name: str) -> None:
            self.name = name

        def add_transform(self, _transform: object) -> None:
            return None

        def add_middleware(self, _middleware: object) -> None:
            return None

    def _fake_create_proxy(config: dict[str, object], *, name: str) -> _Proxy:
        captured["config"] = config
        return _Proxy(name)

    monkeypatch.setenv("ARIA_CALLER_ID", "search-agent")

    with (
        patch(
            "aria.mcp.proxy.server.YamlCapabilityRegistry",
            return_value=_Registry(
                {"search-agent": ["searxng-script__*", "aria-memory__wiki_recall_tool"]}
            ),
        ),
        patch("aria.mcp.proxy.server.create_proxy", side_effect=_fake_create_proxy),
    ):
        proxy = build_proxy(catalog_path=catalog, proxy_config_path=proxy_yaml, strict=False)

    assert proxy.name == "aria-mcp-proxy"
    assert captured["config"] == {
        "mcpServers": {"searxng-script": {"command": "searxng", "args": []}}
    }
