"""Unit tests for CredentialInjector."""
from __future__ import annotations

from typing import Any

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
        name="bad", domain="x", owner_agent="x", transport="stdio",
        command="bash", args=(),
        env={"MISSING": "${MISSING}"},
    )
    survived = inj.inject_all([ok, bad], strict=False)
    assert [s.name for s in survived] == ["tavily-mcp"]


def test_inject_all_strict_raises() -> None:
    manager = _FakeManager({})
    inj = CredentialInjector(manager=manager)
    bad = BackendSpec(
        name="bad", domain="x", owner_agent="x", transport="stdio",
        command="bash", args=(),
        env={"MISSING": "${MISSING}"},
    )
    with pytest.raises(KeyError):
        inj.inject_all([bad], strict=True)
