"""Unit tests for CredentialInjector."""

from __future__ import annotations

import pytest

from aria.mcp.proxy.catalog import BackendSpec
from aria.mcp.proxy.credential import CredentialInjector


class _FakeManager:
    def __init__(self, mapping: dict[str, str]):
        self._m = mapping

    def get(self, key: str) -> str | None:
        return self._m.get(key)


def _spec(env_template: dict[str, str]) -> BackendSpec:
    return BackendSpec(
        name="tavily-mcp",
        domain="search",
        owner_agent="search-agent",
        transport="stdio",
        command="bash",
        args=("scripts/wrappers/tavily-wrapper.sh",),
        env=dict(env_template),
        expected_tools=("tavily_search",),
    )


def test_expands_placeholder_envs() -> None:
    manager = _FakeManager({"TAVILY_API_KEY": "tvly-secret"})
    inj = CredentialInjector(manager=manager)
    spec = _spec({"TAVILY_API_KEY": "${TAVILY_API_KEY}"})
    expanded = inj.inject(spec)
    assert expanded.env["TAVILY_API_KEY"] == "tvly-secret"


def test_unresolved_placeholder_raises() -> None:
    manager = _FakeManager({})
    inj = CredentialInjector(manager=manager)
    spec = _spec({"ARIA_ZZZ_UNDEFINED_KEY": "${ARIA_ZZZ_UNDEFINED_KEY}"})
    with pytest.raises(KeyError, match="ARIA_ZZZ_UNDEFINED_KEY"):
        inj.inject(spec)


def test_passthrough_for_literals() -> None:
    manager = _FakeManager({})
    inj = CredentialInjector(manager=manager)
    spec = _spec({"GOOGLE_OAUTH_REDIRECT_URI": "http://127.0.0.1:8080/callback"})
    expanded = inj.inject(spec)
    assert expanded.env["GOOGLE_OAUTH_REDIRECT_URI"] == "http://127.0.0.1:8080/callback"


def test_no_env_returns_unchanged() -> None:
    manager = _FakeManager({})
    inj = CredentialInjector(manager=manager)
    spec = _spec({})
    out = inj.inject(spec)
    assert out is spec  # short-circuit


def test_inject_all_filters_failures() -> None:
    manager = _FakeManager({"TAVILY_API_KEY": "tvly-x"})
    inj = CredentialInjector(manager=manager)
    ok = _spec({"TAVILY_API_KEY": "${TAVILY_API_KEY}"})
    bad = BackendSpec(
        name="bad",
        domain="x",
        owner_agent="x",
        transport="stdio",
        command="bash",
        args=(),
        env={"MISSING": "${MISSING}"},
    )
    survived = inj.inject_all([ok, bad], strict=False)
    assert [s.name for s in survived] == ["tavily-mcp"]


def test_inject_all_strict_raises() -> None:
    manager = _FakeManager({})
    inj = CredentialInjector(manager=manager)
    bad = BackendSpec(
        name="bad",
        domain="x",
        owner_agent="x",
        transport="stdio",
        command="bash",
        args=(),
        env={"MISSING": "${MISSING}"},
    )
    with pytest.raises(KeyError):
        inj.inject_all([bad], strict=True)


# ---------------------------------------------------------------------------
# Headers resolution tests
# ---------------------------------------------------------------------------


def _http_spec(
    headers_template: dict[str, str] | None = None,
    env_template: dict[str, str] | None = None,
) -> BackendSpec:
    return BackendSpec(
        name="context7",
        domain="search",
        owner_agent="search-agent",
        transport="http",
        command="",
        args=(),
        url="https://mcp.context7.com/mcp",
        headers=dict(headers_template or {}),
        env=dict(env_template or {}),
        expected_tools=("resolve-library-id", "query-docs"),
    )


def test_expands_placeholder_in_headers() -> None:
    manager = _FakeManager({"CONTEXT7_API_KEY": "ctx7-secret-key"})
    inj = CredentialInjector(manager=manager)
    spec = _http_spec(headers_template={"Authorization": "Bearer ${CONTEXT7_API_KEY}"})
    expanded = inj.inject(spec)
    assert expanded.headers["Authorization"] == "Bearer ctx7-secret-key"


def test_unresolved_header_placeholder_raises() -> None:
    manager = _FakeManager({})
    inj = CredentialInjector(manager=manager)
    spec = _http_spec(headers_template={"Authorization": "Bearer ${THIS_VAR_DOES_NOT_EXIST_ZZZ}"})
    with pytest.raises(KeyError, match="THIS_VAR_DOES_NOT_EXIST_ZZZ"):
        inj.inject(spec)


def test_headers_and_env_resolved_together() -> None:
    manager = _FakeManager(
        {
            "CONTEXT7_API_KEY": "ctx7-secret",
            "GHDISC_GITHUB_TOKEN": "ghp-some-token",
        }
    )
    inj = CredentialInjector(manager=manager)
    spec = _http_spec(
        headers_template={"Authorization": "Bearer ${CONTEXT7_API_KEY}"},
        env_template={"GHDISC_GITHUB_TOKEN": "${GHDISC_GITHUB_TOKEN}"},
    )
    expanded = inj.inject(spec)
    assert expanded.headers["Authorization"] == "Bearer ctx7-secret"
    assert expanded.env["GHDISC_GITHUB_TOKEN"] == "ghp-some-token"


def test_no_headers_returns_spec_unchanged() -> None:
    manager = _FakeManager({})
    inj = CredentialInjector(manager=manager)
    spec = _http_spec(headers_template={}, env_template={})
    out = inj.inject(spec)
    assert out is spec


def test_headers_literal_passthrough() -> None:
    """Header values without ${VAR} syntax pass through unchanged."""
    manager = _FakeManager({})
    inj = CredentialInjector(manager=manager)
    spec = _http_spec(headers_template={"X-Custom": "static-value"})
    expanded = inj.inject(spec)
    assert expanded.headers["X-Custom"] == "static-value"
