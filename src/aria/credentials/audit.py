# Credential Audit Logger
#
# Logs all credential operations (acquire, report_success, report_failure).
# Per blueprint §13.6 and sprint plan W1.1.F.
#
# Format (JSON line, consistent with aria.utils.logging):
#   {"ts":"...","op":"acquire","provider":"tavily","key_id":"tvly-1",
#    "result":"ok","credits_remaining":847,"trace_id":"abc123"}
#
# Rules:
# - NEVER log KeyInfo.key (SecretStr) - only key_id
# - Retention 90 days (via log rotation)
#
# Usage:
#   from aria.credentials.audit import AuditLogger
#
#   audit = AuditLogger()
#   audit.record(
#       provider="tavily", op="acquire", key_id="tvly-1",
#       result="ok", credits_remaining=847,
#   )

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aria.utils.logging import get_logger, log_event, trace_id_var

# === Audit Logger ===


class AuditLogger:
    """Audit logger for credential operations.

    Writes JSON lines to .aria/runtime/logs/credentials-YYYY-MM-DD.log
    with structured context for each operation.

    IMPORTANT: Never logs actual key values, only key_id references.
    """

    AUDIT_LOGGER_NAME = "aria.credentials.audit"
    LOG_FILENAME_PREFIX = "credentials"

    def __init__(self, log_dir: Path | None = None) -> None:
        """Initialize audit logger.

        Args:
            log_dir: Optional custom log directory (defaults to ARIA_RUNTIME/logs)
        """
        if log_dir is None:
            import os

            aria_home = Path(os.environ.get("ARIA_HOME", "/home/fulvio/coding/aria"))
            log_dir = aria_home / ".aria" / "runtime" / "logs"

        self._log_dir = log_dir
        self._logger = get_logger(self.AUDIT_LOGGER_NAME)

    def _get_log_file_path(self, dt: datetime | None = None) -> Path:
        """Get log file path for given date."""
        if dt is None:
            dt = datetime.now(UTC)
        date_str = dt.strftime("%Y-%m-%d")
        return self._log_dir / f"{self.LOG_FILENAME_PREFIX}-{date_str}.log"

    def _write_line(self, entry: dict[str, Any]) -> None:
        """Write JSON line to audit log file."""
        # Ensure directory exists
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Get current date for filename
        log_path = self._get_log_file_path()

        # Write line
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def record(
        self,
        provider: str,
        op: str,
        key_id: str,
        result: str,
        credits_remaining: int | None = None,
        trace_id: str | None = None,
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Record a credential operation.

        Args:
            provider: Provider name (e.g., "tavily")
            op: Operation type ("acquire", "report_success", "report_failure")
            key_id: Key identifier (NOT the actual key)
            result: Result status ("ok", "error", "no_key", "cooldown")
            credits_remaining: Optional remaining credits after operation
            trace_id: Optional trace ID (uses context var if not provided)
            error: Optional error message
            extra: Optional additional context
        """
        # Get trace_id from context if not provided
        if trace_id is None:
            trace_id = trace_id_var.get()

        # Build entry
        entry: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "op": op,
            "provider": provider,
            "key_id": key_id,
            "result": result,
            "trace_id": trace_id,
        }

        # Add optional fields
        if credits_remaining is not None:
            entry["credits_remaining"] = credits_remaining

        if error:
            entry["error"] = error

        if extra:
            entry.update(extra)

        # Write to log file
        try:
            self._write_line(entry)
        except Exception as e:
            # Fall back to logger warning
            self._logger.warning(f"audit_log_write_failed: {e}")

        # Also emit to structured logger (for real-time monitoring)
        log_event(
            self._logger,
            20 if result == "ok" else 30,  # INFO for ok, WARNING otherwise
            f"cred_{op}",
            provider=provider,
            key_id=key_id,
            result=result,
            credits_remaining=credits_remaining,
            error=error,
        )

    # === Convenience methods ===

    def record_acquire(
        self,
        provider: str,
        key_id: str,
        result: str,
        credits_remaining: int | None = None,
    ) -> None:
        """Record an acquire operation."""
        self.record(
            provider=provider,
            op="acquire",
            key_id=key_id,
            result=result,
            credits_remaining=credits_remaining,
        )

    def record_success(
        self,
        provider: str,
        key_id: str,
        credits_used: int,
        credits_remaining: int | None = None,
    ) -> None:
        """Record a success report."""
        self.record(
            provider=provider,
            op="report_success",
            key_id=key_id,
            result="ok",
            credits_remaining=credits_remaining,
        )

    def record_failure(
        self,
        provider: str,
        key_id: str,
        error: str,
        cooldown: int | None = None,
    ) -> None:
        """Record a failure report."""
        self.record(
            provider=provider,
            op="report_failure",
            key_id=key_id,
            result="error",
            error=error,
        )

    def record_no_key(self, provider: str, reason: str) -> None:
        """Record that no key was available."""
        self.record(
            provider=provider,
            op="acquire",
            key_id="-",
            result="no_key",
            error=reason,
        )


# === Singleton instance ===

_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the singleton audit logger instance."""
    global _audit_logger  # noqa: PLW0603 — singleton bootstrap
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
