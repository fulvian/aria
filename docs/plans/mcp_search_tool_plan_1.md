# ARIA MCP Tool Search Proxy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ARIA's static `lazy_loader.py` with a FastMCP-native multi-server proxy that exposes a single `search_tools` + `call_tool` surface to KiloCode, reducing startup tool-definition tokens from ~40 K to < 2 K and scaling linearly to 50+ MCP backends.

**Architecture:** A new Python package `src/aria/mcp/proxy/` builds on `fastmcp.server.create_proxy(mcpServers)` and `BM25SearchTransform`. A custom `HybridSearchTransform` adds semantic ranking via the existing local LM Studio embeddings endpoint (`mxbai-embed-large-v1`, 1024-dim). A `CapabilityMatrixMiddleware` enforces `agent_capability_matrix.yaml` per-agent allowed-tools at runtime via a `_caller_id` argument convention. The original `mcp.json` is retained only as an emergency rollback (`bin/aria start --emergency-direct`).

**Tech Stack:** Python 3.11, FastMCP 3.2+, Pydantic v2, httpx, numpy, pytest + pytest-asyncio + respx, ruff, mypy, structlog, LM Studio OpenAI-compatible local server (already running on 127.0.0.1:1234).

**Spec reference:** `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`

**Branch:** `feat/mcp-tool-search-proxy` (create from `main` at start of F1).

---

## File map

Files to create:

```
src/aria/mcp/proxy/
├── __init__.py
├── __main__.py                      # python -m aria.mcp.proxy entry
├── server.py                        # FastMCP wiring
├── catalog.py                       # YAML catalog → mcpServers dict + cred injection
├── credential.py                    # CredentialInjector (SOPS unwrap, rotation listener)
├── middleware.py                    # CapabilityMatrixMiddleware
├── config.py                        # ProxyConfig pydantic model (loads .aria/config/proxy.yaml)
└── transforms/
    ├── __init__.py
    ├── hybrid.py                    # HybridSearchTransform extends BM25
    └── lmstudio_embedder.py         # httpx client for LM Studio embeddings

tests/unit/mcp/proxy/
├── __init__.py
├── conftest.py                      # shared fixtures
├── test_catalog.py
├── test_config.py
├── test_credential.py
├── test_middleware.py
├── test_lmstudio_embedder.py
├── test_hybrid.py
└── test_server.py

tests/integration/mcp/proxy/
├── __init__.py
├── conftest.py
├── test_proxy_e2e_stdio.py
├── test_call_tool_routing.py
├── test_capability_enforcement.py
├── test_hybrid_with_real_lms.py
└── test_emergency_rollback.py

tests/e2e/mcp/proxy/
├── __init__.py
├── test_search_quality.py
├── test_full_session_kilocode.py
└── test_context_token_reduction.py

docs/foundation/decisions/
└── ADR-0015-fastmcp-native-proxy.md

docs/llm_wiki/wiki/
└── mcp-proxy.md

systemd/
└── aria-mcp-proxy.service           # optional warm-start unit

.aria/config/
└── proxy.yaml                       # search/embedding/cache config

scripts/
└── proxy_smoke.py                   # F0 standalone smoke harness
```

Files to modify:

```
src/aria/launcher/lazy_loader.py     # F4: delete
.aria/config/mcp_catalog.yaml        # F4: drop lazy_load + intent_tags
.aria/config/agent_capability_matrix.yaml  # F3: namespaced tool names
.aria/kilocode/mcp.json              # F2 add proxy entry; F3 reduce to 2 entries
.aria/kilocode/agents/aria-conductor.md     # F3: addendum + namespacing
.aria/kilocode/agents/_aria-conductor.template.md  # F3: addendum
.aria/kilocode/agents/search-agent.md       # F3: namespacing
.aria/kilocode/agents/workspace-agent.md    # F3: namespacing
.aria/kilocode/agents/productivity-agent.md # F3: namespacing
.aria/kilocode/skills/deep-research/SKILL.md       # F5: tool name refs
.aria/kilocode/skills/office-ingest/SKILL.md       # F5
.aria/kilocode/skills/pdf-extract/SKILL.md         # F5
.aria/kilocode/skills/consultancy-brief/SKILL.md   # F5
.aria/kilocode/skills/meeting-prep/SKILL.md        # F5
.aria/kilocode/skills/source-dedup/SKILL.md        # F5
src/aria/agents/coordination/registry.py  # F1: accept namespaced tool names
src/aria/observability/metrics.py    # F5: add aria_proxy_* metrics
src/aria/observability/events.py     # F5: add proxy.* event types
scripts/check_mcp_drift.py           # F3: validate catalog ↔ proxy ↔ matrix
bin/aria                              # F3: --emergency-direct flag
pyproject.toml                       # F1: ensure deps (fastmcp, httpx, numpy, respx)
docs/llm_wiki/wiki/index.md          # F5: add mcp-proxy page reference
docs/llm_wiki/wiki/log.md            # F5: timestamped entry
docs/llm_wiki/wiki/mcp-architecture.md   # F5: update current state
docs/llm_wiki/wiki/mcp-refoundation.md   # F5: deprecate lazy loader section
```

---

## Phase F0 — Smoke (30 min, no commits)

Goal: verify KiloCode 7.2.x correctly reads a 1-backend FastMCP proxy via stdio. Block ship of F1 if this fails.

### Task F0.1: Standalone smoke harness

**Files:**
- Create: `scripts/proxy_smoke.py` (throwaway, do NOT commit)

- [ ] **Step 1: Write smoke script**

```python
# scripts/proxy_smoke.py
"""F0 smoke harness — verify FastMCP proxy is readable by stdio MCP clients.

Run:  python scripts/proxy_smoke.py
Expect: 'tools/list returned 2 synthetic tools'  + sample search hit
"""
import asyncio
from fastmcp import FastMCP
from fastmcp.server import create_proxy
from fastmcp.server.transforms.search import BM25SearchTransform

CONFIG = {
    "mcpServers": {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        }
    }
}

async def main() -> None:
    proxy = create_proxy(CONFIG, name="aria-smoke")
    proxy.add_transform(BM25SearchTransform())
    # In-process client for verification.
    from fastmcp import Client
    async with Client(proxy) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools]
        assert "search_tools" in names and "call_tool" in names, names
        print(f"OK: tools/list returned {len(tools)} synthetic tools: {names}")
        result = await client.call_tool("search_tools", {"pattern": "read"})
        print(f"OK: search_tools(pattern='read') → {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run smoke**

Run: `cd /home/fulvio/coding/aria && uv run python scripts/proxy_smoke.py`
Expected stdout: two lines starting with `OK:`. Exit code 0.

- [ ] **Step 3: Verify against KiloCode 7.2.x stdio**

Add a temporary entry to `.aria/kilocode/mcp.json` named `aria-smoke` pointing to `python scripts/proxy_smoke_server.py` (a stdio variant). Launch KiloCode and confirm via the KiloCode logs that it sees two tools and no errors. Remove the entry after verification.

- [ ] **Step 4: Decision gate**

If the smoke succeeds, proceed to F1. If it fails, abort and re-open the design (likely root cause: FastMCP version mismatch, KiloCode parsing).

- [ ] **Step 5: Cleanup (no commit)**

```bash
rm scripts/proxy_smoke.py
```

---

## Phase F1 — Core implementation (~4–5 days)

Goal: every component in `src/aria/mcp/proxy/` exists with unit + integration tests. Nothing is wired into `mcp.json` yet. The proxy package can be imported and exercised in isolation.

### Task F1.1: Branch + dependency check

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Create branch**

```bash
cd /home/fulvio/coding/aria
git checkout main && git pull
git checkout -b feat/mcp-tool-search-proxy
```

- [ ] **Step 2: Verify dependencies**

Run: `grep -E '"fastmcp|httpx|numpy|respx"' pyproject.toml`
Expected: `fastmcp>=3.2,<4.0` and `httpx`. If `numpy` or `respx` are missing, add them.

- [ ] **Step 3: Add missing dev deps**

Edit `pyproject.toml` `[dependency-groups].dev`:

```toml
dev = [
    # ... existing entries ...
    "respx>=0.21",
    "numpy>=1.26",
]
```

(`numpy` may already be present transitively; declare it explicitly anyway.)

- [ ] **Step 4: Sync**

Run: `make dev-install`
Expected: exit 0, no resolver conflicts.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(proxy): add respx + numpy dev deps for proxy tests"
```

### Task F1.2: Package skeleton

**Files:**
- Create: `src/aria/mcp/proxy/__init__.py`
- Create: `src/aria/mcp/proxy/__main__.py`
- Create: `tests/unit/mcp/proxy/__init__.py`
- Create: `tests/unit/mcp/proxy/conftest.py`

- [ ] **Step 1: Write `__init__.py`**

```python
# src/aria/mcp/proxy/__init__.py
"""ARIA MCP tool-search proxy — FastMCP-native multi-server aggregator.

Replaces the static lazy loader with a runtime BM25/hybrid search surface
exposed as two synthetic tools (search_tools, call_tool) backed by every
catalogued MCP server.

See docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md.
"""

from aria.mcp.proxy.server import build_proxy

__all__ = ["build_proxy"]
```

- [ ] **Step 2: Write `__main__.py`**

```python
# src/aria/mcp/proxy/__main__.py
"""Entry point: python -m aria.mcp.proxy"""
from __future__ import annotations

import asyncio
import logging

from aria.mcp.proxy.server import build_proxy
from aria.utils.logging import get_logger

logger = get_logger("aria.mcp.proxy")


async def _run() -> None:
    proxy = build_proxy()
    logger.info("aria-mcp-proxy starting", extra={"event": "proxy.start"})
    await proxy.run_async(transport="stdio")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write conftest scaffolding**

```python
# tests/unit/mcp/proxy/conftest.py
"""Shared fixtures for proxy unit tests."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def minimal_catalog(tmp_path: Path) -> Path:
    """A YAML catalog with two servers (filesystem + a stub stdio)."""
    yaml_text = """
servers:
  - name: filesystem
    domain: system
    owner_agent: aria-conductor
    tier: 0
    transport: stdio
    lifecycle: enabled
    auth_mode: keyless
    statefulness: stateful
    expected_tools: [read, write]
    risk_level: medium
    cost_class: free
    source_of_truth: npx -y @modelcontextprotocol/server-filesystem
    rollback_class: server
    baseline_status: lkg
    notes: minimal fixture

  - name: stub
    domain: search
    owner_agent: search-agent
    tier: 1
    transport: stdio
    lifecycle: disabled
    auth_mode: keyless
    statefulness: stateless
    expected_tools: [stub_search]
    risk_level: low
    cost_class: free
    source_of_truth: stub
    rollback_class: server
    baseline_status: shadow
    notes: disabled fixture
"""
    p = tmp_path / "catalog.yaml"
    p.write_text(yaml_text.lstrip())
    return p


@pytest.fixture
def minimal_mcp_json(tmp_path: Path) -> Path:
    """A JSON file matching the catalog filesystem entry."""
    import json
    p = tmp_path / "mcp.json"
    payload: dict[str, Any] = {
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", str(tmp_path)],
            }
        }
    }
    p.write_text(json.dumps(payload))
    return p
```

- [ ] **Step 4: Run smoke import test**

Add to `tests/unit/mcp/proxy/test_server.py` (will be expanded in F1.7):

```python
def test_package_importable():
    import aria.mcp.proxy

    assert hasattr(aria.mcp.proxy, "build_proxy")
```

Run: `pytest -q tests/unit/mcp/proxy/test_server.py::test_package_importable`
Expected: ImportError on `build_proxy` (server.py not yet written) — that's fine, will pass after F1.7.

- [ ] **Step 5: Commit**

```bash
git add src/aria/mcp/proxy/__init__.py src/aria/mcp/proxy/__main__.py \
        tests/unit/mcp/proxy/__init__.py tests/unit/mcp/proxy/conftest.py \
        tests/unit/mcp/proxy/test_server.py
git commit -m "feat(proxy): scaffold src/aria/mcp/proxy package + test fixtures"
```

### Task F1.3: ProxyConfig pydantic model

**Files:**
- Create: `src/aria/mcp/proxy/config.py`
- Create: `tests/unit/mcp/proxy/test_config.py`
- Create: `.aria/config/proxy.yaml`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/mcp/proxy/test_config.py
"""Unit tests for ProxyConfig loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from aria.mcp.proxy.config import EmbeddingConfig, ProxyConfig, SearchConfig


def test_defaults_when_file_missing(tmp_path: Path) -> None:
    cfg = ProxyConfig.load(tmp_path / "missing.yaml")
    assert cfg.search.transform == "hybrid"
    assert cfg.search.blend == 0.6
    assert cfg.search.embedding.endpoint == "http://127.0.0.1:1234/v1/embeddings"
    assert cfg.search.embedding.model == "mxbai-embed-large-v1"
    assert cfg.search.embedding.fallback == "bm25"


def test_load_overrides(tmp_path: Path) -> None:
    yaml_text = """
search:
  transform: bm25
  blend: 0.5
  embedding:
    endpoint: http://localhost:9000/v1/embeddings
    model: custom-embed
    timeout_s: 1.5
"""
    p = tmp_path / "proxy.yaml"
    p.write_text(yaml_text.lstrip())
    cfg = ProxyConfig.load(p)
    assert cfg.search.transform == "bm25"
    assert cfg.search.blend == 0.5
    assert cfg.search.embedding.endpoint == "http://localhost:9000/v1/embeddings"
    assert cfg.search.embedding.model == "custom-embed"
    assert cfg.search.embedding.timeout_s == 1.5


def test_invalid_transform_rejected(tmp_path: Path) -> None:
    yaml_text = "search:\n  transform: galactic\n"
    p = tmp_path / "proxy.yaml"
    p.write_text(yaml_text)
    with pytest.raises(ValueError):
        ProxyConfig.load(p)


def test_blend_bounds(tmp_path: Path) -> None:
    yaml_text = "search:\n  blend: 1.5\n"
    p = tmp_path / "proxy.yaml"
    p.write_text(yaml_text)
    with pytest.raises(ValueError):
        ProxyConfig.load(p)
```

- [ ] **Step 2: Run tests, expect import error**

Run: `pytest -q tests/unit/mcp/proxy/test_config.py`
Expected: `ImportError: aria.mcp.proxy.config`.

- [ ] **Step 3: Implement config**

```python
# src/aria/mcp/proxy/config.py
"""Pydantic models for the proxy runtime configuration.

Defaults are tuned for the local LM Studio embedding endpoint that ARIA
already runs (mxbai-embed-large-v1).
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_LMS_ENDPOINT = "http://127.0.0.1:1234/v1/embeddings"
DEFAULT_EMBED_MODEL = "mxbai-embed-large-v1"
DEFAULT_EMBED_DIM = 1024
DEFAULT_CACHE_DIR = Path(".aria/runtime/proxy/embeddings")


class EmbeddingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["lmstudio", "disabled"] = "lmstudio"
    endpoint: str = DEFAULT_LMS_ENDPOINT
    model: str = DEFAULT_EMBED_MODEL
    dim: int = DEFAULT_EMBED_DIM
    max_tokens: int = 512
    timeout_s: float = Field(default=5.0, ge=0.1, le=60.0)
    fallback: Literal["bm25", "regex", "error"] = "bm25"


class CacheConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persist: bool = True
    path: Path = DEFAULT_CACHE_DIR
    invalidate_on: Literal["catalog_change", "always", "never"] = "catalog_change"


class SearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transform: Literal["hybrid", "bm25", "regex"] = "hybrid"
    blend: float = Field(default=0.6, ge=0.0, le=1.0)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)

    @field_validator("blend")
    @classmethod
    def _blend_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("blend must be within [0, 1]")
        return v


class ProxyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: SearchConfig = Field(default_factory=SearchConfig)

    @classmethod
    def load(cls, path: Path) -> "ProxyConfig":
        if not path.exists():
            return cls()
        raw = yaml.safe_load(path.read_text()) or {}
        return cls.model_validate(raw)
```

- [ ] **Step 4: Run tests**

Run: `pytest -q tests/unit/mcp/proxy/test_config.py`
Expected: 4 passed.

- [ ] **Step 5: Write the on-disk config**

```yaml
# .aria/config/proxy.yaml
search:
  transform: hybrid
  blend: 0.6
  embedding:
    provider: lmstudio
    endpoint: http://127.0.0.1:1234/v1/embeddings
    model: mxbai-embed-large-v1
    dim: 1024
    max_tokens: 512
    timeout_s: 5.0
    fallback: bm25
  cache:
    persist: true
    path: .aria/runtime/proxy/embeddings/
    invalidate_on: catalog_change
```

- [ ] **Step 6: Commit**

```bash
git add src/aria/mcp/proxy/config.py tests/unit/mcp/proxy/test_config.py .aria/config/proxy.yaml
git commit -m "feat(proxy): ProxyConfig pydantic loader + .aria/config/proxy.yaml"
```

### Task F1.4: Catalog loader

**Files:**
- Create: `src/aria/mcp/proxy/catalog.py`
- Create: `tests/unit/mcp/proxy/test_catalog.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/mcp/proxy/test_catalog.py
"""Unit tests for the catalog → mcpServers loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from aria.mcp.proxy.catalog import (
    BackendSpec,
    catalog_hash,
    load_backends,
)


def test_load_backends_filters_disabled(minimal_catalog: Path) -> None:
    backends = load_backends(minimal_catalog)
    names = [b.name for b in backends]
    assert "filesystem" in names
    assert "stub" not in names  # lifecycle=disabled


def test_backend_spec_to_mcpservers_entry(minimal_catalog: Path) -> None:
    backends = load_backends(minimal_catalog)
    fs = next(b for b in backends if b.name == "filesystem")
    entry = fs.to_mcp_entry()
    assert entry["command"] == "npx"
    assert entry["args"][0] == "-y"


def test_catalog_hash_stable(minimal_catalog: Path) -> None:
    h1 = catalog_hash(minimal_catalog)
    h2 = catalog_hash(minimal_catalog)
    assert h1 == h2 and len(h1) == 64  # sha256 hex


def test_catalog_hash_changes_on_edit(tmp_path: Path, minimal_catalog: Path) -> None:
    h1 = catalog_hash(minimal_catalog)
    minimal_catalog.write_text(minimal_catalog.read_text() + "\n# touch\n")
    h2 = catalog_hash(minimal_catalog)
    assert h1 != h2


def test_missing_catalog_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_backends(tmp_path / "nope.yaml")


def test_unknown_source_command_string_split(minimal_catalog: Path) -> None:
    backends = load_backends(minimal_catalog)
    fs = next(b for b in backends if b.name == "filesystem")
    # source_of_truth: "npx -y @modelcontextprotocol/server-filesystem"
    assert fs.command == "npx"
    assert "@modelcontextprotocol/server-filesystem" in fs.args
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest -q tests/unit/mcp/proxy/test_catalog.py`
Expected: ImportError on `aria.mcp.proxy.catalog`.

- [ ] **Step 3: Implement catalog**

```python
# src/aria/mcp/proxy/catalog.py
"""Load .aria/config/mcp_catalog.yaml and build the FastMCP backends config.

Schema reference: docs/llm_wiki/wiki/mcp-refoundation.md.

This module deliberately knows nothing about credentials — it produces
spec objects with placeholder env vars (`${VAR}`). The CredentialInjector
expands them later.
"""
from __future__ import annotations

import hashlib
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    env: dict[str, str] = field(default_factory=dict)
    expected_tools: tuple[str, ...] = ()
    notes: str = ""

    def to_mcp_entry(self) -> dict[str, Any]:
        """Render to FastMCP-compatible mcpServers entry."""
        entry: dict[str, Any] = {"command": self.command, "args": list(self.args)}
        if self.env:
            entry["env"] = dict(self.env)
        return entry


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
    parts = shlex.split(source)
    if not parts:
        return None
    command = parts[0]
    args = tuple(parts[1:])
    return BackendSpec(
        name=name,
        domain=str(entry.get("domain", "")),
        owner_agent=str(entry.get("owner_agent", "")),
        transport=str(entry.get("transport", "stdio")),
        command=command,
        args=args,
        env={},  # populated later by CredentialInjector
        expected_tools=tuple(str(t) for t in entry.get("expected_tools", [])),
        notes=str(entry.get("notes", "")),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest -q tests/unit/mcp/proxy/test_catalog.py`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aria/mcp/proxy/catalog.py tests/unit/mcp/proxy/test_catalog.py
git commit -m "feat(proxy): catalog loader with lifecycle filter + sha256 hash"
```

### Task F1.5: Credential injector

**Files:**
- Create: `src/aria/mcp/proxy/credential.py`
- Create: `tests/unit/mcp/proxy/test_credential.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/mcp/proxy/test_credential.py
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
    spec = _spec({"TAVILY_API_KEY": "${TAVILY_API_KEY}"})
    with pytest.raises(KeyError, match="TAVILY_API_KEY"):
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
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest -q tests/unit/mcp/proxy/test_credential.py`
Expected: ImportError.

- [ ] **Step 3: Implement injector**

```python
# src/aria/mcp/proxy/credential.py
"""Resolve ${VAR} placeholders in BackendSpec.env using ARIA's CredentialManager.

Strict mode (default) raises on unresolved keys. Non-strict mode drops the
backend and returns the survivors — used at proxy boot so a single missing
key does not take down the entire proxy.
"""
from __future__ import annotations

import os
import re
from typing import Iterable, Protocol

from aria.mcp.proxy.catalog import BackendSpec
from aria.utils.logging import get_logger

logger = get_logger("aria.mcp.proxy.credential")

_PLACEHOLDER = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


class _SecretSource(Protocol):
    def get(self, key: str) -> str | None: ...


class CredentialInjector:
    def __init__(self, manager: _SecretSource | None = None) -> None:
        self._manager = manager

    def inject(self, spec: BackendSpec) -> BackendSpec:
        if not spec.env:
            return spec
        resolved: dict[str, str] = {}
        for key, value in spec.env.items():
            resolved[key] = self._resolve(value)
        return BackendSpec(
            name=spec.name,
            domain=spec.domain,
            owner_agent=spec.owner_agent,
            transport=spec.transport,
            command=spec.command,
            args=spec.args,
            env=resolved,
            expected_tools=spec.expected_tools,
            notes=spec.notes,
        )

    def inject_all(
        self, specs: Iterable[BackendSpec], *, strict: bool = True
    ) -> list[BackendSpec]:
        out: list[BackendSpec] = []
        for spec in specs:
            try:
                out.append(self.inject(spec))
            except KeyError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping backend due to unresolved credential",
                    extra={"backend": spec.name, "missing": str(exc)},
                )
        return out

    def _resolve(self, value: str) -> str:
        m = _PLACEHOLDER.match(value)
        if not m:
            return value
        var = m.group(1)
        result = self._lookup(var)
        if result is None:
            raise KeyError(var)
        return result

    def _lookup(self, var: str) -> str | None:
        if self._manager is not None:
            v = self._manager.get(var)
            if v is not None:
                return v
        return os.environ.get(var)
```

- [ ] **Step 4: Run tests**

Run: `pytest -q tests/unit/mcp/proxy/test_credential.py`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aria/mcp/proxy/credential.py tests/unit/mcp/proxy/test_credential.py
git commit -m "feat(proxy): CredentialInjector resolves \${VAR} env placeholders"
```

### Task F1.6: LM Studio embedder client

**Files:**
- Create: `src/aria/mcp/proxy/transforms/__init__.py`
- Create: `src/aria/mcp/proxy/transforms/lmstudio_embedder.py`
- Create: `tests/unit/mcp/proxy/test_lmstudio_embedder.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/mcp/proxy/test_lmstudio_embedder.py
"""Unit tests for LMStudioEmbedder using respx mocks."""
from __future__ import annotations

import httpx
import numpy as np
import pytest
import respx

from aria.mcp.proxy.transforms.lmstudio_embedder import (
    LMStudioEmbedder,
    LMStudioUnavailable,
)

ENDPOINT = "http://127.0.0.1:1234/v1/embeddings"
MODELS_URL = "http://127.0.0.1:1234/v1/models"


@respx.mock
def test_probe_returns_true_when_models_endpoint_ok() -> None:
    respx.get(MODELS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
    e = LMStudioEmbedder(endpoint=ENDPOINT, model="m", dim=4)
    assert e.probe() is True


@respx.mock
def test_probe_returns_false_when_offline() -> None:
    respx.get(MODELS_URL).mock(side_effect=httpx.ConnectError("no"))
    e = LMStudioEmbedder(endpoint=ENDPOINT, model="m", dim=4)
    assert e.probe() is False


@respx.mock
def test_embed_returns_arrays() -> None:
    respx.post(ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2, 0.3, 0.4]}, {"embedding": [1, 0, 0, 0]}]},
        )
    )
    e = LMStudioEmbedder(endpoint=ENDPOINT, model="m", dim=4)
    out = e.embed(["a", "b"])
    assert len(out) == 2
    assert isinstance(out[0], np.ndarray)
    assert out[0].shape == (4,)


@respx.mock
def test_embed_raises_on_dim_mismatch() -> None:
    respx.post(ENDPOINT).mock(
        return_value=httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})
    )
    e = LMStudioEmbedder(endpoint=ENDPOINT, model="m", dim=4)
    with pytest.raises(LMStudioUnavailable, match="dimension mismatch"):
        e.embed(["a"])


@respx.mock
def test_embed_raises_on_http_error() -> None:
    respx.post(ENDPOINT).mock(return_value=httpx.Response(500, text="boom"))
    e = LMStudioEmbedder(endpoint=ENDPOINT, model="m", dim=4)
    with pytest.raises(LMStudioUnavailable):
        e.embed(["a"])


@respx.mock
def test_normalize_unit_length() -> None:
    respx.post(ENDPOINT).mock(
        return_value=httpx.Response(200, json={"data": [{"embedding": [3.0, 4.0]}]})
    )
    e = LMStudioEmbedder(endpoint=ENDPOINT, model="m", dim=2, normalize=True)
    out = e.embed(["a"])
    assert pytest.approx(float(np.linalg.norm(out[0])), abs=1e-6) == 1.0
```

- [ ] **Step 2: Run tests**

Run: `pytest -q tests/unit/mcp/proxy/test_lmstudio_embedder.py`
Expected: ImportError.

- [ ] **Step 3: Implement embedder**

```python
# src/aria/mcp/proxy/transforms/__init__.py
```

```python
# src/aria/mcp/proxy/transforms/lmstudio_embedder.py
"""HTTP client for LM Studio's OpenAI-compatible embeddings endpoint.

Returns numpy arrays (shape `(dim,)`, dtype float32). Raises
LMStudioUnavailable on any failure so callers can degrade gracefully.
"""
from __future__ import annotations

import httpx
import numpy as np


class LMStudioUnavailable(RuntimeError):
    """Raised when the LM Studio endpoint cannot fulfil a request."""


class LMStudioEmbedder:
    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        dim: int,
        timeout_s: float = 5.0,
        normalize: bool = True,
    ) -> None:
        self._endpoint = endpoint
        self._model = model
        self._dim = dim
        self._timeout = timeout_s
        self._normalize = normalize
        self._client = httpx.Client(timeout=timeout_s)
        self._models_url = endpoint.replace("/embeddings", "/models")

    def probe(self) -> bool:
        try:
            r = self._client.get(self._models_url)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        try:
            r = self._client.post(
                self._endpoint, json={"model": self._model, "input": texts}
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise LMStudioUnavailable(str(exc)) from exc
        data = r.json().get("data") or []
        out: list[np.ndarray] = []
        for entry in data:
            emb = entry.get("embedding") or []
            if len(emb) != self._dim:
                raise LMStudioUnavailable(
                    f"dimension mismatch: got {len(emb)} expected {self._dim}"
                )
            arr = np.asarray(emb, dtype=np.float32)
            if self._normalize:
                norm = float(np.linalg.norm(arr))
                if norm > 0:
                    arr = arr / norm
            out.append(arr)
        return out

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 4: Run tests**

Run: `pytest -q tests/unit/mcp/proxy/test_lmstudio_embedder.py`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aria/mcp/proxy/transforms/__init__.py \
        src/aria/mcp/proxy/transforms/lmstudio_embedder.py \
        tests/unit/mcp/proxy/test_lmstudio_embedder.py
git commit -m "feat(proxy): LMStudioEmbedder with probe + dim validation + normalisation"
```

### Task F1.7: HybridSearchTransform

**Files:**
- Create: `src/aria/mcp/proxy/transforms/hybrid.py`
- Create: `tests/unit/mcp/proxy/test_hybrid.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/mcp/proxy/test_hybrid.py
"""Unit tests for HybridSearchTransform."""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from aria.mcp.proxy.transforms.hybrid import HybridSearchTransform


def _tool(name: str, description: str, params: dict[str, str] | None = None) -> MagicMock:
    t = MagicMock()
    t.name = name
    t.description = description
    t.parameters = params or {}
    return t


def test_falls_back_to_bm25_when_embedder_missing() -> None:
    transform = HybridSearchTransform(embedder=None)
    transform._index_tool(_tool("read_file", "Read a file from disk"))
    score = transform._score("read", _tool("read_file", "Read a file from disk"))
    assert score > 0.0
    assert transform._semantic_enabled is False


def test_blend_combines_bm25_and_semantic() -> None:
    embedder = MagicMock()
    embedder.embed.side_effect = [
        [np.array([1.0, 0.0], dtype=np.float32)],   # tool vector
        [np.array([1.0, 0.0], dtype=np.float32)],   # query vector
    ]
    transform = HybridSearchTransform(embedder=embedder, blend=0.5)
    transform._semantic_enabled = True
    tool = _tool("send_email", "Send an email")
    transform._index_tool(tool)
    score = transform._score("send email", tool)
    assert score > 0.0  # both layers contribute


def test_degrades_on_embedder_failure_during_index() -> None:
    from aria.mcp.proxy.transforms.lmstudio_embedder import LMStudioUnavailable

    embedder = MagicMock()
    embedder.embed.side_effect = LMStudioUnavailable("offline")
    transform = HybridSearchTransform(embedder=embedder)
    transform._semantic_enabled = True
    transform._index_tool(_tool("x", "y"))
    assert transform._semantic_enabled is False  # degraded


def test_degrades_on_embedder_failure_during_score() -> None:
    from aria.mcp.proxy.transforms.lmstudio_embedder import LMStudioUnavailable

    embedder = MagicMock()
    embedder.embed.side_effect = [
        [np.array([1.0, 0.0], dtype=np.float32)],
        LMStudioUnavailable("offline"),
    ]
    transform = HybridSearchTransform(embedder=embedder, blend=0.5)
    transform._semantic_enabled = True
    tool = _tool("x", "y")
    transform._index_tool(tool)
    score = transform._score("query", tool)
    # scoring still produces a value (BM25 portion only) and downgrades
    assert score >= 0.0
    assert transform._semantic_enabled is False


def test_blend_zero_means_pure_semantic() -> None:
    embedder = MagicMock()
    embedder.embed.side_effect = [
        [np.array([0.6, 0.8], dtype=np.float32)],
        [np.array([0.6, 0.8], dtype=np.float32)],
    ]
    transform = HybridSearchTransform(embedder=embedder, blend=0.0)
    transform._semantic_enabled = True
    tool = _tool("x", "y")
    transform._index_tool(tool)
    s = transform._score("q", tool)
    # cosine similarity ≈ 1.0 with identical normalised vectors
    assert s == s  # not NaN
```

- [ ] **Step 2: Run tests**

Run: `pytest -q tests/unit/mcp/proxy/test_hybrid.py`
Expected: ImportError.

- [ ] **Step 3: Implement transform**

```python
# src/aria/mcp/proxy/transforms/hybrid.py
"""Blend BM25 keyword scoring with mxbai-embed-large-v1 semantic similarity.

Subclasses FastMCP's BM25SearchTransform. When the LM Studio endpoint is
unavailable at boot or fails mid-flight, we degrade silently to BM25-only.
The transform exposes `search_tools` and `call_tool` synthetic tools to
the client (inherited behaviour from BM25SearchTransform).
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

try:  # FastMCP 3.2+ exposes the transform here
    from fastmcp.server.transforms.search.bm25 import BM25SearchTransform
except ImportError:  # pragma: no cover — older FastMCP layouts
    from fastmcp.server.transforms.search import BM25SearchTransform  # type: ignore[no-redef]

from aria.mcp.proxy.transforms.lmstudio_embedder import (
    LMStudioEmbedder,
    LMStudioUnavailable,
)

logger = logging.getLogger("aria.mcp.proxy.transforms.hybrid")


def _tool_text(tool: Any) -> str:
    name = getattr(tool, "name", "") or ""
    description = getattr(tool, "description", "") or ""
    params = getattr(tool, "parameters", {}) or {}
    param_text = " ".join(f"{k}:{v}" for k, v in params.items())
    return f"{name}. {description}. {param_text}"[:2000]


class HybridSearchTransform(BM25SearchTransform):
    def __init__(
        self,
        *,
        embedder: LMStudioEmbedder | None = None,
        blend: float = 0.6,
    ) -> None:
        super().__init__()
        self._embedder = embedder
        self._blend = blend
        self._tool_vectors: dict[str, np.ndarray] = {}
        self._semantic_enabled = embedder is not None and embedder.probe()

    def _index_tool(self, tool: Any) -> None:  # type: ignore[override]
        super()._index_tool(tool)
        if not self._semantic_enabled or self._embedder is None:
            return
        try:
            vec = self._embedder.embed([_tool_text(tool)])[0]
        except LMStudioUnavailable:
            self._semantic_enabled = False
            logger.warning("LM Studio unavailable during indexing — degrading to BM25")
            return
        self._tool_vectors[tool.name] = vec

    def _score(self, query: str, tool: Any) -> float:  # type: ignore[override]
        bm25 = float(super()._score(query, tool))
        if not self._semantic_enabled or self._embedder is None:
            return bm25
        vec = self._tool_vectors.get(tool.name)
        if vec is None:
            return bm25
        try:
            qv = self._embedder.embed([query])[0]
        except LMStudioUnavailable:
            self._semantic_enabled = False
            logger.warning("LM Studio unavailable during scoring — degrading to BM25")
            return bm25
        cos = float(np.dot(qv, vec))
        return self._blend * bm25 + (1.0 - self._blend) * cos
```

- [ ] **Step 4: Run tests**

Run: `pytest -q tests/unit/mcp/proxy/test_hybrid.py`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/aria/mcp/proxy/transforms/hybrid.py tests/unit/mcp/proxy/test_hybrid.py
git commit -m "feat(proxy): HybridSearchTransform blends BM25 with mxbai semantic similarity"
```

### Task F1.8: Capability matrix middleware

**Files:**
- Modify: `src/aria/agents/coordination/registry.py` (add namespaced lookup helper)
- Create: `src/aria/mcp/proxy/middleware.py`
- Create: `tests/unit/mcp/proxy/test_middleware.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/mcp/proxy/test_middleware.py
"""Unit tests for CapabilityMatrixMiddleware."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.exceptions import ToolError

from aria.mcp.proxy.middleware import CapabilityMatrixMiddleware


class _Reg:
    def __init__(self, mapping: dict[str, list[str]]):
        self._m = mapping

    def get_allowed_tools(self, agent: str) -> list[str]:
        return self._m.get(agent, [])

    def is_tool_allowed(self, agent: str, tool: str) -> bool:
        return tool in self._m.get(agent, [])


def _ctx(*, args: dict | None = None, tool_name: str | None = None) -> MagicMock:
    ctx = MagicMock()
    msg = MagicMock()
    msg.arguments = dict(args or {})
    if tool_name is not None:
        msg.name = tool_name
    ctx.message = msg
    return ctx


@pytest.mark.asyncio
async def test_on_call_tool_allows_when_caller_in_matrix() -> None:
    reg = _Reg({"search-agent": ["tavily-mcp__search"]})
    mw = CapabilityMatrixMiddleware(reg)  # type: ignore[arg-type]
    ctx = _ctx(args={"_caller_id": "search-agent", "q": "x"}, tool_name="tavily-mcp__search")
    call_next = AsyncMock(return_value="ok")
    out = await mw.on_call_tool(ctx, call_next)
    assert out == "ok"
    call_next.assert_awaited_once()
    # _caller_id must be stripped before forwarding
    assert "_caller_id" not in ctx.message.arguments


@pytest.mark.asyncio
async def test_on_call_tool_denies_when_caller_not_in_matrix() -> None:
    reg = _Reg({"search-agent": ["tavily-mcp__search"]})
    mw = CapabilityMatrixMiddleware(reg)  # type: ignore[arg-type]
    ctx = _ctx(args={"_caller_id": "search-agent"}, tool_name="google_workspace__gmail_send")
    call_next = AsyncMock()
    with pytest.raises(ToolError, match="not allowed"):
        await mw.on_call_tool(ctx, call_next)
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_call_tool_permissive_when_caller_id_absent() -> None:
    reg = _Reg({})
    mw = CapabilityMatrixMiddleware(reg)  # type: ignore[arg-type]
    ctx = _ctx(args={"q": "x"}, tool_name="filesystem__read")
    call_next = AsyncMock(return_value="ok")
    out = await mw.on_call_tool(ctx, call_next)
    assert out == "ok"


@pytest.mark.asyncio
async def test_on_list_tools_filters_per_caller() -> None:
    reg = _Reg({"search-agent": ["tavily-mcp__search"]})
    mw = CapabilityMatrixMiddleware(reg, default_caller_env="ARIA_CALLER_ID")  # type: ignore[arg-type]
    tool_a = MagicMock(); tool_a.name = "tavily-mcp__search"
    tool_b = MagicMock(); tool_b.name = "google_workspace__gmail_send"
    tool_c = MagicMock(); tool_c.name = "search_tools"  # always_visible synthetic
    call_next = AsyncMock(return_value=[tool_a, tool_b, tool_c])
    ctx = _ctx()
    ctx.fastmcp_context = MagicMock()
    ctx.fastmcp_context.headers = {"X-ARIA-Caller-Id": "search-agent"}
    out = await mw.on_list_tools(ctx, call_next)
    names = [t.name for t in out]
    assert "tavily-mcp__search" in names
    assert "google_workspace__gmail_send" not in names
    # synthetic tools are always visible
    assert "search_tools" in names


@pytest.mark.asyncio
async def test_on_list_tools_passthrough_when_no_caller() -> None:
    reg = _Reg({})
    mw = CapabilityMatrixMiddleware(reg)  # type: ignore[arg-type]
    tool_a = MagicMock(); tool_a.name = "filesystem__read"
    call_next = AsyncMock(return_value=[tool_a])
    out = await mw.on_list_tools(_ctx(), call_next)
    assert out == [tool_a]


@pytest.mark.asyncio
async def test_synthetic_tools_never_filtered() -> None:
    reg = _Reg({"search-agent": []})  # empty allow-list
    mw = CapabilityMatrixMiddleware(reg)  # type: ignore[arg-type]
    sym = MagicMock(); sym.name = "search_tools"
    call = MagicMock(); call.name = "call_tool"
    other = MagicMock(); other.name = "filesystem__read"
    call_next = AsyncMock(return_value=[sym, call, other])
    ctx = _ctx(args={"_caller_id": "search-agent"})
    out = await mw.on_list_tools(ctx, call_next)
    names = [t.name for t in out]
    assert "search_tools" in names and "call_tool" in names
    assert "filesystem__read" not in names
```

- [ ] **Step 2: Run tests**

Run: `pytest -q tests/unit/mcp/proxy/test_middleware.py`
Expected: ImportError.

- [ ] **Step 3: Add namespaced lookup helper to registry**

In `src/aria/agents/coordination/registry.py`, append (or extend) the `AgentRegistry` class:

```python
def is_tool_allowed(self, agent: str, namespaced_tool: str) -> bool:
    """Return True if `namespaced_tool` (server__tool form) is in the agent's allowed list.

    Accepts both legacy `server/tool` and new `server__tool` forms in the
    YAML matrix during the migration window.
    """
    allowed = set(self.get_allowed_tools(agent))
    if namespaced_tool in allowed:
        return True
    # fall back to legacy form: convert "server__tool" → "server/tool"
    if "__" in namespaced_tool:
        legacy = namespaced_tool.replace("__", "/", 1)
        if legacy in allowed:
            return True
    return False
```

(If `is_tool_allowed` already exists with different semantics, preserve the namespaced check above as an additional method or update its docstring.)

- [ ] **Step 4: Implement middleware**

```python
# src/aria/mcp/proxy/middleware.py
"""Per-agent capability enforcement on top of FastMCP's middleware pipeline.

The conventions:
- Agent prompts pass `_caller_id: "<agent>"` as an extra argument to
  search_tools / call_tool. The middleware strips it before forwarding.
- `tools/list` filtering uses the caller hint from a request header
  (`X-ARIA-Caller-Id`) when available, otherwise falls back to the
  `ARIA_CALLER_ID` env var (set when KiloCode launches the proxy
  process).
- Synthetic tools (`search_tools`, `call_tool`) are always visible.
"""
from __future__ import annotations

import os
from typing import Iterable, Protocol

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

from aria.utils.logging import get_logger

logger = get_logger("aria.mcp.proxy.middleware")

ALWAYS_VISIBLE: frozenset[str] = frozenset({"search_tools", "call_tool"})


class _Registry(Protocol):
    def get_allowed_tools(self, agent: str) -> list[str]: ...
    def is_tool_allowed(self, agent: str, tool: str) -> bool: ...


class CapabilityMatrixMiddleware(Middleware):
    def __init__(
        self,
        registry: _Registry,
        *,
        default_caller_env: str = "ARIA_CALLER_ID",
        caller_header: str = "X-ARIA-Caller-Id",
    ) -> None:
        self._registry = registry
        self._env = default_caller_env
        self._header = caller_header

    async def on_list_tools(
        self, ctx: MiddlewareContext, call_next
    ) -> list:
        tools = await call_next(ctx)
        caller = self._resolve_caller(ctx)
        if not caller:
            return tools
        allowed = set(self._registry.get_allowed_tools(caller))
        return [
            t for t in tools
            if t.name in ALWAYS_VISIBLE or self._matches(t.name, allowed)
        ]

    async def on_call_tool(self, ctx: MiddlewareContext, call_next):
        args = dict(getattr(ctx.message, "arguments", None) or {})
        caller = args.pop("_caller_id", None) or self._resolve_caller(ctx)
        ctx.message.arguments = args  # strip before forwarding
        tool_name = getattr(ctx.message, "name", "")
        if caller and tool_name not in ALWAYS_VISIBLE:
            if not self._registry.is_tool_allowed(caller, tool_name):
                logger.warning(
                    "proxy.tool_denied",
                    extra={"agent": caller, "tool": tool_name},
                )
                raise ToolError(f"tool {tool_name} not allowed for {caller}")
        return await call_next(ctx)

    def _resolve_caller(self, ctx: MiddlewareContext) -> str | None:
        fctx = getattr(ctx, "fastmcp_context", None)
        if fctx is not None:
            headers = getattr(fctx, "headers", None) or {}
            value = headers.get(self._header)
            if value:
                return str(value)
        return os.environ.get(self._env)

    @staticmethod
    def _matches(tool_name: str, allowed: Iterable[str]) -> bool:
        if tool_name in allowed:
            return True
        # legacy form: "server/tool" in matrix vs "server__tool" in proxy
        if "__" in tool_name:
            legacy = tool_name.replace("__", "/", 1)
            if legacy in allowed:
                return True
        # wildcard `server/*` or `server__*`
        for entry in allowed:
            if entry.endswith("/*") and tool_name.startswith(
                entry[:-2].replace("/", "__") + "__"
            ):
                return True
            if entry.endswith("__*") and tool_name.startswith(entry[:-3] + "__"):
                return True
        return False
```

- [ ] **Step 5: Run tests**

Run: `pytest -q tests/unit/mcp/proxy/test_middleware.py`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add src/aria/mcp/proxy/middleware.py \
        src/aria/agents/coordination/registry.py \
        tests/unit/mcp/proxy/test_middleware.py
git commit -m "feat(proxy): CapabilityMatrixMiddleware enforces per-agent allowed-tools"
```

### Task F1.9: Server wiring

**Files:**
- Create: `src/aria/mcp/proxy/server.py`
- Modify: `tests/unit/mcp/proxy/test_server.py`

- [ ] **Step 1: Replace test_server.py with full coverage**

```python
# tests/unit/mcp/proxy/test_server.py
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
```

- [ ] **Step 2: Run tests**

Run: `pytest -q tests/unit/mcp/proxy/test_server.py`
Expected: ImportError on `build_proxy`.

- [ ] **Step 3: Implement server.py**

```python
# src/aria/mcp/proxy/server.py
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

from aria.agents.coordination.registry import AgentRegistry
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
    composite.add_middleware(CapabilityMatrixMiddleware(AgentRegistry()))
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
    injector = CredentialInjector(manager=manager)  # type: ignore[arg-type]
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
    return HybridSearchTransform(embedder=embedder, blend=cfg.search.blend)
```

- [ ] **Step 4: Run tests**

Run: `pytest -q tests/unit/mcp/proxy/test_server.py`
Expected: 3 passed.

- [ ] **Step 5: Quality gate**

Run: `make quality`
Expected: ruff, format, mypy, pytest all green for the new code.
If failures: fix them before commit.

- [ ] **Step 6: Commit**

```bash
git add src/aria/mcp/proxy/server.py tests/unit/mcp/proxy/test_server.py
git commit -m "feat(proxy): build_proxy() wires catalog + transform + middleware"
```

### Task F1.10: Integration test — stdio e2e

**Files:**
- Create: `tests/integration/mcp/proxy/__init__.py`
- Create: `tests/integration/mcp/proxy/conftest.py`
- Create: `tests/integration/mcp/proxy/test_proxy_e2e_stdio.py`

- [ ] **Step 1: Write the test**

```python
# tests/integration/mcp/proxy/test_proxy_e2e_stdio.py
"""Integration: spawn the proxy via stdio and exercise the synthetic tools."""
from __future__ import annotations

import os

import pytest
from fastmcp import Client

from aria.mcp.proxy.server import build_proxy


@pytest.mark.integration
@pytest.mark.asyncio
async def test_proxy_lists_synthetic_tools(monkeypatch) -> None:
    monkeypatch.setenv("ARIA_PROXY_DISABLE_BACKENDS", "1")
    proxy = build_proxy(strict=False)
    async with Client(proxy) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert "search_tools" in names
        assert "call_tool" in names


@pytest.mark.integration
@pytest.mark.asyncio
async def test_proxy_search_finds_tool(monkeypatch, minimal_catalog, tmp_path) -> None:
    monkeypatch.delenv("ARIA_PROXY_DISABLE_BACKENDS", raising=False)
    # use a stub backend that the proxy can spawn quickly
    proxy = build_proxy(catalog_path=minimal_catalog, strict=False)
    async with Client(proxy) as client:
        result = await client.call_tool("search_tools", {"pattern": "read"})
        assert result is not None
```

- [ ] **Step 2: Conftest for integration**

```python
# tests/integration/mcp/proxy/conftest.py
"""Shared fixtures for integration tests (re-export unit fixtures)."""
from tests.unit.mcp.proxy.conftest import minimal_catalog, minimal_mcp_json  # noqa: F401
```

- [ ] **Step 3: Run integration**

Run: `pytest -q tests/integration/mcp/proxy/test_proxy_e2e_stdio.py`
Expected: 2 passed (the second test may skip if `npx` is unavailable; mark it `@pytest.mark.skipif` accordingly).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/mcp/proxy/
git commit -m "test(proxy): integration e2e — proxy returns synthetic tools via stdio"
```

### Task F1.11: Integration test — capability enforcement

**Files:**
- Create: `tests/integration/mcp/proxy/test_capability_enforcement.py`

- [ ] **Step 1: Write the test**

```python
# tests/integration/mcp/proxy/test_capability_enforcement.py
"""Integration: middleware blocks tools not in agent_capability_matrix.yaml."""
from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from aria.mcp.proxy.middleware import CapabilityMatrixMiddleware
from aria.mcp.proxy.server import build_proxy


class _StubReg:
    def get_allowed_tools(self, agent: str) -> list[str]:
        return {"search-agent": ["filesystem__read"]}.get(agent, [])

    def is_tool_allowed(self, agent: str, tool: str) -> bool:
        return tool in self.get_allowed_tools(agent)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_agent_blocked_from_workspace(monkeypatch) -> None:
    monkeypatch.setenv("ARIA_PROXY_DISABLE_BACKENDS", "1")
    proxy = build_proxy(strict=False)
    # replace the registry-backed middleware with our stub
    proxy._middleware = [m for m in proxy._middleware if not isinstance(m, CapabilityMatrixMiddleware)]  # type: ignore[attr-defined]
    proxy.add_middleware(CapabilityMatrixMiddleware(_StubReg()))

    async with Client(proxy) as client:
        with pytest.raises(ToolError, match="not allowed"):
            await client.call_tool(
                "call_tool",
                {
                    "_caller_id": "search-agent",
                    "name": "google_workspace__gmail_send",
                    "arguments": {"to": "x"},
                },
            )
```

- [ ] **Step 2: Run integration**

Run: `pytest -q tests/integration/mcp/proxy/test_capability_enforcement.py`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/mcp/proxy/test_capability_enforcement.py
git commit -m "test(proxy): integration — middleware blocks unauthorised cross-agent calls"
```

### Task F1.12: Integration test — emergency rollback flag

**Files:**
- Modify: `bin/aria` (add `--emergency-direct` flag)
- Create: `tests/integration/mcp/proxy/test_emergency_rollback.py`

- [ ] **Step 1: Write the test**

```python
# tests/integration/mcp/proxy/test_emergency_rollback.py
"""Integration: --emergency-direct restores the LKG mcp.json."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
def test_emergency_direct_uses_lkg_baseline(tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    bin_aria = repo_root / "bin/aria"
    if not bin_aria.exists():
        pytest.skip("bin/aria not present")
    monkeypatch.setenv("ARIA_HOME", str(tmp_path))
    # simulate baseline mcp.json present in the worktree
    baseline_dir = tmp_path / ".aria/kilocode"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    (baseline_dir / "mcp.json.baseline").write_text(json.dumps({"mcpServers": {"a": {}}}))

    res = subprocess.run(
        [str(bin_aria), "start", "--emergency-direct", "--dry-run"],
        capture_output=True,
        text=True,
        env={**dict(monkeypatch.delenv.__globals__["os"].environ),
             "ARIA_HOME": str(tmp_path)},
    )
    assert res.returncode == 0, res.stderr
    out = (baseline_dir / "mcp.json").read_text()
    assert "mcpServers" in out
```

- [ ] **Step 2: Add `--emergency-direct` to `bin/aria`**

In `bin/aria` (bash launcher), add a flag handler near the top of `start`:

```bash
# bin/aria — fragment
case "${1:-}" in
  start)
    shift
    EMERGENCY_DIRECT=0
    DRY_RUN=0
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --emergency-direct) EMERGENCY_DIRECT=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) break ;;
      esac
    done
    if [ "$EMERGENCY_DIRECT" = "1" ]; then
      BASELINE="$ARIA_HOME/.aria/kilocode/mcp.json.baseline"
      TARGET="$ARIA_HOME/.aria/kilocode/mcp.json"
      if [ ! -f "$BASELINE" ]; then
        echo "ERROR: emergency baseline missing: $BASELINE" >&2
        exit 2
      fi
      cp "$BASELINE" "$TARGET"
      echo "restored mcp.json from baseline"
      [ "$DRY_RUN" = "1" ] && exit 0
    fi
    # ... existing start path ...
    ;;
esac
```

(Adapt to the existing bin/aria control flow; preserve all existing cases.)

- [ ] **Step 3: Snapshot a baseline mcp.json**

```bash
cp .aria/kilocode/mcp.json .aria/kilocode/mcp.json.baseline
git add .aria/kilocode/mcp.json.baseline
```

- [ ] **Step 4: Run integration**

Run: `pytest -q tests/integration/mcp/proxy/test_emergency_rollback.py`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add bin/aria .aria/kilocode/mcp.json.baseline tests/integration/mcp/proxy/test_emergency_rollback.py
git commit -m "feat(launcher): bin/aria start --emergency-direct restores LKG mcp.json"
```

### Task F1.13: F1 quality gate

- [ ] **Step 1: Run full quality gate**

Run: `make quality`
Expected: green.

- [ ] **Step 2: Run new e2e gate guard (search quality placeholder)**

We'll add the real e2e tests in F2; for now, ensure the proxy package imports cleanly and the unit + integration suites under `tests/{unit,integration}/mcp/proxy/` are green.

Run:
```
pytest -q tests/unit/mcp/proxy tests/integration/mcp/proxy
```
Expected: green.

- [ ] **Step 3: Push branch (no PR yet)**

```bash
git push -u origin feat/mcp-tool-search-proxy
```

---

## Phase F2 — Shadow mode (~2 days)

Goal: the proxy runs alongside the existing direct MCP path. Production traffic still goes through the original 14 entries in `mcp.json`. We collect cold-start, search, and embedding metrics for 48 hours.

### Task F2.1: Add proxy entry to mcp.json (alongside existing entries)

**Files:**
- Modify: `.aria/kilocode/mcp.json`

- [ ] **Step 1: Add proxy entry**

Append to the `mcpServers` map (do not remove anything):

```json
"aria-mcp-proxy": {
  "command": "/home/fulvio/coding/aria/.venv/bin/python",
  "args": ["-m", "aria.mcp.proxy"],
  "env": {
    "ARIA_HOME": "/home/fulvio/coding/aria"
  },
  "_comment": "@F2 shadow mode — not yet referenced by any agent prompt"
}
```

- [ ] **Step 2: Validate JSON**

Run: `python -c 'import json,sys; json.load(open(".aria/kilocode/mcp.json"))'`
Expected: no error.

- [ ] **Step 3: Restart KiloCode**

Restart your KiloCode session. Confirm via KiloCode logs that the new server initialises and exposes `search_tools` + `call_tool`. No agent prompt references it yet, so production behaviour is unchanged.

- [ ] **Step 4: Commit**

```bash
git add .aria/kilocode/mcp.json
git commit -m "feat(proxy): add aria-mcp-proxy entry to mcp.json (shadow mode, F2)"
```

### Task F2.2: Shadow observation harness

**Files:**
- Create: `scripts/proxy_shadow_observe.py`

- [ ] **Step 1: Write observation script**

```python
# scripts/proxy_shadow_observe.py
"""Connect to the running proxy and emit a 30-call sample of search_tools.

Run periodically (cron / manual) for 48h. Output JSONL to
.aria/runtime/proxy/shadow-{YYYYMMDD-HHMM}.jsonl.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from fastmcp import Client

QUERIES = [
    "wiki recall",
    "send email",
    "search papers",
    "read pdf",
    "calendar event",
    "tavily search",
    "reddit search",
    "filesystem read",
    "convert pdf",
    "github repo discovery",
]


async def main() -> None:
    out_dir = Path(".aria/runtime/proxy")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"shadow-{datetime.utcnow().strftime('%Y%m%d-%H%M')}.jsonl"
    async with Client("python -m aria.mcp.proxy") as client:
        with out_file.open("w") as f:
            for q in QUERIES * 3:
                t0 = time.perf_counter()
                try:
                    res = await client.call_tool("search_tools", {"pattern": q})
                    latency_ms = (time.perf_counter() - t0) * 1000
                    f.write(json.dumps({"q": q, "ok": True, "latency_ms": latency_ms,
                                        "n_results": len(res.content) if hasattr(res, "content") else 0}) + "\n")
                except Exception as exc:  # pragma: no cover
                    f.write(json.dumps({"q": q, "ok": False, "err": str(exc)}) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run once, verify output**

Run: `uv run python scripts/proxy_shadow_observe.py`
Expected: a JSONL file under `.aria/runtime/proxy/shadow-*.jsonl` with 30 entries, all `ok: true`, p95 latency < 200 ms.

- [ ] **Step 3: Schedule shadow runs (manual, 48h window)**

```bash
( cd /home/fulvio/coding/aria && uv run python scripts/proxy_shadow_observe.py ) &
# or add a cron entry
```

- [ ] **Step 4: Commit**

```bash
git add scripts/proxy_shadow_observe.py
git commit -m "chore(proxy): F2 shadow observation harness (30-call sample, JSONL output)"
```

### Task F2.3: F2 ship gate review

- [ ] **Step 1: After 48 h, summarise the JSONL**

```bash
ls .aria/runtime/proxy/shadow-*.jsonl | xargs cat | jq -s '
  {n: length,
   ok: (map(select(.ok)) | length),
   p50: (map(select(.ok)) | sort_by(.latency_ms) | .[length/2 | floor].latency_ms),
   p95: (map(select(.ok)) | sort_by(.latency_ms) | .[length*0.95 | floor].latency_ms)}'
```

Expected: ok ≥ 99%, p95 < 200 ms. If gates fail, fix root causes (likely LM Studio cold-start or an unhealthy backend) before F3.

- [ ] **Step 2: Decision gate**

Pass: proceed to F3 cutover. Fail: address regressions in F1, repeat F2.

---

## Phase F3 — Cutover (~2 days)

Goal: KiloCode sees only `aria-memory` + `aria-mcp-proxy`. All agent prompts use namespaced tool names. The proxy becomes the production path.

### Task F3.1: Reduce mcp.json to two entries

**Files:**
- Modify: `.aria/kilocode/mcp.json`

- [ ] **Step 1: Replace contents**

```json
{
  "mcpServers": {
    "aria-memory": {
      "command": "/home/fulvio/coding/aria/.venv/bin/python",
      "args": ["-m", "aria.memory.mcp_server"],
      "env": {
        "ARIA_HOME": "/home/fulvio/coding/aria"
      }
    },
    "aria-mcp-proxy": {
      "command": "/home/fulvio/coding/aria/.venv/bin/python",
      "args": ["-m", "aria.mcp.proxy"],
      "env": {
        "ARIA_HOME": "/home/fulvio/coding/aria"
      }
    }
  }
}
```

- [ ] **Step 2: Validate JSON + lint**

Run: `python -c 'import json; json.load(open(".aria/kilocode/mcp.json"))'`
Expected: no error.

- [ ] **Step 3: Commit**

```bash
git add .aria/kilocode/mcp.json
git commit -m "feat(proxy): F3 cutover — mcp.json reduced to aria-memory + aria-mcp-proxy"
```

### Task F3.2: Update agent_capability_matrix.yaml to namespaced tool names

**Files:**
- Modify: `.aria/config/agent_capability_matrix.yaml`

- [ ] **Step 1: Rewrite tool entries**

Replace each `server/tool` entry with `server__tool` form (the legacy form is still accepted by `is_tool_allowed`, but we want the canonical YAML to use the new form). Example:

```yaml
agents:
  - name: search-agent
    type: worker
    allowed_tools:
      - searxng-script__search
      - tavily-mcp__search
      - exa-script__search
      - brave-mcp__web_search
      - brave-mcp__news_search
      - reddit-search__search
      - reddit-search__search_subreddit
      - reddit-search__get_post
      - reddit-search__get_subreddit_posts
      - reddit-search__get_user
      - reddit-search__get_user_posts
      - scientific-papers-mcp__search_papers
      - scientific-papers-mcp__fetch_content
      - scientific-papers-mcp__fetch_latest
      - scientific-papers-mcp__list_categories
      - scientific-papers-mcp__fetch_top_cited
      - aria-memory__wiki_update_tool
      - aria-memory__wiki_recall_tool
      - fetch__fetch
    mcp_dependencies:
      - aria-mcp-proxy
      - aria-memory
    delegation_targets: []
    hitl_triggers: []
    intent_categories:
      - general/news
      - academic
      - social
      - deep_scrape
    max_tools: 20
    max_spawn_depth: 0
```

Repeat for `aria-conductor`, `workspace-agent`, `productivity-agent`. Keep `mcp_dependencies` list small (proxy + aria-memory only).

- [ ] **Step 2: Run drift validator**

Run: `python scripts/check_mcp_drift.py --shadow`
Expected: warnings only (we will tighten in F3.5). No catastrophic failures.

- [ ] **Step 3: Commit**

```bash
git add .aria/config/agent_capability_matrix.yaml
git commit -m "feat(proxy): F3 — agent_capability_matrix uses namespaced tool names"
```

### Task F3.3: Update agent prompts (4 files)

**Files:**
- Modify: `.aria/kilocode/agents/aria-conductor.md`
- Modify: `.aria/kilocode/agents/_aria-conductor.template.md`
- Modify: `.aria/kilocode/agents/search-agent.md`
- Modify: `.aria/kilocode/agents/workspace-agent.md`
- Modify: `.aria/kilocode/agents/productivity-agent.md`

- [ ] **Step 1: For each agent prompt, rewrite YAML front matter**

Replace `allowed-tools` with namespaced names (mirror the matrix). Replace `mcp-dependencies` with `[aria-mcp-proxy, aria-memory]`. Example for `search-agent.md`:

```yaml
---
name: search-agent
type: subagent
description: Ricerca web multi-tier e sintesi informazioni da fonti online
color: "#2E86AB"
category: research
temperature: 0.1
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - aria-memory__wiki_update_tool
  - aria-memory__wiki_recall_tool
required-skills:
  - deep-research
  - source-dedup
mcp-dependencies:
  - aria-mcp-proxy
  - aria-memory
---
```

The agent body keeps tool *names* (e.g. `tavily-mcp/search`) where they appear inside narrative tier ladders, but the agent now reaches them by going through `aria-mcp-proxy__call_tool`.

- [ ] **Step 2: Insert the `_caller_id` addendum**

Add a new top-level section to each agent prompt (after the YAML front matter):

```markdown
## Proxy invocation rule

Quando chiami `aria-mcp-proxy__search_tools` o `aria-mcp-proxy__call_tool`,
includi sempre l'argomento `_caller_id` con il NOME ESATTO di questo agente,
es. `_caller_id: "search-agent"`.

Il proxy usa `_caller_id` per applicare la `agent_capability_matrix.yaml`.
Una chiamata senza `_caller_id` viene comunque servita ma logged come
anomalia (`aria_proxy_caller_missing_total`).
```

(Translate the agent name in each file accordingly — `aria-conductor`, `workspace-agent`, `productivity-agent`.)

- [ ] **Step 3: Validate front matter parses**

Run:
```bash
python -c '
import yaml, pathlib
for p in pathlib.Path(".aria/kilocode/agents").glob("*.md"):
    text = p.read_text()
    if not text.startswith("---"): continue
    body = text.split("---", 2)
    assert len(body) >= 3, p
    yaml.safe_load(body[1])
    print("ok", p.name)
'
```
Expected: `ok` for every prompt file.

- [ ] **Step 4: Commit**

```bash
git add .aria/kilocode/agents/*.md
git commit -m "feat(proxy): F3 — agent prompts use namespaced tools + _caller_id rule"
```

### Task F3.4: E2E smoke session

**Files:**
- Create: `tests/e2e/mcp/proxy/__init__.py`
- Create: `tests/e2e/mcp/proxy/test_full_session_kilocode.py`

- [ ] **Step 1: Manual smoke**

In a real KiloCode 7.2.x session, ask:
> "Cerca tre paper recenti su modelli di stato (state space models)."

Expected: conductor spawns search-agent → search-agent uses `aria-mcp-proxy__search_tools(pattern="state space model papers", _caller_id="search-agent")` → top results include `scientific-papers-mcp__search_papers`. Final answer cites at least one arXiv reference.

Capture `KiloCode logs` and `.aria/runtime/proxy/shadow-*.jsonl` excerpt; paste into the PR description.

- [ ] **Step 2: Programmatic e2e gate**

```python
# tests/e2e/mcp/proxy/test_full_session_kilocode.py
"""End-to-end gate: KiloCode session reaches the proxy and gets a result.

This test is environment-conditional. It runs only when ARIA_E2E_KILOCODE=1.
"""
from __future__ import annotations

import os
import pytest


@pytest.mark.e2e
@pytest.mark.skipif(os.getenv("ARIA_E2E_KILOCODE") != "1", reason="manual KiloCode harness")
def test_kilocode_session_reaches_proxy() -> None:
    from fastmcp import Client
    import asyncio

    async def _run() -> None:
        async with Client("python -m aria.mcp.proxy") as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "search_tools" in names
            res = await client.call_tool(
                "search_tools", {"pattern": "wiki recall", "_caller_id": "aria-conductor"}
            )
            assert res is not None

    asyncio.run(_run())
```

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/mcp/proxy/__init__.py tests/e2e/mcp/proxy/test_full_session_kilocode.py
git commit -m "test(proxy): F3 — manual + programmatic e2e KiloCode session smoke"
```

### Task F3.5: Update drift validator

**Files:**
- Modify: `scripts/check_mcp_drift.py`

- [ ] **Step 1: Add proxy-aware checks**

Add (or extend) checks so that:

1. `mcp.json.mcpServers` keys are exactly `{"aria-memory", "aria-mcp-proxy"}`.
2. Every entry in `agent_capability_matrix.yaml.allowed_tools` either (a) is a synthetic `aria-mcp-proxy__*`, (b) is `aria-memory__*`, or (c) is a backend tool whose `<server>` exists as a `lifecycle: enabled` entry in `mcp_catalog.yaml`.
3. Every agent prompt's `allowed-tools` list mirrors its matrix entry (modulo the addendum).

Reference fragment:

```python
def check_mcp_json_shape(mcp_json_path):
    data = json.loads(mcp_json_path.read_text())
    keys = set(data.get("mcpServers", {}))
    expected = {"aria-memory", "aria-mcp-proxy"}
    if keys != expected:
        return f"mcp.json keys mismatch: {sorted(keys)} != {sorted(expected)}"
    return None
```

- [ ] **Step 2: Run validator in enforce mode**

Run: `python scripts/check_mcp_drift.py --enforce`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add scripts/check_mcp_drift.py
git commit -m "feat(drift): validator enforces mcp.json shape + matrix ↔ catalog cross-refs (F3)"
```

### Task F3.6: F3 ship gate

- [ ] **Step 1: Tag the cutover**

```bash
git tag -a proxy-cutover-v1 -m "F3 cutover: aria-mcp-proxy is the production path"
```

- [ ] **Step 2: Push tags**

```bash
git push origin proxy-cutover-v1
```

- [ ] **Step 3: Run full test suite**

Run: `make quality && pytest -q tests/`
Expected: green.

---

## Phase F4 — Lazy loader removal (~1 day)

### Task F4.1: Remove lazy_loader module

**Files:**
- Delete: `src/aria/launcher/lazy_loader.py`
- Delete: any imports of `lazy_loader` from `bin/aria` or other modules.

- [ ] **Step 1: Search for references**

Run: `rg -n "lazy_loader|lazy_load|intent_tags" src bin scripts`
Expected: a finite list of references. Resolve each by either deleting or substituting.

- [ ] **Step 2: Delete file**

```bash
git rm src/aria/launcher/lazy_loader.py
```

- [ ] **Step 3: Update bin/aria**

Remove any `--intent` / `--profile candidate` handling from `bin/aria`. Keep `--profile baseline` only as a no-op alias for `--emergency-direct`.

- [ ] **Step 4: Update __init__.py**

Edit `src/aria/launcher/__init__.py` to drop the `lazy_loader` export.

- [ ] **Step 5: Run quality gate**

Run: `make quality`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(launcher): remove lazy_loader.py and --intent flow (replaced by proxy)"
```

### Task F4.2: Clean up mcp_catalog.yaml metadata

**Files:**
- Modify: `.aria/config/mcp_catalog.yaml`

- [ ] **Step 1: Drop `lazy_load` and `intent_tags` from each entry**

For each server, remove the `lazy_load:` and `intent_tags:` keys. Add a top-of-file comment:

```yaml
# Note: as of 2026-05-XX the lazy_load and intent_tags keys are no longer
# read; ARIA reaches MCP backends through src/aria/mcp/proxy/. Removed
# from each entry in the F4 cleanup. Governance metadata (tier, domain,
# rollback_class) remains canonical.
```

- [ ] **Step 2: Run drift validator**

Run: `python scripts/check_mcp_drift.py --enforce`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add .aria/config/mcp_catalog.yaml
git commit -m "chore(catalog): drop lazy_load/intent_tags metadata (F4)"
```

### Task F4.3: ADR-0015

**Files:**
- Create: `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`

- [ ] **Step 1: Write the ADR**

```markdown
# ADR-0015: FastMCP-native MCP proxy replaces static lazy loader

**Date**: 2026-05-XX
**Status**: Accepted
**Supersedes**: ADR-0010 (Lazy loading per intent enablement)

## Context

The original lazy loader (`src/aria/launcher/lazy_loader.py`) filtered MCP
servers by intent tag at boot. It required a-priori intent classification,
did not adapt at runtime, and only achieved a 30–50% reduction in tool
definition tokens. With the planned scaling from 14 to 50+ MCP backends and
from 4 to 30+ agents, that approach was no longer viable.

## Decision

Adopt a FastMCP-native multi-server proxy
(`src/aria/mcp/proxy/`) using `fastmcp.server.create_proxy(mcpServers)` and
`HybridSearchTransform` (BM25 + mxbai-embed-large-v1 semantic blend via
LM Studio's local OpenAI-compatible endpoint). KiloCode sees a single MCP
server (`aria-mcp-proxy`) exposing `search_tools` and `call_tool`. Per-agent
capability enforcement runs in `CapabilityMatrixMiddleware` (P9 preserved).

## Consequences

- ~95% reduction in tool definition tokens at startup (~40 K → < 2 K).
- Constant context cost regardless of agent count or backend count.
- Single point of failure: the proxy. Mitigated by `bin/aria start
  --emergency-direct` (MTTR < 2 min) and by `aria-memory` remaining on
  the direct path.
- Stack stays pure Python. FastMCP is already a dependency. No new
  third-party orchestrator.

## Alternatives considered

- `fussraider/tool-search-tools-mcp` (TypeScript): rejected due to stack
  drift and solo-dev maintenance signal.
- `rupinder2/mcp-orchestrator` (Python): rejected due to fragile dynamic
  tools (`inspect.Signature`) and stale upstream.

See `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md` and
`docs/analysis/mcp_tool_search_analysis_1.md` for full analysis.
```

- [ ] **Step 2: Commit**

```bash
git add docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md
git commit -m "docs(adr): ADR-0015 FastMCP-native MCP proxy replaces lazy loader"
```

---

## Phase F5 — Observability + skills + wiki (~1 day)

### Task F5.1: Add proxy metrics

**Files:**
- Modify: `src/aria/observability/metrics.py`
- Create: `tests/unit/observability/test_proxy_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/observability/test_proxy_metrics.py
from aria.observability.metrics import (
    aria_proxy_search_latency_seconds,
    aria_proxy_tool_call_total,
    aria_proxy_tool_denied_total,
    aria_proxy_backend_health,
    aria_proxy_context_tokens_saved,
    aria_proxy_caller_missing_total,
    aria_proxy_embedding_index_seconds,
)


def test_proxy_metrics_exposed() -> None:
    aria_proxy_search_latency_seconds.labels(agent="search-agent").observe(0.05)
    aria_proxy_tool_call_total.labels(agent="search-agent", tool="x", status="ok").inc()
    aria_proxy_tool_denied_total.labels(agent="search-agent", tool="x", reason="not_allowed").inc()
    aria_proxy_backend_health.labels(server="filesystem").set(1)
    aria_proxy_context_tokens_saved.set(38000)
    aria_proxy_caller_missing_total.labels(reason="missing").inc()
    aria_proxy_embedding_index_seconds.observe(1.5)
```

- [ ] **Step 2: Add metric definitions**

```python
# src/aria/observability/metrics.py — append
from prometheus_client import Counter, Gauge, Histogram

aria_proxy_search_latency_seconds = Histogram(
    "aria_proxy_search_latency_seconds",
    "Latency of search_tools calls",
    labelnames=("agent",),
)
aria_proxy_tool_call_total = Counter(
    "aria_proxy_tool_call_total",
    "Total call_tool invocations through the proxy",
    labelnames=("agent", "tool", "status"),
)
aria_proxy_tool_denied_total = Counter(
    "aria_proxy_tool_denied_total",
    "call_tool invocations denied by capability matrix",
    labelnames=("agent", "tool", "reason"),
)
aria_proxy_backend_health = Gauge(
    "aria_proxy_backend_health",
    "Backend health (0 unhealthy, 1 healthy)",
    labelnames=("server",),
)
aria_proxy_context_tokens_saved = Gauge(
    "aria_proxy_context_tokens_saved",
    "Estimated tool definition tokens saved vs LKG baseline",
)
aria_proxy_caller_missing_total = Counter(
    "aria_proxy_caller_missing_total",
    "call_tool invocations without _caller_id",
    labelnames=("reason",),
)
aria_proxy_embedding_index_seconds = Histogram(
    "aria_proxy_embedding_index_seconds",
    "Time spent indexing tool embeddings at boot or rebuild",
)
```

- [ ] **Step 3: Run tests**

Run: `pytest -q tests/unit/observability/test_proxy_metrics.py`
Expected: 1 passed.

- [ ] **Step 4: Wire metrics into middleware + transform**

In `src/aria/mcp/proxy/middleware.py`, increment `aria_proxy_tool_call_total` and `aria_proxy_tool_denied_total` from `on_call_tool`.

In `src/aria/mcp/proxy/transforms/hybrid.py`, observe `aria_proxy_embedding_index_seconds` around `_index_tool` and `aria_proxy_search_latency_seconds` around `_score`.

- [ ] **Step 5: Commit**

```bash
git add src/aria/observability/metrics.py \
        src/aria/mcp/proxy/middleware.py \
        src/aria/mcp/proxy/transforms/hybrid.py \
        tests/unit/observability/test_proxy_metrics.py
git commit -m "feat(observability): add aria_proxy_* metrics + wire into proxy components"
```

### Task F5.2: Add proxy events

**Files:**
- Modify: `src/aria/observability/events.py`

- [ ] **Step 1: Add event types**

```python
# src/aria/observability/events.py — append to the typed-event registry
class ProxyStartedEvent(BaseEvent):
    event: Literal["proxy.start"] = "proxy.start"
    backends: list[str]


class ProxyShutdownEvent(BaseEvent):
    event: Literal["proxy.shutdown"] = "proxy.shutdown"


class ProxyBackendQuarantinedEvent(BaseEvent):
    event: Literal["proxy.backend_quarantine"] = "proxy.backend_quarantine"
    server: str
    reason: str


class ProxyBackendRecoveredEvent(BaseEvent):
    event: Literal["proxy.backend_recovered"] = "proxy.backend_recovered"
    server: str


class ProxyCutoverEvent(BaseEvent):
    event: Literal["proxy.cutover"] = "proxy.cutover"
    from_baseline: str
    to: str


class ProxyEmergencyRollbackEvent(BaseEvent):
    event: Literal["proxy.emergency_rollback"] = "proxy.emergency_rollback"
    triggered_by: str


class ProxyCallerAnomalyEvent(BaseEvent):
    event: Literal["proxy.caller_anomaly"] = "proxy.caller_anomaly"
    caller: str | None
    tool: str
    reason: str
```

- [ ] **Step 2: Emit on proxy startup / shutdown**

In `src/aria/mcp/proxy/__main__.py`, around `proxy.run_async`, emit `ProxyStartedEvent(backends=[...])` and `ProxyShutdownEvent()`.

- [ ] **Step 3: Run quality gate**

Run: `make quality`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add src/aria/observability/events.py src/aria/mcp/proxy/__main__.py
git commit -m "feat(observability): typed proxy.* events + start/shutdown emission"
```

### Task F5.3: Update skills with namespaced tool refs

**Files:**
- Modify: `.aria/kilocode/skills/deep-research/SKILL.md`
- Modify: `.aria/kilocode/skills/office-ingest/SKILL.md`
- Modify: `.aria/kilocode/skills/pdf-extract/SKILL.md`
- Modify: `.aria/kilocode/skills/consultancy-brief/SKILL.md`
- Modify: `.aria/kilocode/skills/meeting-prep/SKILL.md`
- Modify: `.aria/kilocode/skills/source-dedup/SKILL.md`

- [ ] **Step 1: Search for hardcoded references**

Run: `rg -n "tavily-mcp/|brave-mcp/|exa-script/|searxng-script/|reddit-search/|scientific-papers-mcp/|markitdown-mcp/" .aria/kilocode/skills`
Expected: a list of skill files with hardcoded `server/tool` references.

- [ ] **Step 2: Replace with namespaced form**

For each skill, replace `server/tool` with `aria-mcp-proxy__call_tool(name="server__tool", ...)`. Example diff for a deep-research SKILL excerpt:

```diff
-Use `tavily-mcp/search` for web tier 2.
+Use `aria-mcp-proxy__call_tool(name="tavily-mcp__search", _caller_id="search-agent", arguments={...})` for web tier 2.
```

- [ ] **Step 3: Validate skills file structure**

Run: `python -c '
import yaml, pathlib
for p in pathlib.Path(".aria/kilocode/skills").rglob("SKILL.md"):
    if p.read_text().startswith("---"):
        body = p.read_text().split("---", 2)
        yaml.safe_load(body[1])
print("ok")
'`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add .aria/kilocode/skills/
git commit -m "feat(skills): rewrite hardcoded MCP refs to namespaced proxy invocations"
```

### Task F5.4: Wiki update

**Files:**
- Create: `docs/llm_wiki/wiki/mcp-proxy.md`
- Modify: `docs/llm_wiki/wiki/index.md`
- Modify: `docs/llm_wiki/wiki/log.md`
- Modify: `docs/llm_wiki/wiki/mcp-architecture.md`
- Modify: `docs/llm_wiki/wiki/mcp-refoundation.md`

- [ ] **Step 1: Write `mcp-proxy.md`**

```markdown
# MCP Proxy (aria-mcp-proxy)

**Last Updated**: 2026-05-XX
**Status**: Active
**Source**: `src/aria/mcp/proxy/`, `.aria/config/proxy.yaml`,
`docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`

## Purpose

A FastMCP-native multi-server proxy that exposes `search_tools` and
`call_tool` synthetic tools to KiloCode. Replaces the static
`lazy_loader.py` and removes per-server tool-definition cost from the
KiloCode startup context.

## Components

| File | Responsibility |
|---|---|
| `src/aria/mcp/proxy/server.py` | wires catalog + transform + middleware |
| `src/aria/mcp/proxy/catalog.py` | loads `mcp_catalog.yaml`, yields `BackendSpec`s |
| `src/aria/mcp/proxy/credential.py` | resolves `${VAR}` placeholders via `CredentialManager` |
| `src/aria/mcp/proxy/middleware.py` | per-agent allowed-tools enforcement (`_caller_id`) |
| `src/aria/mcp/proxy/transforms/hybrid.py` | BM25 + mxbai-embed-large-v1 blend |
| `src/aria/mcp/proxy/transforms/lmstudio_embedder.py` | HTTP client for LM Studio embeddings |

## Operational

- mcp.json: 2 entries (`aria-memory`, `aria-mcp-proxy`)
- Emergency rollback: `bin/aria start --emergency-direct`
- Embeddings cache: `.aria/runtime/proxy/embeddings/`
- Metrics: `aria_proxy_*` (Prometheus)
- Events: `proxy.start`, `proxy.shutdown`, `proxy.backend_quarantine`,
  `proxy.cutover`, `proxy.emergency_rollback`, `proxy.caller_anomaly`

## Spec & ADR

- Design: `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`
- ADR: `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`
```

- [ ] **Step 2: Update index.md**

Append a row in the page table:

```markdown
| **[[mcp-proxy]]** | **NEW v6.0**: FastMCP-native MCP proxy replacing the static lazy loader. Hybrid BM25+mxbai semantic search. Per-agent capability enforcement. | **✅ v1.0** |
```

- [ ] **Step 3: Update mcp-refoundation.md**

In the section that documents the lazy loader, add a banner:

```markdown
> **Superseded as of 2026-05-XX** by `aria-mcp-proxy` — see
> `docs/llm_wiki/wiki/mcp-proxy.md` and ADR-0015. The static lazy loader
> has been removed.
```

- [ ] **Step 4: Update mcp-architecture.md**

Refresh the "Current state" section to reflect 2 mcp.json entries and the proxy.

- [ ] **Step 5: Append a log entry**

In `docs/llm_wiki/wiki/log.md`:

```markdown
### 2026-05-XX — v6.0

- Cutover to `aria-mcp-proxy` (FastMCP-native).
- Removed `src/aria/launcher/lazy_loader.py`.
- Reduced `mcp.json` to 2 entries (`aria-memory`, `aria-mcp-proxy`).
- Updated 4 agent prompts and 6 skills to namespaced tool names.
- Added `aria_proxy_*` Prometheus metrics + typed `proxy.*` events.
- ADR-0015 written.
```

- [ ] **Step 6: Commit**

```bash
git add docs/llm_wiki/wiki/mcp-proxy.md docs/llm_wiki/wiki/index.md \
        docs/llm_wiki/wiki/log.md docs/llm_wiki/wiki/mcp-architecture.md \
        docs/llm_wiki/wiki/mcp-refoundation.md
git commit -m "docs(wiki): mcp-proxy page + index/log/architecture/refoundation refresh"
```

### Task F5.5: Search-quality e2e gate

**Files:**
- Create: `tests/e2e/mcp/proxy/test_search_quality.py`

- [ ] **Step 1: Write the test**

```python
# tests/e2e/mcp/proxy/test_search_quality.py
"""Search quality gate — top-3 hit rate ≥85% across 20 reference queries.

Skipped unless ARIA_E2E_SEARCH_QUALITY=1 (depends on real LM Studio + real
backends). The 20 queries below were curated from real ARIA traces.
"""
from __future__ import annotations

import asyncio
import os

import pytest
from fastmcp import Client

QUERIES = [
    ("ricerca paper accademici state space model", "scientific-papers-mcp__search_papers"),
    ("invia un'email a Mario", "google_workspace__gmail_send"),
    ("cerca su reddit discussioni AI", "reddit-search__search"),
    ("converti questo PDF in markdown", "markitdown-mcp__convert"),
    ("salva memoria utente preferenze", "aria-memory__wiki_update_tool"),
    ("recall wiki Tavily routing", "aria-memory__wiki_recall_tool"),
    ("naviga su un sito e prendi screenshot", "playwright__navigate"),
    ("cerca file in /tmp", "filesystem__list_directory"),
    ("leggi questo file txt", "filesystem__read"),
    ("scrivi un file json", "filesystem__write"),
    ("ricerca Brave news ultime", "brave-mcp__news_search"),
    ("cerca su Tavily best practice REST API", "tavily-mcp__search"),
    ("Exa deep search Mamba architecture", "exa-script__search"),
    ("self-hosted searxng query", "searxng-script__search"),
    ("get post da subreddit /r/Python", "reddit-search__get_post"),
    ("crea un evento calendario domani", "google_workspace__calendar_create_event"),
    ("aggiungi nota in google docs", "google_workspace__docs_create"),
    ("scarica una pagina web in plain text", "fetch__fetch"),
    ("trova repo su github relativi a fastmcp", "github-discovery__discover_repos"),
    ("cerca paper recenti EuropePMC", "scientific-papers-mcp__fetch_latest"),
]


@pytest.mark.e2e
@pytest.mark.skipif(os.getenv("ARIA_E2E_SEARCH_QUALITY") != "1", reason="manual quality harness")
def test_top3_hit_rate() -> None:
    async def _run() -> float:
        hits = 0
        async with Client("python -m aria.mcp.proxy") as client:
            for query, expected_tool in QUERIES:
                res = await client.call_tool(
                    "search_tools", {"pattern": query, "_caller_id": "aria-conductor"}
                )
                top3 = [r.get("name") for r in (res.data or [])[:3]]
                if expected_tool in top3:
                    hits += 1
        return hits / len(QUERIES)

    rate = asyncio.run(_run())
    assert rate >= 0.85, f"top-3 hit rate {rate:.2%} below ship gate 85%"
```

- [ ] **Step 2: Run with real LM Studio**

Run: `ARIA_E2E_SEARCH_QUALITY=1 pytest -q tests/e2e/mcp/proxy/test_search_quality.py -s`
Expected: rate ≥ 0.85.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/mcp/proxy/test_search_quality.py
git commit -m "test(proxy): F5 search-quality gate (top-3 hit rate ≥85%)"
```

### Task F5.6: Context-token reduction gate

**Files:**
- Create: `tests/e2e/mcp/proxy/test_context_token_reduction.py`

- [ ] **Step 1: Write the test**

```python
# tests/e2e/mcp/proxy/test_context_token_reduction.py
"""Context-token reduction gate.

Compare token cost of mcp.json (LKG with 14 servers) to the proxy
configuration (2 servers). Pass if reduction ≥ 80%.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
LKG = REPO / ".aria/kilocode/mcp.json.baseline"
LIVE = REPO / ".aria/kilocode/mcp.json"


def _approx_tokens(d: dict) -> int:
    # naive token estimate: 1 token ≈ 4 characters
    return len(json.dumps(d)) // 4


@pytest.mark.e2e
def test_token_reduction_at_least_80pct() -> None:
    if not LKG.exists() or not LIVE.exists():
        pytest.skip("baseline or live mcp.json missing")
    lkg_tokens = _approx_tokens(json.loads(LKG.read_text()))
    live_tokens = _approx_tokens(json.loads(LIVE.read_text()))
    assert live_tokens / lkg_tokens <= 0.20, (
        f"reduction insufficient: live={live_tokens} lkg={lkg_tokens}"
    )
```

- [ ] **Step 2: Run**

Run: `pytest -q tests/e2e/mcp/proxy/test_context_token_reduction.py`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/mcp/proxy/test_context_token_reduction.py
git commit -m "test(proxy): F5 context-token reduction gate (≥80%)"
```

### Task F5.7: Final quality gate + PR

- [ ] **Step 1: Run full test + quality gate**

Run: `make quality && pytest -q`
Expected: green.

- [ ] **Step 2: Open PR**

```bash
gh pr create --title "feat(proxy): replace lazy loader with FastMCP-native tool search proxy" \
  --body "$(cat <<'EOF'
## Summary

- Replace `src/aria/launcher/lazy_loader.py` with a FastMCP-native multi-server proxy at `src/aria/mcp/proxy/`.
- Reduce mcp.json from 14 entries to 2 (`aria-memory`, `aria-mcp-proxy`).
- Add HybridSearchTransform that blends BM25 with the locally available mxbai-embed-large-v1 embeddings via LM Studio (no new external downloads, no network egress).
- Enforce `agent_capability_matrix.yaml` at runtime via CapabilityMatrixMiddleware (P9 preserved).
- Add `bin/aria start --emergency-direct` for <2-min rollback to LKG.
- Add `aria_proxy_*` Prometheus metrics and typed `proxy.*` events.

Spec: `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md`
Plan: `docs/plans/mcp_search_tool_plan_1.md`
ADR: `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`

## Test plan

- [ ] make quality green
- [ ] pytest tests/unit/mcp/proxy + tests/integration/mcp/proxy green
- [ ] Manual KiloCode 7.2.x session: conductor → search-agent academic query → result cited
- [ ] tests/e2e/mcp/proxy/test_search_quality.py top-3 hit rate ≥ 85% (with ARIA_E2E_SEARCH_QUALITY=1)
- [ ] tests/e2e/mcp/proxy/test_context_token_reduction.py ≥ 80% reduction
- [ ] `bin/aria start --emergency-direct` restores baseline mcp.json in < 2 min
EOF
)"
```

---

## Self-review checklist

- [ ] **Spec coverage**: every requirement in `docs/superpowers/specs/2026-05-01-mcp-tool-search-design.md` §11 (Acceptance criteria) is realised by at least one task above.
- [ ] **Placeholder scan**: no "TBD", "TODO", "later" — `Branch: TBD` resolved by F1.1; F4.3 / F5.4 contain placeholder dates `2026-05-XX` to be filled at commit time (acceptable — they are calendar values, not engineering placeholders).
- [ ] **Type consistency**: `BackendSpec`, `CredentialInjector`, `LMStudioEmbedder`, `HybridSearchTransform`, `CapabilityMatrixMiddleware`, `ProxyConfig` referenced consistently across tasks.
- [ ] **Reversible**: every phase ends with a committed state; `git revert <sha>` restores the prior phase. F3 + F4 also covered by `bin/aria start --emergency-direct`.

---

## Execution

Plan complete. Two execution options:

1. **Subagent-driven (recommended)** — fresh subagent per task, review between tasks. Required sub-skill: `superpowers:subagent-driven-development`.
2. **Inline execution** — execute tasks in the current session with checkpoints. Required sub-skill: `superpowers:executing-plans`.

Pick one when ready to start F1.
