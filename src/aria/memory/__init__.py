# ARIA memory module
#
# Implements the 5D memory subsystem:
# - Tier 0: Episodic (SQLite WAL + FTS5)
# - Tier 1: Semantic (FTS5 search)
# - Tier 2: Semantic embeddings (LanceDB, lazy)
# - Tier 3: Associative graph (@phase2)
# - Procedural: Skills registry in filesystem
#
# Actor-aware tagging: user_input | tool_output | agent_inference | system_event
#
# Usage:
#   from aria.memory import EpisodicStore
#   store = EpisodicStore(db_path)

from __future__ import annotations

__all__ = ["EpisodicStore"]


class EpisodicStore:
    """Episodic memory store stub - full implementation in Phase 1."""

    def __init__(self, db_path: str = ":memory:") -> None:
        """Initialize episodic store."""
        pass

    def add(
        self,
        session_id: str,
        actor: str,
        role: str,
        content: str,
        **kwargs: object,
    ) -> dict:
        """Add an episodic entry."""
        return {"id": "stub", "session_id": session_id}

    def get_by_session(self, session_id: str, limit: int = 50) -> list[dict]:
        """Get entries by session."""
        return []

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Search episodic memory."""
        return []
