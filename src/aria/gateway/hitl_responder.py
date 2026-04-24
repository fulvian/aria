# HITL Responder — Handles HITL notifications
#
# Stub implementation for HITL response handling.
#
# Usage:
#   from aria.gateway.hitl_responder import on_hitl_created
#
#   await on_hitl_created(payload, bot_token, whitelist_primary_user_id)

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def on_hitl_created(
    payload: dict,
    bot_token: str,
    whitelist_primary_user_id: str,
) -> None:
    """Handle HITL created event.

    Args:
        payload: Event payload with hitl_id, target_id, action
        bot_token: Telegram bot token
        whitelist_primary_user_id: Primary user ID for notifications
    """
    hitl_id = payload.get("hitl_id", "unknown")
    target_id = payload.get("target_id", "unknown")
    action = payload.get("action", "unknown")

    logger.info(
        "HITL created: id=%s target=%s action=%s (stub - would send Telegram message)",
        hitl_id,
        target_id,
        action,
    )
    # In full implementation, this would send a Telegram message to the user
    # asking them to approve or reject the action
