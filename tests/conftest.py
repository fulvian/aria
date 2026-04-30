from __future__ import annotations

import sys
from pathlib import Path

from aiosqlite import core as aiosqlite_core

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _patched_connection_worker_thread(tx: aiosqlite_core._TxQueue) -> None:
    """Test-only shim for late aiosqlite callbacks on closed loops.

    Under pytest teardown, some fully-awaited connection operations can still
    race with event-loop shutdown and emit `PytestUnhandledThreadExceptionWarning`
    from `future.get_loop().call_soon_threadsafe(...)`. In tests we treat those
    late callbacks as benign once the target loop is already closed.
    """

    while True:
        future, function = tx.get()

        try:
            aiosqlite_core.LOG.debug("executing %s", function)
            result = function()

            if future:
                try:
                    future.get_loop().call_soon_threadsafe(
                        aiosqlite_core.set_result,
                        future,
                        result,
                    )
                except RuntimeError as exc:
                    if "closed" not in str(exc).lower():
                        raise
            aiosqlite_core.LOG.debug("operation %s completed", function)

            if result is aiosqlite_core._STOP_RUNNING_SENTINEL:
                break

        except BaseException as exc:  # noqa: B036
            aiosqlite_core.LOG.debug("returning exception %s", exc)
            if future:
                try:
                    future.get_loop().call_soon_threadsafe(
                        aiosqlite_core.set_exception,
                        future,
                        exc,
                    )
                except RuntimeError as loop_exc:
                    if "closed" not in str(loop_exc).lower():
                        raise


aiosqlite_core._connection_worker_thread = _patched_connection_worker_thread
