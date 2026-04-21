"""Tests for prompt safety framing and sanitization."""

from aria.utils.prompt_safety import (
    FRAME_CLOSE,
    FRAME_OPEN,
    extract_framed_output,
    redact_secrets,
    sanitize_nested_frames,
    wrap_tool_output,
)


def test_wrap_tool_output_uses_expected_delimiters():
    wrapped = wrap_tool_output("payload")
    assert wrapped == f"{FRAME_OPEN}payload{FRAME_CLOSE}"


def test_sanitize_nested_frames_strips_inner_frames():
    nested = f"safe {FRAME_OPEN}inner{FRAME_CLOSE} content"
    cleaned = sanitize_nested_frames(nested)
    assert FRAME_OPEN not in cleaned
    assert FRAME_CLOSE not in cleaned
    assert "inner" in cleaned


def test_extract_framed_output_returns_inner_content():
    text = f"prefix {FRAME_OPEN}hello{FRAME_CLOSE} suffix"
    assert extract_framed_output(text) == "hello"


def test_redact_secrets_masks_known_prefixes():
    text = "token sk-ABCDEF123456 and ghp_ZYXWVUT98765"
    redacted = redact_secrets(text)
    assert "sk-***" in redacted
    assert "ghp_***" in redacted
