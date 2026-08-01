"""Tests for pairing-code generation."""

from __future__ import annotations

import base64
import unittest

from security.pairing import make_pairing_code


class PairingCodeTest(unittest.TestCase):
    def test_returns_non_empty_string(self) -> None:
        code = make_pairing_code()

        self.assertIsInstance(code, str)
        self.assertTrue(code)

    def test_is_unpredictable_across_calls(self) -> None:
        codes = {make_pairing_code() for _ in range(10)}

        # Ten CSPRNG-backed codes must never collide.
        self.assertEqual(len(codes), 10)

    def test_carries_at_least_128_bits_of_entropy(self) -> None:
        raw = make_pairing_code().replace("-", "").upper()
        decoded = base64.b32decode(raw + "=" * (-len(raw) % 8))

        self.assertGreaterEqual(len(decoded), 16)  # 16 bytes = 128 bits


if __name__ == "__main__":
    unittest.main()
