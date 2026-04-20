# ARIA Gateway — Telegram Adapter
#
# PTB 22.x async Telegram bot adapter.
# Per blueprint §7.1-7.4 and sprint plan W1.2.J.
#
# PTB 22.x invariants:
#   - Use Application class (NOT Updater)
#   - All handlers async def
#   - No Updater.idle() — use asyncio.Event on SIGTERM
#   - No secrets in CallbackQuery.data (64 byte max)
#   - Whitelist check FIRST, before any download

from __future__ import annotations

import asyncio
import signal
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

if TYPE_CHECKING:
    from aria.config import AriaConfig
    from aria.credentials import CredentialManager
    from aria.gateway.auth import AuthGuard
    from aria.gateway.session_manager import SessionManager

from aria.utils.logging import get_logger

logger = get_logger(__name__)

# === Rate Limiter (in-memory token bucket) ===

RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 30  # messages per window


class RateLimiter:
    """Per-user rate limiter using token bucket algorithm."""

    def __init__(
        self,
        max_messages: int = RATE_LIMIT_MAX,
        window_seconds: int = RATE_LIMIT_WINDOW,
    ) -> None:
        self._max = max_messages
        self._window = window_seconds
        self._buckets: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        """Check if user is within rate limit.

        Args:
            user_id: Telegram user ID.

        Returns:
            True if allowed, False if rate limited.
        """
        now = asyncio.get_event_loop().time()
        bucket = self._buckets[user_id]

        # Remove old timestamps outside the window
        cutoff = now - self._window
        bucket[:] = [ts for ts in bucket if ts > cutoff]

        # Check limit
        if len(bucket) >= self._max:
            return False

        # Add current timestamp
        bucket.append(now)
        return True

    def clear(self) -> None:
        """Clear all rate limit data."""
        self._buckets.clear()


# === HITL Responder (inline keyboard + callback) ===

HITL_PAYLOAD_TEMPLATE = "hitl:{hitl_id}:{response}"
MAX_CALLBACK_DATA = 64  # Telegram callback_data max bytes


def build_hitl_keyboard(hitl_id: str) -> InlineKeyboardMarkup:
    """Build HITL approval inline keyboard.

    Args:
        hitl_id: Opaque HITL pending ID.

    Returns:
        InlineKeyboardMarkup with yes/no/later buttons.
    """
    yes_payload = HITL_PAYLOAD_TEMPLATE.format(hitl_id=hitl_id, response="yes")
    no_payload = HITL_PAYLOAD_TEMPLATE.format(hitl_id=hitl_id, response="no")
    later_payload = HITL_PAYLOAD_TEMPLATE.format(hitl_id=hitl_id, response="later")

    # Ensure payloads don't exceed 64 bytes
    for payload in (yes_payload, no_payload, later_payload):
        assert len(payload.encode()) <= MAX_CALLBACK_DATA, f"Payload too long: {payload}"

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="✅ Yes", callback_data=yes_payload),
                InlineKeyboardButton(text="❌ No", callback_data=no_payload),
                InlineKeyboardButton(text="⏸ Later", callback_data=later_payload),
            ]
        ]
    )


# === Event Bus (minimal in-process) ===


class EventBus:
    """Minimal async event bus for gateway internal events."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[callable] | asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def publish(self, event: str, payload: dict[str, Any]) -> None:
        """Publish event to all subscribers.

        Args:
            event: Event name.
            payload: Event payload data.
        """
        async with self._lock:
            callbacks = self._subscribers.get(event, [])
            for callback in callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback(payload)
                elif isinstance(callback, asyncio.Event):
                    callback.set()

    def subscribe(self, event: str, callback: callable) -> None:
        """Subscribe to an event.

        Args:
            event: Event name.
            callback: Async callback function.
        """
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(callback)


# === Telegram Adapter ===

# Download limits
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # 20MB
HTTP_TIMEOUT_SECONDS = 30


class TelegramAdapter:
    """Telegram gateway adapter using PTB 22.x async.

    Per blueprint §7.1-7.4 and sprint plan W1.2.J.

    Attributes:
        app: The PTB Application instance (available after build_app).
    """

    def __init__(
        self,
        cm: CredentialManager,
        auth: AuthGuard,
        sessions: SessionManager,
        bus: EventBus,
        config: AriaConfig,
    ) -> None:
        """Initialize Telegram adapter.

        Args:
            cm: CredentialManager for API access.
            auth: AuthGuard for whitelist enforcement.
            sessions: SessionManager for session persistence.
            bus: EventBus for internal event publishing.
            config: AriaConfig for settings.
        """
        self._cm = cm
        self._auth = auth
        self._sessions = sessions
        self._bus = bus
        self._config = config
        self._rate_limiter = RateLimiter()
        self._app: Application | None = None
        self._shutdown_event = asyncio.Event()
        self._token: str | None = None

    async def build_app(self) -> Application:
        """Build PTB Application with handlers registered.

        Returns:
            Configured Application instance.
        """
        # Acquire bot token from CredentialManager via OAuth/keyring (not API key rotation)
        oauth = self._cm.get_oauth("telegram", "bot")
        if oauth is None or not oauth.refresh_token:
            raise RuntimeError("Telegram bot token not available in CredentialManager")
        self._token = oauth.refresh_token

        app = (
            Application.builder()
            .token(self._token)
            .read_timeout(HTTP_TIMEOUT_SECONDS)
            .write_timeout(HTTP_TIMEOUT_SECONDS)
            .build()
        )

        # Register handlers
        app.add_handler(CommandHandler("start", self._handle_start, filters.ChatType.PRIVATE))
        app.add_handler(CommandHandler("help", self._handle_help, filters.ChatType.PRIVATE))
        app.add_handler(CommandHandler("status", self._handle_status, filters.ChatType.PRIVATE))
        app.add_handler(CommandHandler("run", self._handle_run, filters.ChatType.PRIVATE))

        # Text message handler (echo for Sprint 1.2, publishes gateway.user_message)
        app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                self._handle_text,
            )
        )

        # Photo handler
        app.add_handler(
            MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, self._handle_photo)
        )

        # Voice/Audio handler
        app.add_handler(
            MessageHandler(
                filters.VOICE | filters.AUDIO & filters.ChatType.PRIVATE,
                self._handle_voice,
            )
        )

        # CallbackQuery handler (HITL responses)
        app.add_handler(CallbackQueryHandler(self._handle_callback, block=True))

        # Store app reference
        self._app = app
        return app

    async def start_polling(self) -> None:
        """Start polling loop (for daemon integration).

        Sets up SIGTERM/SIGINT handlers and runs until shutdown.
        """
        if self._app is None:
            await self.build_app()

        # Initialize application
        await self._app.initialize()
        await self._app.start()

        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()

        def signal_handler() -> None:
            logger.info("Received shutdown signal, stopping Telegram adapter...")
            self._shutdown_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)

        logger.info("Telegram adapter started, polling...")

        # Wait for shutdown signal
        try:
            await self._shutdown_event.wait()
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the PTB application gracefully."""
        if self._app is not None:
            logger.info("Stopping Telegram adapter...")
            await self._app.stop()
            await self._app.shutdown()
            logger.info("Telegram adapter stopped")

    # === Handler Implementations ===

    async def _whitelist_check(self, update: Update) -> bool:
        """Check if user is whitelisted. Silently discard if not.

        Args:
            update: PTB Update.

        Returns:
            True if user is whitelisted, False otherwise.
        """
        user_id = update.effective_user.id if update.effective_user else None
        if user_id is None:
            logger.warning("Update without user_id, discarding")
            return False

        # Logged by auth.is_allowed_telegram_user, silently discard
        return self._auth.is_allowed_telegram_user(user_id)

    async def _get_session(self, update: Update) -> Any:  # noqa: ANN401
        """Get or create gateway session for user."""
        user = update.effective_user
        if user is None:
            return None

        session = await self._sessions.get_or_create(
            channel="telegram",
            external_user_id=str(user.id),
            locale=getattr(user, "language_code", "it-IT") or "it-IT",
        )
        await self._sessions.touch(session.id)
        return session

    async def _handle_start(self, update: Update, context: Any) -> None:  # noqa: ANN401
        """Handle /start command."""
        if not await self._whitelist_check(update):
            return

        session = await self._get_session(update)
        user = update.effective_user

        await update.message.reply_text(
            f"Ciao {user.first_name}! 👋\n\n"
            "Sono ARIA, il tuo assistente personale.\n"
            "Usa /help per vedere i comandi disponibili.",
            parse_mode=ParseMode.HTML,
        )
        logger.info("User %s started session %s", user.id, session.id if session else None)

    async def _handle_help(self, update: Update, context: Any) -> None:  # noqa: ANN401
        """Handle /help command."""
        if not await self._whitelist_check(update):
            return

        await update.message.reply_text(
            "*Comandi disponibili:*\n\n"
            "📋 `/status` — Stato del sistema\n"
            "▶️ `/run <task_id>` — Avvia un task manuale\n"
            "📝 Invia un messaggio — Lo inoltro ad ARIA\n"
            "🖼️ Invia una foto — Analisi OCR\n"
            "🎤 Invia un messaggio vocale — Trascrizione\n\n"
            "Usa /help per maggiori informazioni.",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def _handle_status(self, update: Update, context: Any) -> None:  # noqa: ANN401
        """Handle /status command."""
        if not await self._whitelist_check(update):
            return

        # Basic status - extend in later sprints
        active_sessions = await self._sessions.list_active()
        await update.message.reply_text(
            f"*ARIA Gateway Status*\n\n"
            f"🟢 Online\n"
            f"📊 Sessioni attive: {len(active_sessions)}\n"
            f"⏰ Timestamp: {datetime.now(tz=UTC).isoformat()}",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def _handle_run(self, update: Update, context: Any) -> None:  # noqa: ANN401
        """Handle /run <task_id> — trigger manual scheduler task.

        Per sprint plan: publishes scheduler.task.run event.
        """
        if not await self._whitelist_check(update):
            return

        if not context.args:
            await update.message.reply_text("Usage: /run <task_id>")
            return

        task_id = context.args[0].strip()
        logger.info(
            "Manual task trigger requested: %s by user %s",
            task_id,
            update.effective_user.id,
        )

        # Publish event for scheduler to pick up (Sprint 1.3 integration)
        await self._bus.publish(
            "scheduler.task.run",
            {"task_id": task_id, "triggered_by": update.effective_user.id},
        )

        await update.message.reply_text(f"✅ Task `/run {task_id}` inoltrato allo scheduler.")

    async def _handle_text(self, update: Update, context: Any) -> None:  # noqa: ANN401
        """Handle incoming text messages.

        In Sprint 1.2: echo handler (publishes gateway.user_message event).
        In Sprint 1.3: wires to conductor consumer.
        """
        if not await self._whitelist_check(update):
            return

        # Rate limit check
        user_id = update.effective_user.id
        if not self._rate_limiter.is_allowed(user_id):
            await update.message.reply_text("⏳ Troppi messaggi. Riprova tra un minuto.")
            logger.warning("Rate limit exceeded for user %d", user_id)
            return

        session = await self._get_session(update)
        text = update.message.text

        # Log for debugging
        logger.debug(
            "Text message from user %d session %s: %s",
            user_id,
            session.id if session else None,
            text[:50],
        )

        # Publish event for conductor (Sprint 1.3 real integration)
        await self._bus.publish(
            "gateway.user_message",
            {
                "session_id": session.id if session else None,
                "user_id": user_id,
                "text": text,
                "locale": session.locale if session else "it-IT",
            },
        )

        # In Sprint 1.2, echo back as confirmation
        await update.message.reply_text(f"📨 Ricevuto: {text[:100]}...")

    async def _handle_photo(self, update: Update, context: Any) -> None:  # noqa: ANN401
        """Handle photo messages — download and process OCR.

        Per sprint plan W1.2.K: OCR via multimodal.py (pytesseract).
        """
        if not await self._whitelist_check(update):
            return

        user_id = update.effective_user.id

        # Get largest photo
        photo = update.message.photo[-1]
        file_size = photo.file_size or 0

        if file_size > MAX_DOWNLOAD_BYTES:
            await update.message.reply_text("❌ Immagine troppo grande (max 20MB)")
            return

        # Download to temp file
        tmp_dir = self._config.paths.runtime / "tmp" / "gateway"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=str(tmp_dir),
            delete=True,
            suffix=".jpg",
        ) as tmp:
            tmp_path = Path(tmp.name)

            await context.bot.download(photo.file_id, tmp_path)

            # Process OCR via multimodal
            try:
                from aria.gateway.multimodal import ocr_image

                text = await ocr_image(tmp_path)
                logger.info("OCR result for user %d: %s", user_id, text[:100])

                await update.message.reply_text(f"📄 OCR result:\n\n{text[:500]}")
            except Exception as e:
                logger.error("OCR failed for user %d: %s", user_id, e)
                await update.message.reply_text(f"❌ OCR failed: {e}")

    async def _handle_voice(self, update: Update, context: Any) -> None:  # noqa: ANN401
        """Handle voice messages — download and process STT.

        Per sprint plan W1.2.K: STT via multimodal.py (faster-whisper).
        """
        if not await self._whitelist_check(update):
            return

        user_id = update.effective_user.id

        voice = update.message.voice
        file_size = voice.file_size or 0

        if file_size > MAX_DOWNLOAD_BYTES:
            await update.message.reply_text("❌ File audio troppo grande (max 20MB)")
            return

        # Download to temp file
        tmp_dir = self._config.paths.runtime / "tmp" / "gateway"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=str(tmp_dir),
            delete=True,
            suffix=".ogg",
        ) as tmp:
            tmp_path = Path(tmp.name)

            await context.bot.download(voice.file_id, tmp_path)

            # Process STT via multimodal
            try:
                from aria.gateway.multimodal import transcribe_audio

                text = await transcribe_audio(tmp_path)
                logger.info("STT result for user %d: %s", user_id, text[:100])

                await update.message.reply_text(f"🎤 Transcribed:\n\n{text[:500]}")
            except Exception as e:
                logger.error("STT failed for user %d: %s", user_id, e)
                await update.message.reply_text(f"❌ Transcription failed: {e}")

    async def _handle_callback(self, update: Update, context: Any) -> None:  # noqa: ANN401
        """Handle CallbackQuery from inline keyboard (HITL responses).

        Payload format: hitl:<id>:yes|no|later
        Resolves HITL via hitl.resolve().
        """
        query = update.callback_query
        if query is None:
            return

        user_id = query.from_user.id

        # Whitelist check
        if not self._auth.is_allowed_telegram_user(user_id):
            await query.answer("Unauthorized", show_alert=True)
            return

        # Parse callback data
        data = query.data or ""
        parts = data.split(":", 2)

        if len(parts) != 3 or parts[0] != "hitl":
            logger.warning("Unknown callback data from user %d: %s", user_id, data)
            await query.answer("Unknown request", show_alert=True)
            return

        _prefix, hitl_id, response = parts

        if response not in ("yes", "no", "later"):
            await query.answer("Invalid response", show_alert=True)
            return

        logger.info(
            "HITL response from user %d: hitl_id=%s response=%s",
            user_id,
            hitl_id,
            response,
        )

        # Resolve HITL via bus event
        await self._bus.publish(
            "hitl.resolved",
            {"hitl_id": hitl_id, "response": response, "user_id": user_id},
        )

        # Answer callback
        await query.answer(f"Response recorded: {response}", show_alert=True)

        # Edit message to show acknowledgment
        await query.edit_message_text(
            text=f"✅ Risposta registrata: `{response}`\n\n"
            "Lo scheduler elaborerà la tua decisione.",
            parse_mode=ParseMode.MARKDOWN,
        )

    @property
    def app(self) -> Application | None:
        """Get the PTB Application instance."""
        return self._app


# === Stub Event Bus for standalone use ===


class StubEventBus:
    """Stub event bus for when SessionManager is used standalone."""

    def __init__(self) -> None:
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)

    async def publish(self, event: str, payload: dict[str, Any]) -> None:
        """Store event for inspection (testing)."""
        self._events[event].append(payload)
        logger.debug("Event published: %s", event)

    def subscribe(self, event: str, callback: callable) -> None:
        """No-op in stub."""
        pass

    def get_events(self, event: str) -> list[dict[str, Any]]:
        """Get published events (for testing)."""
        return self._events.get(event, [])
