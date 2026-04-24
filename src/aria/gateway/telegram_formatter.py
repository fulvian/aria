"""Telegram message formatting utilities.

Converts CommonMark-style Markdown to Telegram-compatible HTML and splits
long messages into chunks that fit within Telegram's 4096-character limit.

Only standard-library ``re`` is used — no external markdown parsers.
"""

from __future__ import annotations

import re

# Telegram message length cap
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

# Regex matching Telegram-safe HTML tags (opening and closing)
_SAFE_TAG_RE = re.compile(r"(</?(?:b|i|code|pre|a)(?:\s[^>]*)?>)")


def markdown_to_telegram_html(text: str) -> str:
    """Convert CommonMark-style Markdown to Telegram-compatible HTML.

    Processing order matters:
      1. Extract and protect fenced code blocks (```)
      2. Escape HTML entities outside code blocks
      3. Convert headings, bold, italic, inline code, links, bullets
      4. Reinsert code blocks

    Args:
        text: Raw Markdown text (may already contain some HTML tags).

    Returns:
        Telegram-compatible HTML string.
    """
    if not text:
        return ""

    # --- Step 1: Extract fenced code blocks and replace with placeholders ---
    code_blocks: list[str] = []
    placeholder_prefix = "\x00CODEBLOCK_"

    def _extract_code_block(match: re.Match[str]) -> str:
        code = match.group(1)  # the code content (without fences)
        block_idx = len(code_blocks)
        code_blocks.append(f"<pre>{code}</pre>")
        return f"{placeholder_prefix}{block_idx}\x00"

    # Match ```lang\n...\n``` — DOTALL so . matches newlines
    fenced_re = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)
    text = fenced_re.sub(_extract_code_block, text)

    # --- Step 2: Escape HTML entities (but preserve existing safe HTML tags) ---
    def _escape_outside_tags(line: str) -> str:
        """Escape < > & only when they are NOT part of a known safe HTML tag."""
        parts = _SAFE_TAG_RE.split(line)
        result_parts: list[str] = []
        for part in parts:
            if _SAFE_TAG_RE.fullmatch(part):
                # This is a known safe tag — keep as-is
                result_parts.append(part)
            else:
                # Escape HTML entities
                escaped = part.replace("&", "&amp;")
                escaped = escaped.replace("<", "&lt;")
                escaped = escaped.replace(">", "&gt;")
                result_parts.append(escaped)
        return "".join(result_parts)

    lines = text.split("\n")
    escaped_lines = [_escape_outside_tags(line) for line in lines]
    text = "\n".join(escaped_lines)

    # --- Step 3: Convert Markdown constructs ---

    # Headings: ## Title → <b>Title</b> (h1-h6 all become bold)
    text = re.sub(r"^#{1,6}\s+(.+?)(?:\s+#+)?\s*$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # Bold: **text** → <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # Italic: *text* → <i>text</i> (but not within ** or at line start as bullet)
    # Negative lookbehind/ahead to avoid matching **bold**
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)

    # Inline code: `text` → <code>text</code>
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Links: [text](url) → <a href="url">text</a>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # Bullet lists: "- item" or "* item" → "• item"
    # Only at line start, not ** bold ** (already converted above)
    text = re.sub(r"^[*\-]\s+", "• ", text, flags=re.MULTILINE)

    # --- Step 4: Reinsert fenced code blocks ---
    for block_idx, block in enumerate(code_blocks):
        placeholder = f"{placeholder_prefix}{block_idx}\x00"
        text = text.replace(placeholder, block)

    # Clean up any remaining null chars
    return text.replace("\x00", "")


def split_telegram_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message into chunks that fit Telegram's message size limit.

    Tries to split at paragraph boundaries (``\\n\\n``), then at newlines (``\\n``),
    then hard-splits if no break is possible.

    Args:
        text: The full text to split.
        max_length: Maximum characters per chunk (default: 4096).

    Returns:
        List of text chunks, each ≤ max_length characters.
    """
    if not text:
        return []

    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []

    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        search_region = text[:max_length]

        # Prefer double newline — split at the \n\n boundary
        last_para = search_region.rfind("\n\n")
        if last_para >= 0:
            split_pos = last_para
        else:
            # Then single newline
            last_nl = search_region.rfind("\n")
            if last_nl >= 0:
                split_pos = last_nl
            else:
                # Then space
                last_space = search_region.rfind(" ")
                split_pos = last_space if last_space >= 0 else max_length

        chunks.append(text[:split_pos])

        # Advance past the break point, consuming separator characters
        text = text[split_pos:].lstrip("\n ")

    return chunks
