"""Unit tests for telegram_formatter — Markdown→Telegram HTML conversion + message splitting."""

from __future__ import annotations

import pytest

from aria.gateway.telegram_formatter import markdown_to_telegram_html, split_telegram_message


# === markdown_to_telegram_html ===


class TestMarkdownToTelegramHtml:
    """Test suite for markdown_to_telegram_html."""

    # --- Headings ---

    def test_h2_to_bold(self) -> None:
        assert markdown_to_telegram_html("## Heading") == "<b>Heading</b>"

    def test_h1_to_bold(self) -> None:
        assert markdown_to_telegram_html("# Heading") == "<b>Heading</b>"

    def test_h3_to_bold(self) -> None:
        assert markdown_to_telegram_html("### Sub") == "<b>Sub</b>"

    def test_heading_with_trailing_hashes(self) -> None:
        assert markdown_to_telegram_html("## Title ##") == "<b>Title</b>"

    def test_heading_preserves_inline_formatting(self) -> None:
        result = markdown_to_telegram_html("## **Bold Title**")
        assert "<b>" in result
        assert "Bold Title" in result

    # --- Bold ---

    def test_double_star_bold(self) -> None:
        assert markdown_to_telegram_html("**bold**") == "<b>bold</b>"

    def test_bold_in_sentence(self) -> None:
        result = markdown_to_telegram_html("This is **bold** text")
        assert result == "This is <b>bold</b> text"

    def test_multiple_bold(self) -> None:
        result = markdown_to_telegram_html("**a** and **b**")
        assert result == "<b>a</b> and <b>b</b>"

    # --- Italic ---

    def test_single_star_italic(self) -> None:
        assert markdown_to_telegram_html("*italic*") == "<i>italic</i>"

    def test_italic_in_sentence(self) -> None:
        result = markdown_to_telegram_html("This is *italic* text")
        assert result == "This is <i>italic</i> text"

    def test_italic_not_applied_to_double_star(self) -> None:
        """**bold** should not be misinterpreted as *bold*."""
        result = markdown_to_telegram_html("**bold**")
        assert "<i>" not in result

    # --- Inline code ---

    def test_inline_code(self) -> None:
        assert markdown_to_telegram_html("`code`") == "<code>code</code>"

    def test_inline_code_in_sentence(self) -> None:
        result = markdown_to_telegram_html("Use `pip install` to install")
        assert result == "Use <code>pip install</code> to install"

    # --- Code blocks ---

    def test_fenced_code_block(self) -> None:
        md = "```\ncode line\n```"
        result = markdown_to_telegram_html(md)
        assert "<pre>" in result
        assert "code line" in result
        assert "</pre>" in result

    def test_fenced_code_block_with_language(self) -> None:
        md = "```python\nprint('hello')\n```"
        result = markdown_to_telegram_html(md)
        assert "<pre>" in result
        assert "print('hello')" in result

    def test_code_block_preserves_html(self) -> None:
        """HTML inside code blocks should NOT be escaped to &lt; etc."""
        md = "```html\n<div>test</div>\n```"
        result = markdown_to_telegram_html(md)
        assert "<div>test</div>" in result
        assert "&lt;" not in result

    # --- Links ---

    def test_link(self) -> None:
        result = markdown_to_telegram_html("[click here](https://example.com)")
        assert result == '<a href="https://example.com">click here</a>'

    def test_link_with_bold_text(self) -> None:
        result = markdown_to_telegram_html("[**bold link**](https://example.com)")
        assert '<a href="https://example.com">' in result
        assert "<b>bold link</b>" in result

    # --- Bullet lists ---

    def test_dash_bullet(self) -> None:
        result = markdown_to_telegram_html("- item one")
        assert result.startswith("• item one")

    def test_star_bullet(self) -> None:
        result = markdown_to_telegram_html("* item one")
        assert result.startswith("• item one")

    def test_numbered_list_preserved(self) -> None:
        result = markdown_to_telegram_html("1. first item")
        assert result.startswith("1. first item")

    # --- HTML escaping ---

    def test_html_entities_escaped(self) -> None:
        result = markdown_to_telegram_html("a < b > c & d")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result

    def test_html_entities_not_escaped_in_code(self) -> None:
        """Code blocks should preserve raw HTML."""
        result = markdown_to_telegram_html("```\nx < y\n```")
        assert "x < y" in result
        assert "&lt;" not in result

    # --- Edge cases ---

    def test_empty_string(self) -> None:
        assert markdown_to_telegram_html("") == ""

    def test_plain_text_passthrough(self) -> None:
        result = markdown_to_telegram_html("Just plain text here.")
        assert result == "Just plain text here."

    def test_newlines_preserved(self) -> None:
        result = markdown_to_telegram_html("line1\nline2")
        assert "line1\nline2" == result

    def test_complex_document(self) -> None:
        md = (
            "## Header\n\n"
            "Some **bold** and *italic* text.\n\n"
            "- item 1\n"
            "- item 2\n\n"
            "Use `code` for inline.\n\n"
            "```\ncode block\n```"
        )
        result = markdown_to_telegram_html(md)
        assert "<b>Header</b>" in result
        assert "<b>bold</b>" in result
        assert "<i>italic</i>" in result
        assert "• item 1" in result
        assert "<code>code</code>" in result
        assert "<pre>" in result

    def test_already_html_bold_preserved(self) -> None:
        """If text already contains <b> tags, they should survive."""
        result = markdown_to_telegram_html("<b>already bold</b>")
        assert "<b>already bold</b>" in result

    def test_mixed_heading_and_list(self) -> None:
        md = "## Ricerca e Analisi\n- **Web research**: search the web\n- **Deep research**: multi-source"
        result = markdown_to_telegram_html(md)
        assert "<b>Ricerca e Analisi</b>" in result
        assert "• <b>Web research</b>: search the web" in result


# === split_telegram_message ===


class TestSplitTelegramMessage:
    """Test suite for split_telegram_message."""

    def test_short_message_single_chunk(self) -> None:
        chunks = split_telegram_message("Short message")
        assert chunks == ["Short message"]

    def test_exact_limit_single_chunk(self) -> None:
        text = "a" * 4096
        chunks = split_telegram_message(text)
        assert len(chunks) == 1
        assert len(chunks[0]) == 4096

    def test_over_limit_splits_at_paragraph(self) -> None:
        part_a = "a" * 2000
        part_b = "b" * 2100
        text = part_a + "\n\n" + part_b
        chunks = split_telegram_message(text)
        assert len(chunks) == 2
        assert all(len(c) <= 4096 for c in chunks)
        assert part_a in chunks[0]
        assert part_b in chunks[1]

    def test_over_limit_splits_at_newline_when_no_paragraph_break(self) -> None:
        part_a = "a" * 3000
        part_b = "b" * 2000
        text = part_a + "\n" + part_b
        chunks = split_telegram_message(text)
        assert len(chunks) == 2
        assert all(len(c) <= 4096 for c in chunks)

    def test_no_break_possible_hard_split(self) -> None:
        """A single continuous string > max_length must be hard-split."""
        text = "x" * 5000
        chunks = split_telegram_message(text)
        assert len(chunks) == 2
        assert all(len(c) <= 4096 for c in chunks)

    def test_custom_max_length(self) -> None:
        text = "a" * 50 + "\n" + "b" * 50
        chunks = split_telegram_message(text, max_length=60)
        assert len(chunks) == 2

    def test_empty_string_returns_empty_list(self) -> None:
        assert split_telegram_message("") == []

    def test_multiple_paragraphs(self) -> None:
        text = "\n\n".join(["paragraph " + str(i) * 100 for i in range(50)])
        chunks = split_telegram_message(text)
        assert len(chunks) > 1
        assert all(len(c) <= 4096 for c in chunks)
        # All paragraph content is preserved across chunks
        rejoined = "\n".join(chunks)
        for i in range(50):
            assert str(i) * 100 in rejoined

    def test_whitespace_content(self) -> None:
        assert split_telegram_message("   ") == ["   "]
