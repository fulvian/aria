#!/usr/bin/env python3
"""Extract text and metadata from a PDF using PyMuPDF."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import fitz


def extract_pdf(path: Path) -> dict[str, Any]:
    """Extract metadata and plain text from a PDF."""
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    with fitz.open(path) as doc:
        metadata = doc.metadata or {}
        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text("text"))

    return {
        "path": str(path),
        "metadata": {
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "subject": metadata.get("subject"),
            "keywords": metadata.get("keywords"),
            "creator": metadata.get("creator"),
            "producer": metadata.get("producer"),
            "creationDate": metadata.get("creationDate"),
            "modDate": metadata.get("modDate"),
            "page_count": len(pages),
        },
        "text": "\n\n".join(pages),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract metadata and text from PDF")
    parser.add_argument("pdf_path", type=Path, help="Absolute or relative PDF path")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = extract_pdf(args.pdf_path)
    except Exception as exc:
        payload = {"success": False, "error": str(exc)}
        sys.stdout.write(json.dumps(payload))
        return 1

    sys.stdout.write(json.dumps({"success": True, "data": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
