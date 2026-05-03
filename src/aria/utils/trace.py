"""Trace ID generation — UUID v7 (time-ordered) with Python 3.12 fallback.

UUID v7 provides time-ordered, sortable UUIDs with 74 bits of randomness,
compliant with RFC 9562.  Python 3.15+ includes ``uuid.uuid7()`` natively;
for 3.12 we implement it via bit manipulation per the RFC.

Usage
-----
    from aria.utils.trace import generate_trace_id

    trace_id = generate_trace_id()          # UUIDv7 hex string
    trace_id_short = generate_trace_id(short=True)  # first 8 hex chars
"""

from __future__ import annotations

import os
import time

# ---------------------------------------------------------------------------
# UUID version / variant constants (RFC 9562)
# ---------------------------------------------------------------------------
_VERSION_MASK = 0xF000
_VERSION_7 = 0x7000
_VARIANT_MASK = 0xC000
_VARIANT_RFC9562 = 0x8000


def _uuid7_bytes() -> bytes:
    """Return a 16-byte UUIDv7 value.

    Layout (128 bits):
      - 48 bits: Unix timestamp in milliseconds
      -  4 bits: version (0b0111 = 7)
      - 12 bits: random (sub-second / sequence)
      -  2 bits: variant (0b10 = RFC 9562)
      - 62 bits: random
    """
    # 48-bit timestamp in milliseconds
    ts = int(time.time() * 1000) & 0xFFFFFFFFFFFF

    # 12 bits of random
    rand_a = os.urandom(1)[0] & 0x0F  # 4 bits (the other 4 become version)
    rand_b = os.urandom(1)[0]  # 8 bits
    rand_12 = (rand_a << 8) | rand_b  # 12 bits total (4 + 8)

    # 62 bits of random (8 bytes minus 2 variant bits)
    rand_62 = int.from_bytes(os.urandom(8), "big") >> 2

    packed = (
        (ts << 16)  # 48 bits timestamp
        | (rand_12)  # 12 bits random
    )
    # 8 bytes: 6 (ts+rand) + 2 (version + variant + random)
    b1 = packed.to_bytes(8, "big")
    # Set version nibble: byte 6 high nibble = 0b0111
    b1_6 = (b1[6] & 0x0F) | _VERSION_7.to_bytes(2, "big")[0]
    # Set variant: byte 8 high 2 bits = 0b10
    b2 = rand_62.to_bytes(8, "big")
    b2_0 = (b2[0] & 0x3F) | _VARIANT_RFC9562.to_bytes(2, "big")[0]

    result = bytearray(16)
    result[0:6] = b1[2:8]  # bytes 2-7 of b1 → indices 0-5
    result[6] = b1_6
    result[7] = b1[7]
    result[8] = b2_0
    result[9:16] = b2[1:8]
    return bytes(result)


def generate_trace_id(short: bool = False) -> str:
    """Generate a UUID v7 trace identifier.

    Parameters
    ----------
    short : bool
        When True, return only the first 8 hex characters (32 bits)
        for concise display.  Default False (full 36-char UUID).

    Returns
    -------
    str
        Hexadecimal UUID string (with hyphens when not short).
    """
    raw = _uuid7_bytes()
    if short:
        return raw[:4].hex()

    # Standard UUID hexadecimal representation with hyphens
    parts = [
        raw[0:4].hex(),  # time_low (4 bytes)
        raw[4:6].hex(),  # time_mid (2 bytes)
        raw[6:8].hex(),  # time_hi_and_version (2 bytes)
        raw[8:10].hex(),  # clock_seq_hi_and_reserved + clock_seq_low (2 bytes)
        raw[10:16].hex(),  # node (6 bytes)
    ]
    return "-".join(parts)
