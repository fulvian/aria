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

# Tier defaults
DEFAULT_TIER_LIFECYCLE: str = "lazy"
DEFAULT_TIER_CONCURRENCY: int = 4
DEFAULT_TIER_IDLE_TTL_S: int = 300
DEFAULT_TIER_BREAKER_THRESHOLD: int = 3
DEFAULT_TIER_BREAKER_COOLDOWN_S: int = 60
DEFAULT_TIER_WARM_BOOT_TIMEOUT_S: float = 5.0
DEFAULT_TIER_HEALTHCHECK_INTERVAL_S: float = 30.0
DEFAULT_TIER_MAX_RETRY_ATTEMPTS: int = 10


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


class TierConfig(BaseModel):
    """Global tier default overrides for the tier-based proxy lifecycle.

    Per-backend values in catalog take precedence over these defaults.
    """

    model_config = ConfigDict(extra="forbid")

    default_lifecycle: Literal["warm", "lazy"] = DEFAULT_TIER_LIFECYCLE  # type: ignore[assignment]
    default_concurrency: int = Field(default=DEFAULT_TIER_CONCURRENCY, ge=1)
    default_idle_ttl_s: int = Field(default=DEFAULT_TIER_IDLE_TTL_S, ge=10)
    default_breaker_threshold: int = Field(default=DEFAULT_TIER_BREAKER_THRESHOLD, ge=1)
    default_breaker_cooldown_s: int = Field(default=DEFAULT_TIER_BREAKER_COOLDOWN_S, ge=5)
    warm_boot_timeout_s: float = Field(default=DEFAULT_TIER_WARM_BOOT_TIMEOUT_S, ge=1.0, le=60.0)
    healthcheck_interval_s: float = Field(
        default=DEFAULT_TIER_HEALTHCHECK_INTERVAL_S, ge=5.0, le=300.0
    )
    max_retry_attempts: int = Field(default=DEFAULT_TIER_MAX_RETRY_ATTEMPTS, ge=1, le=100)


class ProxyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: SearchConfig = Field(default_factory=SearchConfig)
    tier: TierConfig = Field(default_factory=TierConfig)

    @classmethod
    def load(cls, path: Path) -> ProxyConfig:
        if not path.exists():
            return cls()
        raw = yaml.safe_load(path.read_text()) or {}
        return cls.model_validate(raw)
