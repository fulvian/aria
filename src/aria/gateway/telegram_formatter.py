# Telegram Formatter — Format messages for Telegram
#
# Stub implementation for formatting.
#
# Usage:
#   from aria.gateway.telegram_formatter import format_message
#
#   text = format_message(content)

from __future__ import annotations


def format_message(content: str, parse_mode: str = "Markdown") -> dict:
    """Format a message for Telegram.

    Args:
        content: The message content
        parse_mode: Parse mode (Markdown or HTML)

    Returns:
        Dict with text and parse_mode
    """
    return {"text": content, "parse_mode": parse_mode}


def format_keyboard(buttons: list[list[str]]) -> dict:
    """Format inline keyboard buttons.

    Args:
        buttons: 2D list of button labels

    Returns:
        Dict with inline_keyboard
    """
    keyboard = [[{"text": text} for text in row] for row in buttons]
    return {"inline_keyboard": keyboard}
