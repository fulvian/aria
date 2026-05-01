"""Unit tests for ProxyConfig loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from aria.mcp.proxy.config import ProxyConfig


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
