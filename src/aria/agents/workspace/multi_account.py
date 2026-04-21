from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceAccount:
    """Workspace account descriptor for Phase 2 multi-account readiness."""

    label: str
    is_primary: bool = False


class MultiAccountRegistry:
    """Phase 1 stub that keeps single-account behavior explicit."""

    def list_accounts(self) -> list[WorkspaceAccount]:
        return [WorkspaceAccount(label="primary", is_primary=True)]

    def resolve(self, label: str | None = None) -> WorkspaceAccount:
        candidate = (label or "primary").strip() or "primary"
        if candidate != "primary":
            raise ValueError(
                "Multi-account routing is not enabled in Phase 1. Use account='primary'."
            )
        return WorkspaceAccount(label="primary", is_primary=True)


__all__ = ["WorkspaceAccount", "MultiAccountRegistry"]
