"""HTTP client for LM Studio's OpenAI-compatible embeddings endpoint.

Returns numpy arrays (shape `(dim,)`, dtype float32). Raises
LMStudioUnavailableError on any failure so callers can degrade gracefully.
"""

from __future__ import annotations

import httpx
import numpy as np


class LMStudioUnavailableError(RuntimeError):
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
            r = self._client.post(self._endpoint, json={"model": self._model, "input": texts})
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise LMStudioUnavailableError(str(exc)) from exc
        data = r.json().get("data") or []
        out: list[np.ndarray] = []
        for entry in data:
            emb = entry.get("embedding") or []
            if len(emb) != self._dim:
                raise LMStudioUnavailableError(
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
