"""Tests for main.py argument parsing."""

from __future__ import annotations

import unittest

from main import parse_args


class ParseArgsTest(unittest.TestCase):
    def test_parses_host_mode(self) -> None:
        mode, address = parse_args(["host", "127.0.0.1:5050"])

        self.assertEqual((mode, address), ("host", ("127.0.0.1", 5050)))

    def test_parses_join_mode(self) -> None:
        mode, address = parse_args(["join", "localhost:9000"])

        self.assertEqual((mode, address), ("join", ("localhost", 9000)))

    def test_rejects_unknown_mode(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["serve", "127.0.0.1:5050"])

    def test_rejects_address_without_port(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["host", "127.0.0.1"])


if __name__ == "__main__":
    unittest.main()
