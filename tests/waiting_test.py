"""Tests for the waiting-screen countdown formatting."""

from __future__ import annotations

import unittest

from ui.waiting import _format_remaining


class FormatRemainingTest(unittest.TestCase):
    def test_formats_minutes_and_seconds(self) -> None:
        self.assertEqual(_format_remaining(120), "02:00")
        self.assertEqual(_format_remaining(59), "00:59")
        self.assertEqual(_format_remaining(5), "00:05")

    def test_never_shows_negative(self) -> None:
        self.assertEqual(_format_remaining(-3), "00:00")

    def test_infinite_shows_placeholder(self) -> None:
        self.assertEqual(_format_remaining(float("inf")), "--:--")


if __name__ == "__main__":
    unittest.main()
