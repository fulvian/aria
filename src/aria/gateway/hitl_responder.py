"""HITL Responder — bridge between scheduler's hitl.created events and Telegram.

Consumer of the bus event `hitl.created`.
Reads the hitl_pending record, sends a Telegram message to the owner_user_id
(or the primary whitelisted user if owner is null) with an inline keyboard
(Yes / No / Later).

CallbackQuery from the inline keyboard is handled by forwarding to
HitlManager.resolve(), which publishes `hitl.resolved` upon completion.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update

if TYPE_CHECKING:
    from telegram.ext import ContextTypes

    from aria.scheduler.hitl import HitlManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Telegram message builder
# ---------------------------------------------------------------------------


def build_hitl_keyboard(hitl_id: str) -> InlineKeyboardMarkup:
    """Build the Yes / No / Later inline keyboard for a HITL request.

    Args:
        hitl_id: Opaque HITL record ID used in callback_data.

    Returns:
        InlineKeyboardMarkup with three buttons.
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"hitl:{hitl_id}:yes"),
            InlineKeyboardButton("❌ No", callback_data=f"hitl:{hitl_id}:no"),
            InlineKeyboardButton("⏸ Later", callback_data=f"hitl:{hitl_id}:later"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_hitl_message(question: str) -> str:
    """Format the HITL question as a user-facing Telegram message."""
    return f"⚠️ *ARIA — Approval Required*\n\n{question}\n\n*Approve the action above?*"


# ---------------------------------------------------------------------------
# Callback query handler
# ---------------------------------------------------------------------------

HITL_CALLBACK_PREFIX = "hitl:"


async def handle_hitl_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    hitl_manager: HitlManager,
) -> None:
    """Handle an inline keyboard callback for a HITL response.

    Parses the callback_data as ``hitl:<hitl_id>:<response>`` and
    forwards the resolution to ``hitl_manager.resolve()``.

    Args:
        update: Telegram Update object.
        context: Telegram context (unused, kept for API compatibility).
        hitl_manager: HitlManager instance to perform resolution.
    """
    query = update.callback_query
    if query is None:
        logger.warning("HITL callback with no query")
        return

    # Acknowledge immediately to avoid Telegram timeout
    await query.answer()

    callback_data = query.data or ""
    if not callback_data.startswith(HITL_CALLBACK_PREFIX):
        logger.warning("Unknown callback data prefix: %s", callback_data)
        return

    try:
        _, hitl_id, response = callback_data.split(":", 2)
    except ValueError:
        logger.warning("Malformed HITL callback_data: %s", callback_data)
        return

    # Map "yes"/"no"/"later" to the canonical response strings
    response_map = {
        "yes": "yes",
        "no": "no",
        "later": "later",
    }
    canonical = response_map.get(response)
    if canonical is None:
        logger.warning("Unknown HITL response value: %s", response)
        return

    try:
        await hitl_manager.resolve(hitl_id, canonical)
        # Acknowledge with a brief user-visible message
        await query.edit_message_text(
            text=f"✅ HITL {hitl_id} resolved: `{canonical}`",
            parse_mode="Markdown",
        )
        logger.info("HITL %s resolved with response %s", hitl_id, canonical)
    except Exception as exc:
        logger.error("Failed to resolve HITL %s: %s", hitl_id, exc)
        await query.edit_message_text(
            text=f"❌ Failed to resolve HITL: `{exc}`",
            parse_mode="Markdown",
        )


# ---------------------------------------------------------------------------
# Event consumer — hitl.created
# ---------------------------------------------------------------------------


async def on_hitl_created(
    payload: dict,
    bot_token: str,
    whitelist_primary_user_id: str,
) -> None:
    """Handle the ``hitl.created`` bus event.

    This function is registered as a subscriber to the ``hitl.created``
    event published by the scheduler's HitlManager.

    It extracts the hitl_pending details and sends a Telegram message
    to the owner_user_id (or ``whitelist_primary_user_id`` if owner is null),
    with an inline keyboard for approval.

    Args:
        payload: Event payload containing ``hitl_pending`` dict and ``question``.
        bot_token: Telegram bot token for sending messages.
        whitelist_primary_user_id: Fallback user ID when owner_user_id is null.
    """
    # Support both payload formats:
    # - legacy: {"hitl_pending": {...}, "question": "..."}
    # - scheduler event: {"hitl_id": "...", "question": "...", "owner_user_id": "..."}
    hitl_data = payload.get("hitl_pending", {})
    hitl_id = payload.get("hitl_id") or hitl_data.get("id", "unknown")
    question = payload.get("question") or hitl_data.get("question") or "No question provided."
    owner_user_id = (
        payload.get("owner_user_id") or hitl_data.get("owner_user_id") or whitelist_primary_user_id
    )

    if not owner_user_id:
        logger.error("HITL %s: no owner_user_id and no primary whitelist user", hitl_id)
        return

    keyboard = build_hitl_keyboard(hitl_id)
    text = build_hitl_message(question)

    try:
        bot = Bot(token=bot_token)
        await bot.send_message(
            chat_id=int(owner_user_id),
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        logger.info(
            "HITL notification sent to user %s for hitl_id=%s",
            owner_user_id,
            hitl_id,
        )
    except Exception as exc:
        logger.error("Failed to send HITL notification for %s: %s", hitl_id, exc)
