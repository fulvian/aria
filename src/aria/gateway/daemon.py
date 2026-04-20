# ARIA Gateway Daemon
#
# Entry point for the Gateway service that handles Telegram integration.
# Per blueprint §7 and sprint plan W1.2.L.
#
# Full daemon implementation requires integration work between:
# - TelegramAdapter (PTB 22.x)
# - Metrics server (Prometheus on 127.0.0.1:9090)
# - HitlResponder (event consumer)
# - Shared TaskStore with scheduler
#
# Usage:
#   python -m aria.gateway.daemon
#   python -m aria.gateway.daemon --check

from __future__ import annotations

import argparse
import asyncio
import logging

logger = logging.getLogger(__name__)


async def _async_main() -> int:  # noqa: PLR0915
    """Async main entry point for gateway daemon."""
    # Import here to avoid circular imports and allow --check to work without full setup
    from aria.config import get_config
    from aria.credentials import CredentialManager
    from aria.gateway.auth import AuthGuard
    from aria.gateway.hitl_responder import on_hitl_created
    from aria.gateway.metrics_server import (
        start_metrics_server,
        stop_metrics_server,
    )
    from aria.gateway.session_manager import SessionManager
    from aria.gateway.telegram_adapter import TelegramAdapter
    from aria.scheduler.hitl import HitlManager
    from aria.scheduler.notify import SdNotifier
    from aria.scheduler.store import TaskStore
    from aria.scheduler.triggers import EventBus

    config = get_config()
    logger.info("Starting ARIA Gateway daemon...")

    # Initialize components
    credential_manager = CredentialManager(config)
    auth_guard = AuthGuard(whitelist=config.telegram.whitelist)
    sessions = SessionManager(config.paths.runtime / "gateway/sessions.db")
    bus = EventBus()
    notifier = SdNotifier(watchdog_interval_s=30)

    # Initialize scheduler store for HITL (shared with scheduler)
    scheduler_db = config.paths.runtime / "scheduler/scheduler.db"
    task_store = TaskStore(scheduler_db)
    await task_store.connect()

    # Initialize HITL manager
    _hitl_manager = HitlManager(task_store, bus, config)
    # HITL responder subscribes to bus events; no further reference needed
    _ = _hitl_manager

    # Initialize Telegram adapter
    telegram_adapter = TelegramAdapter(
        cm=credential_manager,
        auth=auth_guard,
        sessions=sessions,
        bus=bus,
        config=config,
    )

    oauth = credential_manager.get_oauth("telegram", "bot")
    if oauth is None or not oauth.refresh_token:
        raise RuntimeError("Telegram bot token not available in CredentialManager")

    primary_user_id = str(config.telegram.whitelist[0]) if config.telegram.whitelist else ""

    async def _on_hitl_resolved(payload: dict[str, object]) -> None:
        hitl_id = str(payload.get("hitl_id", ""))
        response = str(payload.get("response", ""))
        if hitl_id:
            await _hitl_manager.resolve(hitl_id, response)

    async def _on_hitl_created(payload: dict[str, object]) -> None:
        await on_hitl_created(
            payload=payload,
            bot_token=oauth.refresh_token,
            whitelist_primary_user_id=primary_user_id,
        )

    bus.subscribe("hitl.resolved", _on_hitl_resolved)
    bus.subscribe("hitl.created", _on_hitl_created)

    start_metrics_server(host="127.0.0.1", port=9090)

    await notifier.start()
    logger.info("ARIA Gateway daemon started successfully")

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(notifier.run_forever())
            tg.create_task(telegram_adapter.start_polling())
    finally:
        logger.info("Shutting down ARIA Gateway daemon...")
        await notifier.stop("shutdown")
        await task_store.close()
        await sessions.close()
        stop_metrics_server()
        logger.info("ARIA Gateway daemon stopped")

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for gateway daemon."""
    parser = argparse.ArgumentParser(
        prog="python -m aria.gateway.daemon",
        description="ARIA Gateway daemon.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate CLI wiring and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for gateway daemon."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check:
        # Validate that we can import all required modules
        try:
            from aria.config import get_config
            from aria.credentials import CredentialManager
            from aria.gateway.auth import AuthGuard
            from aria.gateway.metrics_server import (
                is_metrics_server_running,
                start_metrics_server,
                stop_metrics_server,
            )
            from aria.gateway.session_manager import SessionManager
            from aria.gateway.telegram_adapter import TelegramAdapter
            from aria.scheduler.hitl import HitlManager
            from aria.scheduler.notify import SdNotifier
            from aria.scheduler.store import TaskStore
            from aria.scheduler.triggers import EventBus

            _ = (
                get_config,
                CredentialManager,
                AuthGuard,
                is_metrics_server_running,
                start_metrics_server,
                stop_metrics_server,
                SessionManager,
                TelegramAdapter,
                HitlManager,
                SdNotifier,
                TaskStore,
                EventBus,
            )
            return 0
        except ImportError as e:
            print(f"Import error: {e}", file=__import__("sys").stderr)
            return 1

    # Set up basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    try:
        return asyncio.run(_async_main())
    except KeyboardInterrupt:
        logger.info("Gateway daemon interrupted")
        return 0
    except Exception as e:
        logger.exception("Gateway daemon failed: %s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
