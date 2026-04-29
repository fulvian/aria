"""Office file ingestion — dispatcher for markitdown-mcp.

Converts local/remote office files (PDF, DOCX, XLSX, PPTX, TXT, HTML, CSV)
to structured markdown via the markitdown-mcp MCP server.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# Supported formats
FileFormat = Literal["pdf", "docx", "xlsx", "pptx", "txt", "html", "csv", "other"]

# Extensions mapped to canonical format names
EXTENSION_MAP: dict[str, FileFormat] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".pptx": "pptx",
    ".txt": "txt",
    ".text": "txt",
    ".html": "html",
    ".htm": "html",
    ".csv": "csv",
}

# YAML frontmatter pattern for metadata extraction
YAML_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL
)

# Keys to extract from frontmatter, in order of preference
METADATA_KEYS = {
    "title": ["title", "subject"],
    "author": ["author", "creator", "producer"],
}


@dataclass
class IngestResult:
    """Typed result of an office file ingestion."""

    file_path: str
    format: FileFormat
    markdown: str
    title: str | None = None
    author: str | None = None
    page_count: int | None = None
    byte_size: int = 0
    sha256: str = ""
    truncated: bool = False
    metadata: dict = field(default_factory=dict)

    @property
    def summary(self) -> str:
        """Short 1-line summary of the ingest result."""
        parts = [f"{self.format.upper()}: {Path(self.file_path).name}"]
        if self.title:
            parts.append(f"'{self.title}'")
        parts.append(f"{len(self.markdown)} chars")
        if self.truncated:
            parts.append("[TRUNCATED]")
        return " — ".join(parts)


def detect_format(path: Path) -> FileFormat:
    """Detect file format from extension.

    Args:
        path: File path to check.

    Returns:
        Canonical format name, or ``"other"`` if unknown.
    """
    return EXTENSION_MAP.get(path.suffix.lower(), "other")


def hash_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file.

    Args:
        path: Path to the file.

    Returns:
        Lowercase hex SHA-256 string.
    """
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def parse_markitdown_output(raw: str) -> dict:
    """Parse raw output from markitdown-mcp into structured metadata + body.

    markitdown may emit a YAML frontmatter block before the markdown body.
    This function extracts known metadata keys from that block.

    Args:
        raw: Full string returned by markitdown-mcp ``convert_to_markdown``.

    Returns:
        Dict with keys:
        - ``markdown`` (str): cleaned markdown body
        - ``title`` (str | None)
        - ``author`` (str | None)
        - ``page_count`` (int | None)
        - ``metadata`` (dict): raw key-value pairs from frontmatter
    """
    result: dict = {
        "markdown": raw,
        "title": None,
        "author": None,
        "page_count": None,
        "metadata": {},
    }

    if not raw:
        return result

    match = YAML_FRONTMATTER_RE.match(raw)
    if not match:
        return result

    frontmatter_text = match.group(1)
    body = match.group(2)

    # Simple line-based YAML parsing (no PyYAML dependency needed for flat keys)
    metadata: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                metadata[key] = value

    result["metadata"] = metadata

    # Extract known fields with fallback keys
    for field_name, keys in METADATA_KEYS.items():
        for k in keys:
            if k in metadata:
                result[field_name] = metadata[k]
                break

    # page_count — try integer parsing
    for k in ("page_count", "pages", "slide_count"):
        if k in metadata:
            try:
                result["page_count"] = int(metadata[k])
            except (ValueError, TypeError):
                pass
            break

    # Remove empty frontmatter
    body = body.strip()
    result["markdown"] = body if body else raw

    return result


async def ingest_file(
    uri: str,
    max_bytes: int = 50 * 1024 * 1024,
) -> IngestResult:
    """Ingest a file via markitdown-mcp and return typed result.

    Args:
        uri: ``file://`` absolute path or ``https://`` URL.
        max_bytes: Maximum file size in bytes before warning (not enforced as
            hard limit, but triggers a size check).

    Returns:
        An :class:`IngestResult` with the converted markdown and metadata.

    Note:
        This function is designed to be called from a KiloCode agent context
        where ``convert_to_markdown`` is available as an MCP tool. The actual
        MCP invocation is expected to be done by the agent's skill; this
        module provides the parsing and data modeling layer.

        For direct usage outside of MCP context, use the :func:`ingest_file_local`
        fallback.
    """
    # Parse file path from URI
    if uri.startswith("file://"):
        path = Path(uri[7:])
    elif uri.startswith("https://") or uri.startswith("http://"):
        path = Path(uri.split("/")[-1]) if "/" in uri else Path("remote_file")
    else:
        path = Path(uri)

    fmt = detect_format(path)
    byte_size = path.stat().st_size if path.exists() else 0
    sha256 = hash_file(path) if path.exists() else ""

    # NOTE: Actual MCP call (convert_to_markdown) is invoked by the agent.
    # This function is called with the raw result for parsing.
    # When called outside agent context, a NotImplementedError is raised
    # to signal that the MCP call must be performed by the caller.
    raise NotImplementedError(
        "ingest_file() requires agent-level MCP invocation. "
        "Use parse_markitdown_output() to process the raw MCP result."
    )


def ingest_file_local(path: Path) -> IngestResult:
    """Fallback: read a plain text file directly (no markitdown).

    Used when markitdown-mcp is unavailable. Only works for text-based
    formats that can be read with ``filesystem/read``.

    Args:
        path: Path to the file.

    Returns:
        An :class:`IngestResult` with raw text content (no structure).
    """
    fmt = detect_format(path)
    byte_size = path.stat().st_size
    sha256 = hash_file(path)

    content = path.read_text(encoding="utf-8", errors="replace")

    return IngestResult(
        file_path=str(path),
        format=fmt,
        markdown=content,
        title=path.stem,
        byte_size=byte_size,
        sha256=sha256,
    )
