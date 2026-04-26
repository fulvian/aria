# ARIA Memory MCP Server
#
# FastMCP 3.x server exposing 11 memory tools.
# Per blueprint §5.6 and sprint plan W1.1.L / Sprint 1.2.
#
# Tools:
# 1. remember - Write T0 episodic entry
# 2. recall - Semantic/T0 search
# 3. recall_episodic - Session chronological recall
# 4. distill - Trigger CLM distillation
# 5. curate - HITL-gated promote/demote/forget
# 6. forget - HITL-gated soft delete
# 7. stats - Memory telemetry
# 8. hitl_ask - Queue a human-in-the-loop approval request
# 9. hitl_list_pending - List all pending HITL approval requests
# 10. hitl_cancel - Cancel a pending HITL request before approval
# 11. hitl_approve - Approve a pending HITL request and execute the action
#
# Transport: stdio (configurable via ARIA_MEMORY_MCP_TRANSPORT)
#
# Usage:
#   python -m aria.memory.mcp_server

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

from aria.config import get_config
from aria.memory.actor_tagging import derive_actor_from_role
from aria.memory.clm import CLM
from aria.memory.episodic import EpisodicStore, create_episodic_store
from aria.memory.schema import Actor, EpisodicEntry, content_hash
from aria.memory.semantic import SemanticStore
from aria.utils.logging import new_trace_id, set_trace_id

# === FastMCP Setup ===

mcp = FastMCP("aria-memory")

# Global state (initialized on first tool call)
_store: EpisodicStore | None = None
_semantic: SemanticStore | None = None
_clm: CLM | None = None
_config = None


async def _ensure_store() -> tuple[EpisodicStore, SemanticStore, CLM]:
    """Ensure stores are initialized (lazy init)."""
    global _store, _semantic, _clm, _config  # noqa: PLW0603

    if _store is None:
        _config = get_config()
        _store = await create_episodic_store(_config)

        # Initialize semantic store with same connection
        _semantic = SemanticStore(_store._db_path, _config)
        conn = _store._conn
        if conn is None:
            raise RuntimeError("EpisodicStore connection is None")
        await _semantic.connect(conn)

        # Initialize CLM
        _clm = CLM(_store, _semantic)

    if _semantic is None or _clm is None:
        raise RuntimeError("Stores not fully initialized")

    return _store, _semantic, _clm


def _get_session_id() -> uuid.UUID:
    """Return the active ARIA session id.

    Priority:
      1. ``ARIA_SESSION_ID`` env var (UUID)
      2. ``uuid.uuid4()`` fallback when ``ARIA_MEMORY_STRICT_SESSION`` is unset/false

    Raises:
        RuntimeError: when strict mode is requested but no env var is set.
            Strict mode is enabled by setting ``ARIA_MEMORY_STRICT_SESSION=1``
            and is required for interactive (REPL/Telegram) sessions so every
            ``remember`` lands in the same session bucket.
    """
    session_str = os.environ.get("ARIA_SESSION_ID", "").strip()
    if session_str:
        try:
            return uuid.UUID(session_str)
        except ValueError as exc:
            raise RuntimeError(
                f"ARIA_SESSION_ID is set but not a valid UUID: {session_str!r}"
            ) from exc
    if os.environ.get("ARIA_MEMORY_STRICT_SESSION", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        raise RuntimeError(
            "ARIA_SESSION_ID is required when ARIA_MEMORY_STRICT_SESSION=1"
        )
    return uuid.uuid4()


# === MCP Tools ===


@mcp.tool
async def remember(
    content: str,
    actor: str,
    role: str,
    session_id: str | None = None,
    tags: list[str] | str | None = None,
) -> dict:
    """Store a new episodic memory entry (Tier 0).

    Args:
        content: Verbatim content to store
        actor: Actor type (user_input, tool_output, agent_inference, system_event)
        role: Message role (user, assistant, system, tool)
        session_id: Session UUID (optional — resolved from ARIA_SESSION_ID env if omitted)
        tags: Optional tags (list of strings)

    Returns:
        {"status": "ok", "entry_id": "...", "session_id": "..."}
    """
    # Ensure trace_id
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, _, _ = await _ensure_store()

        # Parse actor
        try:
            actor_enum = Actor(actor)
        except ValueError:
            actor_enum = derive_actor_from_role(role, is_tool_result=False)

        # Parse session — always use env-aware resolver; ignore literal
        # "${ARIA_SESSION_ID}" that agents may send when they cannot read env.
        resolved_sid: str | None = None
        if session_id and not session_id.startswith("$"):
            resolved_sid = session_id
        sess_uuid = uuid.UUID(resolved_sid) if resolved_sid else _get_session_id()

        # Parse tags — agents may send a JSON string instead of a list.
        parsed_tags: list[str] = []
        if isinstance(tags, str):
            try:
                parsed_tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                parsed_tags = [tags]
        elif isinstance(tags, list):
            parsed_tags = tags

        # Create entry
        entry = EpisodicEntry(
            session_id=sess_uuid,
            ts=datetime.now(UTC),
            actor=actor_enum,
            role=role,
            content=content,
            content_hash=content_hash(content),
            tags=parsed_tags,
        )

        await store.insert(entry)

        return {
            "status": "ok",
            "entry_id": str(entry.id),
            "session_id": str(entry.session_id),
            "content_hash": entry.content_hash,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool
async def recall(
    query: str,
    top_k: int = 10,
    kinds: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    """Recall semantic chunks matching query (Tier 1 first, then T0 fallback).

    Args:
        query: Search query
        top_k: Number of results (default 10)
        kinds: Optional filter by chunk kinds
        since: Optional start time (ISO8601)
        until: Optional end time (ISO8601)

    Returns:
        List of matching entries/chunks
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        _, semantic, _ = await _ensure_store()

        # Search semantic first
        chunks = await semantic.search(query, top_k=top_k, kinds=kinds)

        results = []
        for chunk in chunks:
            results.append(
                {
                    "id": str(chunk.id),
                    "kind": chunk.kind,
                    "text": chunk.text,
                    "actor": chunk.actor.value if isinstance(chunk.actor, Actor) else chunk.actor,
                    "confidence": chunk.confidence,
                    "keywords": chunk.keywords,
                    "source_episodic_ids": [str(id) for id in chunk.source_episodic_ids],
                    "first_seen": chunk.first_seen.isoformat(),
                    "last_seen": chunk.last_seen.isoformat(),
                }
            )

        # If no semantic results, search episodic (T0 fallback)
        if not results and top_k > 0:
            store, _, _ = await _ensure_store()
            episodic_results = await store.search_text(query, top_k=top_k)

            for entry in episodic_results:
                results.append(
                    {
                        "id": str(entry.id),
                        "kind": "episodic",
                        "text": entry.content,
                        "actor": entry.actor.value
                        if isinstance(entry.actor, Actor)
                        else entry.actor,
                        "role": entry.role,
                        "content_hash": entry.content_hash,
                        "session_id": str(entry.session_id),
                        "ts": entry.ts.isoformat(),
                        "tags": entry.tags,
                    }
                )

        return results

    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool
async def recall_episodic(
    session_id: str | None = None,
    since: str | None = None,
    limit: int = 50,
    query: str | None = None,
    include_benchmark: bool = False,
) -> list[dict]:
    """Recall episodic entries chronologically, optionally filtered by topic.

    Args:
        session_id: Optional session filter (UUID).
        since: Optional ISO8601 lower bound. Defaults to 7 days ago.
        limit: Max results (default 50).
        query: Optional FTS5 query. When provided, performs a full-text
            search over the episodic content within the chosen window.
        include_benchmark: When False (default) drops entries tagged with
            "benchmark" or "test_seed".

    Returns:
        List of EpisodicEntry serialized to dict.
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    excluded = None if include_benchmark else ["benchmark", "test_seed"]

    try:
        store, _, _ = await _ensure_store()

        if query:
            # Topic search: FTS5 on content; tag filter applied client-side
            entries = await store.search_text(query, top_k=max(limit, 1))
            if excluded:
                blocked = set(excluded)
                entries = [e for e in entries if not blocked.intersection(e.tags)]
            entries = entries[:limit]
        elif session_id:
            sess_uuid = uuid.UUID(session_id)
            entries = await store.list_by_session(sess_uuid, limit=limit)
            if excluded:
                blocked = set(excluded)
                entries = [e for e in entries if not blocked.intersection(e.tags)]
        else:
            now = datetime.now(UTC)
            since_dt = (
                datetime.fromisoformat(since.replace("Z", "+00:00"))
                if since
                else datetime.fromtimestamp(now.timestamp() - 7 * 86400, tz=UTC)
            )
            entries = await store.list_by_time_range(
                since_dt, now, limit=limit, exclude_tags=excluded
            )

        return [
            {
                "id": str(entry.id),
                "session_id": str(entry.session_id),
                "ts": entry.ts.isoformat(),
                "actor": entry.actor.value if isinstance(entry.actor, Actor) else entry.actor,
                "role": entry.role,
                "content": entry.content,
                "content_hash": entry.content_hash,
                "tags": entry.tags,
            }
            for entry in entries
        ]

    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool
async def distill(session_id: str) -> list[dict]:
    """Trigger CLM distillation for a session.

    Args:
        session_id: Session to distill

    Returns:
        List of distilled SemanticChunk
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        _, _, clm = await _ensure_store()

        sess_uuid = uuid.UUID(session_id)
        chunks = await clm.distill_session(sess_uuid)

        return [
            {
                "id": str(chunk.id),
                "kind": chunk.kind,
                "text": chunk.text,
                "actor": chunk.actor.value if isinstance(chunk.actor, Actor) else chunk.actor,
                "confidence": chunk.confidence,
                "keywords": chunk.keywords,
                "source_episodic_ids": [str(id) for id in chunk.source_episodic_ids],
            }
            for chunk in chunks
        ]

    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool
async def curate(
    id: str,
    action: Literal["promote", "demote", "forget"],
) -> dict:
    """Curate a semantic chunk (HITL-gated in Sprint 1.1, stubbed).

    In Sprint 1.1, curate with forget creates hitl_pending entry.
    Full HITL wiring in Sprint 1.2.

    Args:
        id: Chunk ID
        action: Action (promote, demote, forget)

    Returns:
        {"status": "pending_hitl", "hitl_id": "..."} or error
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, semantic, clm = await _ensure_store()

        chunk_uuid = uuid.UUID(id)

        if action == "promote":
            await clm.promote(chunk_uuid)
            return {"status": "ok", "action": "promoted"}

        elif action == "demote":
            await clm.demote(chunk_uuid)
            return {"status": "ok", "action": "demoted"}

        elif action == "forget":
            hitl_id = await store.enqueue_hitl(
                target_id=chunk_uuid,
                action="forget_semantic",
                reason="queued via curate(forget)",
                trace_id=trace_id,
                channel="cli",
            )
            return {
                "status": "pending_hitl",
                "hitl_id": hitl_id,
                "message": "forget request queued for HITL approval (Sprint 1.2)",
            }

        return {"status": "error", "error": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool
async def forget(id: str) -> dict:
    """Queue an episodic forget request (HITL-gated).

    Per P6: NO hard delete. Tombstone records deletion request.
    In Sprint 1.1, stub creates hitl_pending; full wiring in Sprint 1.2.

    Args:
        id: Entry ID to forget

    Returns:
        {"status": "pending_hitl", "hitl_id": "..."} or error
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, _, _ = await _ensure_store()
        entry_uuid = uuid.UUID(id)
        hitl_id = await store.enqueue_hitl(
            target_id=entry_uuid,
            action="forget_episodic",
            reason="queued via forget()",
            trace_id=trace_id,
            channel="cli",
        )

        return {
            "status": "pending_hitl",
            "hitl_id": hitl_id,
            "message": "forget request queued for HITL approval (Sprint 1.2)",
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool
async def stats() -> dict:
    """Get memory subsystem statistics.

    Returns:
        MemoryStats (t0_count, t1_count, sessions, etc.)
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, _, _ = await _ensure_store()

        stats = await store.stats()

        return {
            "t0_count": stats.t0_count,
            "t1_count": stats.t1_count,
            "sessions": stats.sessions,
            "last_session_ts": stats.last_session_ts.isoformat() if stats.last_session_ts else None,
            "avg_entry_size": stats.avg_entry_size,
            "storage_bytes": stats.storage_bytes,
        }

    except Exception as e:
        return {"error": str(e)}


@mcp.tool
async def hitl_ask(
    action: str,
    target_id: str,
    reason: str | None = None,
) -> dict:
    """Queue a human-in-the-loop approval request for a memory operation.

    Per blueprint P5/HITL: destructive operations (forget, hard-delete)
    MUST be approved by a human before execution.

    Args:
        action: The action to approve (forget_episodic, forget_semantic)
        target_id: UUID of the target entry/chunk
        reason: Optional human-readable reason for the request

    Returns:
        {"status": "pending_hitl", "hitl_id": "...", "message": "..."}
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, _, _ = await _ensure_store()
        target_uuid = uuid.UUID(target_id)
        channel = os.environ.get("ARIA_HITL_CHANNEL", "mcp")
        hitl_id = await store.enqueue_hitl(
            target_id=target_uuid,
            action=action,
            reason=reason,
            trace_id=trace_id,
            channel=channel,
        )
        return {
            "status": "pending_hitl",
            "hitl_id": hitl_id,
            "message": f"HITL approval requested for {action} on {target_id}",
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool
async def hitl_list_pending(limit: int = 100) -> list[dict]:
    """List all pending HITL approval requests.

    Args:
        limit: Max number of records to return (default 100)

    Returns:
        List of pending HITL records
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, _, _ = await _ensure_store()
        return await store.list_hitl_pending(limit=limit)

    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool
async def hitl_cancel(hitl_id: str) -> dict:
    """Cancel a pending HITL request (before approval).

    Args:
        hitl_id: The HITL request ID to cancel

    Returns:
        {"status": "ok"} or {"status": "error", "error": "..."}
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, _, _ = await _ensure_store()
        conn = await store._ensure_connected()
        cursor = await conn.execute(
            "UPDATE memory_hitl_pending SET status = 'cancelled', resolved_at = ? "
            "WHERE id = ? AND status = 'pending'",
            (int(datetime.now(UTC).timestamp()), hitl_id),
        )
        await conn.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "error": "HITL request not found or already resolved"}
        return {"status": "ok", "hitl_id": hitl_id}

    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool
async def hitl_approve(hitl_id: str) -> dict:  # noqa: PLR0911
    """Approve a pending HITL request and execute the consequent action.

    Supported actions:
    - forget_episodic: tombstones the target episodic entry
    - forget_semantic: deletes the target semantic chunk

    Args:
        hitl_id: The HITL request ID to approve

    Returns:
        {"status": "ok", "action": "...", "target_id": "..."} or error
    """
    trace_id = os.environ.get("ARIA_TRACE_ID") or new_trace_id()
    set_trace_id(trace_id)

    try:
        store, semantic, _ = await _ensure_store()
        conn = await store._ensure_connected()

        # Fetch the pending record
        cursor = await conn.execute(
            "SELECT id, target_id, action, status FROM memory_hitl_pending WHERE id = ?",
            (hitl_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return {"status": "error", "error": f"HITL request {hitl_id} not found"}

        if row["status"] != "pending":
            return {
                "status": "error",
                "error": f"HITL request {hitl_id} is not pending (status={row['status']})",
            }

        action = row["action"]
        target_id = row["target_id"]

        # Execute the action
        if action == "forget_episodic":
            import uuid as _uuid

            tombstoned = await store.tombstone(
                _uuid.UUID(target_id),
                reason=f"approved via hitl_approve({hitl_id})",
            )
            if not tombstoned:
                return {
                    "status": "error",
                    "error": f"Entry {target_id} not found or already tombstoned",
                }

        elif action == "forget_semantic":
            import uuid as _uuid

            deleted = await semantic.delete(_uuid.UUID(target_id))
            if not deleted:
                return {
                    "status": "error",
                    "error": f"Semantic chunk {target_id} not found",
                }

        else:
            return {
                "status": "error",
                "error": f"Unsupported HITL action: {action}",
            }

        # Mark resolved
        await conn.execute(
            "UPDATE memory_hitl_pending SET status = 'approved', resolved_at = ? WHERE id = ?",
            (int(datetime.now(UTC).timestamp()), hitl_id),
        )
        await conn.commit()

        return {
            "status": "ok",
            "hitl_id": hitl_id,
            "action": action,
            "target_id": target_id,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# === Main ===


def main() -> int:
    """Run the MCP server."""
    transport = os.environ.get("ARIA_MEMORY_MCP_TRANSPORT", "stdio")

    # Configure logging to file (not stdout for MCP)
    aria_home = Path(os.environ.get("ARIA_HOME", "/home/fulvio/coding/aria"))
    log_dir = aria_home / ".aria" / "runtime" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Override logging to file
    log_file = log_dir / f"mcp-aria-memory-{datetime.now(UTC).strftime('%Y-%m-%d')}.log"

    handler = logging.FileHandler(log_file)
    from aria.utils.logging import JsonLineFormatter

    handler.setFormatter(JsonLineFormatter())

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    try:
        if transport == "stdio":
            mcp.run()
        else:
            return 1
        return 0

    except KeyboardInterrupt:
        return 0
    except Exception as e:
        logging.error(f"MCP server error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
