# Unit tests for aria.utils.logging
# Per sprint plan W1.1.A acceptance criteria

import json
import logging
import tempfile
from pathlib import Path

import pytest

from aria.utils.logging import (
    JsonLineFormatter,
    get_logger,
    get_trace_id,
    log_event,
    new_trace_id,
    redact_secret,
    set_trace_id,
    trace_id_var,
)


class TestRedactSecret:
    """Test secret redaction."""

    def test_redact_none_returns_none_string(self) -> None:
        """redact_secret(None) → '<none>'"""
        assert redact_secret(None) == "<none>"

    def test_redact_short_string(self) -> None:
        """Short strings are fully redacted."""
        result = redact_secret("abc")
        assert result == "***" or result == "*" * len("abc")

    def test_redact_long_string_keeps_last_4(self) -> None:
        """Long strings show last 4 characters."""
        result = redact_secret("sk-abc1234567")
        assert result == "***4567"

    def test_redact_key_pattern(self) -> None:
        """API key pattern is redacted."""
        result = redact_secret("sk-12345678901234567890")
        assert result == "***7890"

    def test_redact_token_pattern(self) -> None:
        """Token pattern is redacted (keeps last 4 by default)."""
        # Last 4 chars of "ghp_abcd1234efgh5678ijkl" are "ijkl"
        result = redact_secret("ghp_abcd1234efgh5678ijkl")
        assert result == "***ijkl"

    def test_redact_keep_last_custom(self) -> None:
        """Custom keep_last parameter works."""
        result = redact_secret("my_secret_key_12345", keep_last=5)
        assert result == "***12345"


class TestTraceId:
    """Test trace ID context management."""

    def test_new_trace_id_is_12_chars(self) -> None:
        """new_trace_id() returns 12 character hex string."""
        tid = new_trace_id()
        assert len(tid) == 12
        assert all(c in "0123456789abcdef" for c in tid)

    def test_new_trace_id_is_unique(self) -> None:
        """new_trace_id() generates unique IDs."""
        ids = [new_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_trace_id_context_default(self) -> None:
        """Default trace_id is '-'."""
        assert trace_id_var.get() == "-"

    def test_set_and_get_trace_id(self) -> None:
        """set_trace_id and get_trace_id work."""
        set_trace_id("test123")
        assert get_trace_id() == "test123"
        # Reset
        trace_id_var.set("-")

    def test_trace_id_propagation_in_logger(self) -> None:
        """trace_id is included in log output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            handler = logging.FileHandler(log_file)
            handler.setFormatter(JsonLineFormatter())
            logger = logging.getLogger("test_trace")
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

            set_trace_id("abc123")
            log_event(logger, logging.INFO, "test_event", key="value")

            handler.flush()
            content = log_file.read_text()
            assert "abc123" in content
            assert "test_event" in content


class TestJsonLineFormatter:
    """Test JSON line formatter."""

    def test_format_outputs_json(self) -> None:
        """format() outputs valid JSON."""
        # Reset trace_id to default
        trace_id_var.set("-")

        formatter = JsonLineFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "ts" in parsed
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert parsed["event"] == "test message"
        assert parsed["trace_id"] == "-"  # default

    def test_format_includes_context(self) -> None:
        """format() includes extra context fields."""
        formatter = JsonLineFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="event with context",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["context"]["custom_field"] == "custom_value"


class TestLogEvent:
    """Test structured log_event function."""

    def test_log_event_with_extra_context(self) -> None:
        """log_event includes extra context in output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            handler = logging.FileHandler(log_file)
            handler.setFormatter(JsonLineFormatter())
            logger = logging.getLogger("test_event")
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

            log_event(logger, logging.INFO, "user_action", user="fulvio", action="test")

            handler.flush()
            content = log_file.read_text()
            parsed = json.loads(content.strip())

            assert parsed["event"] == "user_action"
            assert parsed["context"]["user"] == "fulvio"
            assert parsed["context"]["action"] == "test"


class TestGetLogger:
    """Test logger factory."""

    def test_get_logger_returns_logger(self) -> None:
        """get_logger returns a Logger instance."""
        logger = get_logger("aria.test")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_caches_instances(self) -> None:
        """get_logger returns same instance for same name."""
        logger1 = get_logger("aria.cached_test")
        logger2 = get_logger("aria.cached_test")
        assert logger1 is logger2

    def test_get_logger_different_names(self) -> None:
        """Different names return different instances."""
        logger1 = get_logger("aria.diff1")
        logger2 = get_logger("aria.diff2")
        assert logger1 is not logger2


class TestSecretLeakPrevention:
    """Test that secrets are not leaked in logs."""

    def test_secret_in_context_is_redacted(self) -> None:
        """Secrets in context are redacted."""
        formatter = JsonLineFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        # Use a realistic secret that matches the sk- pattern (20+ chars after sk-)
        record.api_key = "sk-12345678901234567890ab"  # 22 chars after sk-

        output = formatter.format(record)
        parsed = json.loads(output)

        # The redaction should have happened - api_key should be redacted
        redacted_val = parsed["context"].get("api_key", "")
        # The value should be redacted (starting with ***)
        assert redacted_val.startswith("***")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
