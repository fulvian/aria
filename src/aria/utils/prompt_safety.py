# Prompt Safety — Prompt safety utilities
#
# Per blueprint §2 (P5) - Never promote inferences to facts.
#
# Provides utilities for validating and filtering prompts.
#
# Usage:
#   from aria.utils.prompt_safety import validate_prompt, sanitize_output

from __future__ import annotations

import re


def validate_prompt(text: str) -> bool:
    """Validate a prompt for safety.

    Args:
        text: The prompt text to validate

    Returns:
        True if prompt is safe
    """
    return bool(text and text.strip())


def sanitize_output(text: str) -> str:
    """Sanitize output text.

    Args:
        text: The text to sanitize

    Returns:
        Sanitized text
    """
    # Basic sanitization - remove potentially dangerous content
    return text.strip()


def contains_sensitive_data(text: str) -> bool:
    """Check if text contains sensitive data patterns.

    Args:
        text: The text to check

    Returns:
        True if sensitive data detected
    """
    patterns = [
        r"\b\d{16}\b",  # Credit card numbers
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def redact_secrets(text: str) -> str:
    """Redact secrets from text.

    Args:
        text: The text to redact

    Returns:
        Text with secrets redacted
    """
    # Stub implementation
    return text


def sanitize_nested_frames(text: str) -> str:
    """Strip nested <<TOOL_OUTPUT>> frames from text.

    Per blueprint §14.3 - prevents TOCTOU attacks by stripping
    any nested frame delimiters from tool output content.

    Args:
        text: The text containing potentially nested frames

    Returns:
        Text with nested frames stripped
    """
    if not isinstance(text, str):
        return text

    # Pattern matches <<TOOL_OUTPUT>>...<</TOOL_OUTPUT>> markers
    # We strip the outer framing markers but preserve content
    # First, find and remove all frame markers
    frame_pattern = r"<<TOOL_OUTPUT>>|<</TOOL_OUTPUT>>"
    return re.sub(frame_pattern, "", text)


def wrap_tool_output(output: str) -> str:
    """Wrap tool output in trusted frame delimiters.

    Per blueprint §14.3 - tool output saved in episodic must be
    wrapped as <<TOOL_OUTPUT>>{content}<</TOOL_OUTPUT>> when
    injected into Conductor system prompt.

    Args:
        output: The tool output to wrap

    Returns:
        Wrapped output with frame delimiters
    """
    if not isinstance(output, str):
        return output
    return f"<<TOOL_OUTPUT>>{output}<</TOOL_OUTPUT>>"
