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
    if not text or len(text.strip()) == 0:
        return False
    # Add more validation as needed
    return True


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


def sanitize_nested_frames(frames: list[dict]) -> list[dict]:
    """Sanitize nested trace frames.

    Args:
        frames: List of trace frames

    Returns:
        Sanitized frames
    """
    # Stub implementation
    return frames


def wrap_tool_output(output: str) -> str:
    """Wrap tool output for safe display.

    Args:
        output: The tool output to wrap

    Returns:
        Wrapped output
    """
    # Stub implementation
    return output
