"""Tests for local IPv4 detection."""

from __future__ import annotations

import unittest
from unittest import mock

from networking.addressing import local_ipv4


class LocalIpv4Test(unittest.TestCase):
    def test_returns_socket_source_address(self) -> None:
        fake_sock = mock.MagicMock()
        fake_sock.getsockname.return_value = ("192.168.3.198", 51234)
        with mock.patch("socket.socket", return_value=fake_sock):
            self.assertEqual(local_ipv4(), "192.168.3.198")
        fake_sock.close.assert_called_once()

    def test_falls_back_to_loopback_on_error(self) -> None:
        fake_sock = mock.MagicMock()
        fake_sock.connect.side_effect = OSError("no network")
        with mock.patch("socket.socket", return_value=fake_sock):
            self.assertEqual(local_ipv4(), "127.0.0.1")
        fake_sock.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
