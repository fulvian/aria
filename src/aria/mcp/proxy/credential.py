"""Resolve ${VAR} placeholders in BackendSpec.env using ARIA's CredentialManager.

Strict mode (default) raises on unresolved keys. Non-strict mode drops the
backend and returns the survivors — used at proxy boot so a single missing
key does not take down the entire proxy.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Protocol

from aria.mcp.proxy.catalog import BackendSpec
from aria.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable

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

    def inject_all(self, specs: Iterable[BackendSpec], *, strict: bool = True) -> list[BackendSpec]:
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
