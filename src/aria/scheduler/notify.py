"""sd_notify integration for systemd watchdog."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sd_notify


class SdNotifier:
    """Systemd watchdog notifier using sd_notify protocol.

    Sends watchdog pings to systemd at regular intervals. If NOTIFY_SOCKET
    is not set, operates as no-op for local development.

    Args:
        watchdog_interval_s: Interval between WATCHDOG=1 pings in seconds.
    """

    def __init__(self, watchdog_interval_s: int = 30) -> None:
        self._interval_s = watchdog_interval_s
        self._notify: sd_notify.Notifier | None = None
        self._enabled = False
        self._stopping = False

    async def start(self) -> None:
        """Send READY=1 to systemd to indicate service startup complete."""
        import sd_notify

        self._notify = sd_notify.Notifier()
        self._enabled = self._notify.enabled()

        if self._enabled:
            self._notify.ready()

    async def ping(self) -> None:
        """Send WATCHDOG=1 to systemd to reset watchdog timer."""
        if self._enabled and self._notify and not self._stopping:
            self._notify.notify()

    async def stop(self, reason: str = "") -> None:
        """Send STOPPING=1 to systemd to indicate graceful shutdown.

        Args:
            reason: Optional reason for stopping (appended as COMMENT=).
        """
        self._stopping = True
        if self._enabled and self._notify:
            # Build STOPPING message
            msg = "STOPPING=1"
            if reason:
                msg += f"\nCOMMENT={reason}"
            # Use socket directly to send custom message
            self._notify.socket.sendto(msg.encode(), self._notify.address)

    async def run_forever(self) -> None:
        """Run background ping loop until stopped.

        Pings systemd every watchdog_interval_s seconds to reset the watchdog timer.
        Uses non-blocking asyncio.sleep between pings.
        """
        if not self._enabled:
            # In dev mode without NOTIFY_SOCKET, just wait for stop signal
            try:
                while not self._stopping:  # noqa: ASYNC110
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            return

        try:
            while not self._stopping:
                await asyncio.sleep(self._interval_s)
                if not self._stopping:
                    await self.ping()
        except asyncio.CancelledError:
            pass
