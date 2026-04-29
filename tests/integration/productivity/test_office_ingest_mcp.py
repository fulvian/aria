"""Integration tests for markitdown-mcp with real fixture files.

Requires markitdown-mcp to be available via uvx.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aria.agents.productivity.ingest import (
    detect_format,
    hash_file,
    parse_markitdown_output,
    ingest_file_local,
)

FIXTURES_DIR = Path("tests/fixtures/office_files")

# Format to expected file
FIXTURE_FILES = {
    "pdf": "sample_invoice.pdf",
    "docx": "sample_proposal.docx",
    "xlsx": "sample_budget.xlsx",
    "pptx": "sample_pitch.pptx",
    "txt": "sample_notes.txt",
}


class TestOfficeIngestMCP:
    """Integration tests calling the real markitdown-mcp server."""

    @pytest.mark.parametrize(
        ("fmt", "filename"),
        [(fmt, fn) for fmt, fn in FIXTURE_FILES.items()],
    )
    def test_format_detection(self, fmt: str, filename: str) -> None:
        """Verify detect_format matches expected format for each fixture."""
        path = FIXTURES_DIR / filename
        assert path.exists(), f"Fixture missing: {path}"
        detected = detect_format(path)
        assert detected == fmt, f"Expected {fmt}, got {detected} for {filename}"

    @pytest.mark.parametrize(
        ("fmt", "filename"),
        [(fmt, fn) for fmt, fn in FIXTURE_FILES.items()],
    )
    def test_hash_consistency(self, fmt: str, filename: str) -> None:
        """Verify hash_file is deterministic for each fixture."""
        path = FIXTURES_DIR / filename
        h1 = hash_file(path)
        h2 = hash_file(path)
        assert h1 == h2, f"Hash not deterministic for {filename}"
        assert len(h1) == 64, f"Expected 64-char SHA256, got {len(h1)}"

    def test_fallback_local_txt(self) -> None:
        """Verify ingest_file_local works for plain text."""
        path = FIXTURES_DIR / "sample_notes.txt"
        result = ingest_file_local(path)
        assert result.format == "txt"
        assert "Project Alpha" in result.markdown
        assert result.sha256 == hash_file(path)
        assert result.byte_size == path.stat().st_size

    @pytest.mark.integration
    @pytest.mark.skipif(
        not FIXTURES_DIR.exists(),
        reason="Fixtures directory not found",
    )
    def test_markitdown_convert_txt(self) -> None:
        """E2E: convert a txt fixture via real markitdown-mcp process.

        This test starts a real markitdown-mcp subprocess and calls
        convert_to_markdown with a file:// URI.
        """
        import asyncio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        path = FIXTURES_DIR / "sample_notes.txt"
        uri = f"file://{path.resolve()}"

        async def _run():
            server_params = StdioServerParameters(
                command="uvx",
                args=["markitdown-mcp"],
            )
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "convert_to_markdown",
                        {"uri": uri},
                    )
                    if result.content:
                        text = result.content[0].text
                    else:
                        text = ""
                    parsed = parse_markitdown_output(text)
                    assert len(parsed["markdown"]) > 0
                    assert "Project Alpha" in parsed["markdown"]

        asyncio.run(_run())

    @pytest.mark.integration
    def test_markitdown_convert_docx(self) -> None:
        """E2E: convert a docx fixture via real markitdown-mcp subprocess."""
        import asyncio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        path = FIXTURES_DIR / "sample_proposal.docx"
        uri = f"file://{path.resolve()}"

        async def _run():
            server_params = StdioServerParameters(
                command="uvx",
                args=["markitdown-mcp"],
            )
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "convert_to_markdown",
                        {"uri": uri},
                    )
                    if result.content:
                        text = result.content[0].text
                    else:
                        text = ""
                    parsed = parse_markitdown_output(text)
                    assert len(parsed["markdown"]) > 0
                    # Should extract meaningful content
                    assert "ARIA" in parsed["markdown"] or "Technical" in parsed["markdown"]

        asyncio.run(_run())
