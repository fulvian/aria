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
