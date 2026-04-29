"""Unit tests for office-ingest module (ingest.py)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from aria.agents.productivity.ingest import (
    IngestResult,
    detect_format,
    hash_file,
    parse_markitdown_output,
)


class TestDetectFormat:
    """Tests for detect_format() — pure function, no MCP."""

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("report.pdf", "pdf"),
            ("document.pdf", "pdf"),
            ("letter.docx", "docx"),
            ("proposal.docx", "docx"),
            ("budget.xlsx", "xlsx"),
            ("data.xlsx", "xlsx"),
            ("pitch.pptx", "pptx"),
            ("deck.pptx", "pptx"),
            ("notes.txt", "txt"),
            ("readme.txt", "txt"),
            ("page.html", "html"),
            ("index.html", "html"),
            ("data.csv", "csv"),
            ("export.csv", "csv"),
            ("unknown.xyz", "other"),
            ("noext", "other"),
        ],
    )
    def test_detect_format_known(self, filename: str, expected: str) -> None:
        assert detect_format(Path(filename)) == expected


class TestHashFile:
    """Tests for hash_file() — SHA256 of file content."""

    def test_hash_file_known_content(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world\n")
        expected = hashlib.sha256(b"hello world\n").hexdigest()
        assert hash_file(f) == expected

    def test_hash_file_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("")
        expected = hashlib.sha256(b"").hexdigest()
        assert hash_file(f) == expected

    def test_hash_file_binary(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02\xff")
        expected = hashlib.sha256(b"\x00\x01\x02\xff").hexdigest()
        assert hash_file(f) == expected


class TestParseMarkitdownOutput:
    """Tests for parse_markitdown_output() — parsing raw markitdown response."""

    def test_simple_markdown(self) -> None:
        raw = "# Hello\n\nThis is a test.\n\n| Col1 | Col2 |\n|------|------|\n| A    | B    |\n"
        result = parse_markitdown_output(raw)
        assert result["markdown"] == raw
        assert result["title"] is None
        assert result["author"] is None
        assert result["page_count"] is None

    def test_with_yaml_frontmatter(self) -> None:
        raw = """---
title: Sample Report
author: Fulvio
date: 2026-04-29
---

# Report Content

Body text here.
"""
        result = parse_markitdown_output(raw)
        assert result["title"] == "Sample Report"
        assert result["author"] == "Fulvio"
        assert "Report Content" in result["markdown"]

    def test_empty_output(self) -> None:
        result = parse_markitdown_output("")
        assert result["markdown"] == ""
        assert result["title"] is None
        assert result["author"] is None

    def test_partial_yaml(self) -> None:
        raw = """---
title: Only Title
---

No author, no date.
"""
        result = parse_markitdown_output(raw)
        assert result["title"] == "Only Title"
        assert result["author"] is None


class TestIngestResult:
    """Tests for IngestResult dataclass."""

    def test_minimal_ingest_result(self) -> None:
        ir = IngestResult(
            file_path="/tmp/test.pdf",
            format="pdf",
            markdown="# Content",
            title=None,
            author=None,
            page_count=None,
            byte_size=100,
            sha256="abc123",
            truncated=False,
        )
        assert ir.file_path == "/tmp/test.pdf"
        assert ir.format == "pdf"
        assert ir.markdown == "# Content"
        assert not ir.truncated

    def test_full_ingest_result(self) -> None:
        ir = IngestResult(
            file_path="/tmp/report.docx",
            format="docx",
            markdown="# Report\n\nBody.",
            title="Report",
            author="Fulvio",
            page_count=5,
            byte_size=5000,
            sha256="def456",
            truncated=True,
        )
        assert ir.title == "Report"
        assert ir.author == "Fulvio"
        assert ir.page_count == 5
        assert ir.byte_size == 5000
        assert ir.truncated
