"""
Prompt injection mitigation utilities per blueprint §14.3 and ADR-0006.

Provides:
1. Frame wrapping: <<TOOL_OUTPUT>>...<</TOOL_OUTPUT>>
2. Nested frame sanitization
3. Secret redaction for logs

IMPORTANT: The frame delimiters <<TOOL_OUTPUT>> and <</TOOL_OUTPUT>> are used
to encapsulate tool outputs before injecting into the Conductor's system prompt.
The Conductor system prompt explicitly forbids executing any instructions
found inside tool outputs.
"""

from __future__ import annotations

import re

# Frame delimiters per ADR-0006
FRAME_OPEN = "<<TOOL_OUTPUT>>"
FRAME_CLOSE = "<</TOOL_OUTPUT>>"

# Pattern to detect nested frames (prevent TOCTOU attacks)
NESTED_FRAME_PATTERN = re.compile(
    rf"\{re.escape(FRAME_OPEN)}\s*.+?\{re.escape(FRAME_CLOSE)}\s*",
    re.DOTALL,
)


def wrap_tool_output(text: str) -> str:
    """Wrap text in tool output frame per ADR-0006.

    Args:
        text: Raw tool output text.

    Returns:
        Text wrapped in frame delimiters.
    """
    if not text:
        return ""
    return f"{FRAME_OPEN}{text}{FRAME_CLOSE}"


def sanitize_nested_frames(text: str) -> str:
    """Remove any nested <<TOOL_OUTPUT>> frames from text.

    This prevents TOCTOU (time-of-check-time-of-use) attacks where
    a malicious tool output could contain frame delimiters to trick
    the Conductor into treating nested content as safe.

    Args:
        text: Text that may contain nested frames.

    Returns:
        Text with nested frames removed.
    """
    if FRAME_OPEN not in text:
        return text

    # Remove any nested frame delimiters
    # Strategy: find the outermost frame and keep content intact,
    # then strip any inner frames that appear in the content
    result = text

    # Keep stripping nested frames until none remain
    while True:
        match = NESTED_FRAME_PATTERN.search(result)
        if not match:
            break
        # Replace nested frame with just its content
        inner = match.group(0)
        # Extract content between the inner delimiters
        inner_content = inner[len(FRAME_OPEN) : -len(FRAME_CLOSE)].strip()
        result = result.replace(inner, inner_content, 1)

    return result


def extract_framed_output(text: str) -> str | None:
    """Extract content from a tool output frame.

    Args:
        text: Text that may contain a framed tool output.

    Returns:
        Extracted content or None if no valid frame found.
    """
    if FRAME_OPEN not in text:
        return None

    # Find the outermost frame
    start = text.find(FRAME_OPEN)
    end = text.find(FRAME_CLOSE, start + len(FRAME_OPEN))

    if end == -1:
        return None

    # Extract content between delimiters
    content = text[start + len(FRAME_OPEN) : end]

    # Sanitize any nested frames
    return sanitize_nested_frames(content)


# Redaction patterns for secret detection
SECRET_PATTERNS = [
    (re.compile(r"\b(sk-|ghp_|exa-|tvly-|fc-|BSA-)[a-zA-Z0-9]{8,}\b"), r"\1***"),
    (re.compile(r"\b(aria_)[a-zA-Z0-9_]{8,}\b"), r"\1***"),
    (re.compile(r"\b(BEARER |TOKEN )[a-zA-Z0-9_.-]{8,}\b"), r"\1***"),
]


def redact_secrets(text: str) -> str:
    """Redact API keys and tokens from text for safe logging.

    Replaces detected secrets with masked versions showing only last 3 chars.

    Args:
        text: Text that may contain secrets.

    Returns:
        Text with secrets redacted.
    """
    result = text
    for pattern, replacement in SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result
