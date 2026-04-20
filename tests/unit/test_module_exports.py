from __future__ import annotations

from aria.credentials import CredentialManager
from aria.memory import EpisodicStore


def test_credentials_exports_real_manager() -> None:
    assert "manager" in CredentialManager.__module__


def test_memory_exports_real_episodic_store() -> None:
    assert "episodic" in EpisodicStore.__module__
