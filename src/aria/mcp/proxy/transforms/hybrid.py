"""Blend BM25 keyword scoring with mxbai-embed-large-v1 semantic similarity.

Subclasses FastMCP's BM25SearchTransform. When the LM Studio endpoint is
unavailable at boot or fails mid-flight, we degrade silently to BM25-only.
The transform exposes `search_tools` and `call_tool` synthetic tools to
the client (inherited behaviour from BM25SearchTransform).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fastmcp.tools import Tool

try:  # FastMCP 3.2+ exposes the transform here
    from fastmcp.server.transforms.search.bm25 import BM25SearchTransform, _BM25Index
except ImportError:  # pragma: no cover — older FastMCP layouts
    from fastmcp.server.transforms.search import BM25SearchTransform

from aria.mcp.proxy.transforms.lmstudio_embedder import (
    LMStudioEmbedder,
    LMStudioUnavailableError,
)

logger = logging.getLogger("aria.mcp.proxy.transforms.hybrid")


def _catalog_hash(tools: Sequence[Tool]) -> str:
    """Compute a hash over tool names to detect catalog changes."""
    import hashlib

    return hashlib.sha256("-".join(t.name for t in tools).encode()).hexdigest()


def _extract_searchable_text(tool: Tool) -> str:
    """Extract searchable text from a tool."""
    name = getattr(tool, "name", "") or ""
    description = getattr(tool, "description", "") or ""
    return f"{name} {description}"


def _tool_text(tool: Tool) -> str:
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
        max_results: int = 5,
    ) -> None:
        super().__init__(max_results=max_results)
        self._embedder = embedder
        self._blend = blend
        self._tool_vectors: dict[str, np.ndarray] = {}
        self._semantic_enabled = embedder is not None and embedder.probe()

    async def _search(  # noqa: PLR0912
        self,
        tools: Sequence[Tool],
        query: str,
    ) -> Sequence[Tool]:
        """Override _search to blend BM25 with semantic similarity."""
        if not tools:
            return tools

        # Build/rebuild BM25 index if catalog changed
        current_hash = _catalog_hash(tools)
        if current_hash != self._last_hash:
            documents = [_extract_searchable_text(t) for t in tools]
            new_index = _BM25Index(self._index.k1, self._index.b)
            new_index.build(documents)
            self._index = new_index
            self._indexed_tools = tools
            self._last_hash = current_hash

        # Get full BM25 ranking
        indices = self._index.query(query, len(tools))
        # BM25 score by position (normalized)
        bm25_by_name: dict[str, float] = {}
        if indices:
            max_pos = len(indices)
            for pos, idx in enumerate(indices):
                tool_name = tools[idx].name
                bm25_by_name[tool_name] = 1.0 - (pos / max_pos)

        # Compute semantic vectors on first use
        if self._semantic_enabled and self._embedder is not None and not self._tool_vectors:
            try:
                texts = [_tool_text(t) for t in tools]
                vectors = self._embedder.embed(texts)
                for tool, vec in zip(tools, vectors, strict=False):
                    self._tool_vectors[tool.name] = vec
            except LMStudioUnavailableError:
                self._semantic_enabled = False
                logger.warning("LM Studio unavailable during hybrid — degraded to BM25")

        # Compute query embedding
        qv: np.ndarray | None = None
        if self._semantic_enabled and self._embedder is not None:
            try:
                qv = self._embedder.embed([query])[0]
            except LMStudioUnavailableError:
                self._semantic_enabled = False
                logger.warning("LM Studio unavailable during scoring — degraded to BM25")

        # Score each tool with combined ranking
        scored: list[tuple[float, Tool]] = []
        for _i, tool in enumerate(tools):
            bm25_score = bm25_by_name.get(tool.name, 0.0)

            if qv is not None and tool.name in self._tool_vectors:
                vec = self._tool_vectors[tool.name]
                cos_sim = float(np.dot(qv, vec))
                # Clamp cosine similarity from [-1, 1] to [0, 1]
                semantic_score = max(0.0, min(1.0, (cos_sim + 1.0) / 2.0))
                combined = self._blend * bm25_score + (1.0 - self._blend) * semantic_score
            else:
                combined = bm25_score

            scored.append((combined, tool))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[: self._max_results]]
