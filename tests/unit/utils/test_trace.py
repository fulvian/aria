"""Unit tests for aria.utils.trace — UUID v7 generation."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Import directly to avoid aria package init (which has keyring dependency)
_SRC = Path(__file__).resolve().parent.parent.parent.parent / "src"
sys.path.insert(0, str(_SRC))

from aria.utils.trace import generate_trace_id  # noqa: E402, I001


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def test_generate_trace_id_format() -> None:
    """Full UUID v7 format: 8-4-4-4-12 hex with version=7 and variant=0b10."""
    tid = generate_trace_id()
    assert _UUID_RE.match(tid) is not None, f"Invalid UUID v7 format: {tid}"


def test_generate_trace_id_version_nibble() -> None:
    """Version nibble (4 bits at position 12-15) must be 7."""
    tid = generate_trace_id()
    parts = tid.split("-")
    version_nibble = int(parts[2][0], 16)
    assert version_nibble == 7, f"Expected version 7, got {version_nibble}"


def test_generate_trace_id_variant() -> None:
    """Variant top 2 bits must be 0b10 (RFC 9562)."""
    tid = generate_trace_id()
    parts = tid.split("-")
    variant_byte = int(parts[3][:2], 16)
    variant_top2 = variant_byte >> 6
    assert variant_top2 == 2, f"Expected variant 0b10, got {variant_top2}"


def test_generate_trace_id_unique() -> None:
    """Two consecutive calls produce distinct IDs."""
    t1 = generate_trace_id()
    t2 = generate_trace_id()
    assert t1 != t2


def test_generate_trace_id_timestamp_monotonic() -> None:
    """UUID v7 timestamp (top 36 bits after masking 12 random bits)."""
    t1 = generate_trace_id()
    t2 = generate_trace_id()
    # UUIDv7 layout: 48-bit ts + 4-bit version + 12-bit random + ...
    # The 48-bit ts occupies the first 12 hex chars.
    # Mask off the lower 12 bits (3 hex chars) to get pure timestamp.
    ts1 = int(t1.replace("-", "")[:9], 16)  # first 36 bits (9 hex chars)
    ts2 = int(t2.replace("-", "")[:9], 16)
    assert ts1 <= ts2  # timestamp is monotonic


def test_generate_trace_id_short_format() -> None:
    """Short mode returns 8 hex characters, no hyphens."""
    short = generate_trace_id(short=True)
    assert len(short) == 8
    assert "-" not in short
    assert all(c in "0123456789abcdef" for c in short)
