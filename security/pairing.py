"""Generation of the out-of-band pairing code.

The two users read this code to each other once; it seeds the authenticated
handshake. It carries 128 bits of CSPRNG entropy so that an attacker cannot
brute-force it, and is grouped into short chunks to make it easy to dictate.
"""

from __future__ import annotations

import base64
import secrets

_CODE_BYTES = 16  # 128 bits of entropy
_GROUP_SIZE = 4  # characters per readable chunk


def make_pairing_code() -> str:
    """Return a fresh high-entropy pairing code, e.g. ``"k7cq-3m2a-...-uf"``."""
    random_bytes = secrets.token_bytes(_CODE_BYTES)
    code_text = base64.b32encode(random_bytes).decode("ascii").rstrip("=").lower()
    return "-".join(
        code_text[i : i + _GROUP_SIZE]
        for i in range(0, len(code_text), _GROUP_SIZE)
    )
