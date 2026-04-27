# ARIA Memory MCP Server
#
# FastMCP 3.x server exposing 10 memory tools (Phase D — legacy tools removed).
# Per blueprint §5.6, plan §9 Phase D, ADR-0005.
#
# Wiki tools (4):
#   wiki_update, wiki_recall, wiki_show, wiki_list
#   (registered via wiki/tools.py)
#
# Legacy bridge tools (2):
#   forget — HITL-gated soft delete (bridge, Phase E will migrate)
#   stats — memory telemetry (includes wiki.db stats)
#
# HITL tools (4):
#   hitl_ask, hitl_list_pending, hitl_cancel, hitl_approve
#
# Removed in Phase D (2026-04-27): remember, complete_turn, recall,
# recall_episodic, distill, curate. See ADR-0005.
#
# Transport: stdio (configurable via ARIA_MEMORY_MCP_TRANSPORT)
#
# Usage:
#   python -m aria.memory.mcp_server

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastmcp import FastMCP

from aria.config import get_config
from aria.memory.episodic import EpisodicStore, create_episodic_store
from aria.utils.logging import new_trace_id, set_trace_id

# === FastMCP Setup ===

mcp = FastMCP("aria-memory")

# Global state (initialized on first tool call)
_store: EpisodicStore | None = None
_config = None


async def _ensure_store() -> EpisodicStore:
    """Ensure episodic store is initialized (lazy init)."""
    global _store, _config  # noqa: PLW0603

    if _store is None:
        _config = get_config()
        _store = await create_episodic_store(_config)

    return _store


# === MCP Tools ===


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
        store = await _ensure_store()
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
        store = await _ensure_store()

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
        store = await _ensure_store()
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
        store = await _ensure_store()
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
        store = await _ensure_store()
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
        store = await _ensure_store()
        # Import semantic store only for forget_semantic action
        from aria.memory.semantic import SemanticStore

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

            semantic = SemanticStore(store._db_path, get_config())
            await semantic.connect(conn)
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


# === Wiki v3 Tools Registration ===
#
# Per docs/plans/auto_persistence_echo.md §7:
# Register 4 new wiki tools alongside existing 11 memory tools.
# Phase A: pure addition, old tools still active.


def _register_wiki_tools() -> None:
    """Register wiki MCP tools on the existing server."""
    from aria.memory.wiki.tools import register_wiki_tools

    register_wiki_tools(mcp)


# Register wiki tools at import time (non-breaking addition)
_register_wiki_tools()


async def _regenerate_conductor_template_on_boot() -> None:
    """Regenerate conductor template with profile on MCP server boot.

    Per plan §6.1: on boot, read profile from wiki.db and write
    the memory block into the active conductor agent template.
    Runs as background task — does not block tool registration.
    """
    try:
        from aria.memory.wiki.db import WikiStore
        from aria.memory.wiki.prompt_inject import regenerate_conductor_template

        aria_home = Path(os.environ.get("ARIA_HOME", "/home/fulvio/coding/aria"))
        db_path = aria_home / ".aria" / "runtime" / "memory" / "wiki.db"
        store = WikiStore(db_path)
        await store.connect()
        try:
            await regenerate_conductor_template(store)
        finally:
            await store.close()
    except Exception as exc:
        logging.getLogger(__name__).warning("Boot-time template regeneration skipped: %s", exc)


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
            # Regenerate conductor template with profile on boot
            import asyncio

            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(_regenerate_conductor_template_on_boot())
                loop.close()
            except Exception as boot_exc:
                logging.warning("Template regeneration on boot failed: %s", boot_exc)

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
