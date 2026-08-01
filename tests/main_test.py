"""Tests for main.py argument parsing and config gathering."""

from __future__ import annotations

import unittest
from unittest import mock

from main import SessionConfig, gather_config, parse_args


class ParseArgsTest(unittest.TestCase):
    def test_parses_host_mode(self) -> None:
        self.assertEqual(
            parse_args(["host", "127.0.0.1:5050"]),
            ("host", ("127.0.0.1", 5050)),
        )

    def test_parses_join_mode(self) -> None:
        self.assertEqual(
            parse_args(["join", "localhost:9000"]),
            ("join", ("localhost", 9000)),
        )

    def test_rejects_unknown_mode(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["serve", "127.0.0.1:5050"])

    def test_rejects_address_without_port(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["host", "127.0.0.1"])


class GatherConfigTest(unittest.TestCase):
    def test_args_bypass_the_wizard(self) -> None:
        config = gather_config(["host", "127.0.0.1:5050"], name="cli")

        self.assertEqual(
            config,
            SessionConfig(
                mode="host", address=("127.0.0.1", 5050), display_name="cli"
            ),
        )

    def test_no_args_runs_the_host_wizard(self) -> None:
        with mock.patch("main.prompts") as prompts:
            prompts.HOST = "host"
            prompts.main_menu.return_value = "host"
            prompts.host_network.return_value = ("192.168.3.198", 5050)
            prompts.ask_name.return_value = "lilike"

            config = gather_config([], name=None)

        self.assertEqual(
            config,
            SessionConfig(
                mode="host",
                address=("192.168.3.198", 5050),
                display_name="lilike",
            ),
        )

    def test_cancelled_wizard_returns_none(self) -> None:
        with mock.patch("main.prompts") as prompts:
            prompts.main_menu.return_value = None

            self.assertIsNone(gather_config([], name=None))


if __name__ == "__main__":
    unittest.main()
