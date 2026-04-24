# Scheduler Notify — sd_notify watchdog integration
#
# Per blueprint §6.
#
# Provides sd_notify integration for systemd watchdog.
#
# Usage:
#   from aria.scheduler.notify import SdNotifier
#
#   notifier = SdNotifier(watchdog_interval_s=30)
#   await notifier.start()

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class SdNotifier:
    """Systemd sd_notify integration for watchdog.

    Sends WATCHDOG=1 and STATUS= updates to systemd.
    """

    def __init__(self, watchdog_interval_s: int = 30) -> None:
        """Initialize SdNotifier.

        Args:
            watchdog_interval_s: Interval to send watchdog pings
        """
        self._watchdog_interval_s = watchdog_interval_s
        self._running = False

    async def start(self) -> None:
        """Start the notifier."""
        self._running = True
        # Notify systemd that we're ready
        self._notify("READY=1\nSTATUS=ARIA Scheduler running")

    async def run_forever(self) -> None:
        """Run the watchdog loop."""
        while self._running:
            await asyncio.sleep(self._watchdog_interval_s)
            self._notify("WATCHDOG=1\nSTATUS=ARIA Scheduler alive")

    async def stop(self, reason: str = "shutdown") -> None:
        """Stop the notifier and notify systemd."""
        self._running = False
        self._notify(f"STOPPING=1\nSTATUS=ARIA Scheduler {reason}")

    def _notify(self, status: str) -> None:
        """Send sd_notify status.

        Args:
            status: Status string to send to systemd
        """
        notify_socket = os.environ.get("NOTIFY_SOCKET")
        if not notify_socket:
            logger.debug("NOTIFY_SOCKET not set, skipping sd_notify")
            return

        try:
            import socket

            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.sendto(status.encode(), notify_socket)
            sock.close()
            logger.debug("sd_notify sent: %s", status.split("\n")[0])
        except Exception as e:
            logger.warning("Failed to send sd_notify: %s", e)
