"""Unit tests for LMStudioEmbedder using respx mocks."""
from __future__ import annotations

import httpx
import numpy as np
import pytest
import respx

from aria.mcp.proxy.transforms.lmstudio_embedder import (
    LMStudioEmbedder,
    LMStudioUnavailableError,
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
    with pytest.raises(LMStudioUnavailableError, match="dimension mismatch"):
        e.embed(["a"])


@respx.mock
def test_embed_raises_on_http_error() -> None:
    respx.post(ENDPOINT).mock(return_value=httpx.Response(500, text="boom"))
    e = LMStudioEmbedder(endpoint=ENDPOINT, model="m", dim=4)
    with pytest.raises(LMStudioUnavailableError):
        e.embed(["a"])


@respx.mock
def test_normalize_unit_length() -> None:
    respx.post(ENDPOINT).mock(
        return_value=httpx.Response(200, json={"data": [{"embedding": [3.0, 4.0]}]})
    )
    e = LMStudioEmbedder(endpoint=ENDPOINT, model="m", dim=2, normalize=True)
    out = e.embed(["a"])
    assert pytest.approx(float(np.linalg.norm(out[0])), abs=1e-6) == 1.0
