"""Tests for prompt safety utilities."""

import pytest

from aria.utils.prompt_safety import (
    wrap_tool_output,
    sanitize_nested_frames,
    redact_secrets,
    FRAME_OPEN,
    FRAME_CLOSE,
)


class TestWrapToolOutput:
    """Tests for tool output wrapping."""

    def test_wraps_content(self):
        text = "Hello World"
        result = wrap_tool_output(text)
        assert result == f"{FRAME_OPEN}Hello World{FRAME_CLOSE}"

    def test_wraps_empty_string(self):
        assert wrap_tool_output("") == ""

    def test_preserves_whitespace(self):
        text = "  Hello  "
        result = wrap_tool_output(text)
        assert "  Hello  " in result


class TestSanitizeNestedFrames:
    """Tests for nested frame sanitization."""

    def test_no_frames_unchanged(self):
        text = "Hello World"
        assert sanitize_nested_frames(text) == text

    def test_removes_nested_frames(self):
        # Malicious content with nested frame
        text = f"{FRAME_OPEN}outer{FRAME_OPEN}nested{FRAME_CLOSE}content{FRAME_CLOSE}"
        result = sanitize_nested_frames(text)
        # Should remove inner frame delimiters, keep content
        assert FRAME_OPEN not in result
        assert "nested" in result
        assert "outer" in result

    def test_multiple_nested_frames(self):
        text = f"{FRAME_OPEN}a{FRAME_OPEN}b{FRAME_CLOSE}c{FRAME_CLOSE}d"
        result = sanitize_nested_frames(text)
        # All frame markers should be removed
        assert result.count(FRAME_OPEN) == 0

    def test_no_false_positives(self):
        text = "This is not a framed text"
        result = sanitize_nested_frames(text)
        # Should be unchanged
        assert "<<" not in result
        assert result == text


class TestRedactSecrets:
    """Tests for secret redaction."""

    def test_redacts_tavily_key(self):
        text = "API key is tvly-abc123defg"
        result = redact_secrets(text)
        assert "tvly-abc" not in result
        assert "***" in result

    def test_redacts_github_token(self):
        text = "Token: ghp_xxxxxxxxxxxx"
        result = redact_secrets(text)
        # Secret portion is masked; prefix preserved for traceability
        assert "xxxxxxxxxxxx" not in result
        assert "ghp_***" in result

    def test_redacts_exa_key(self):
        text = "Exa key exa-abc123456"
        result = redact_secrets(text)
        assert "***" in result

    def test_preserves_normal_text(self):
        text = "Hello World, no secrets here"
        result = redact_secrets(text)
        assert result == text

    def test_no_change_for_clean_text(self):
        assert redact_secrets("hello world") == "hello world"
