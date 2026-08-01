"""Tests for the length-prefixed framing helpers."""

from __future__ import annotations

import socket
import struct
import threading
import unittest

from networking.framing import (
    MAX_FRAME,
    FramingError,
    PeerDisconnected,
    recv_framed,
    send_framed,
)


class FramingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sender, self.receiver = socket.socketpair()
        self.addCleanup(self.sender.close)
        self.addCleanup(self.receiver.close)

    def _send_in_background(self, payload: bytes) -> None:
        """Send from a thread so sendall can drain while the test receives."""
        thread = threading.Thread(target=send_framed, args=(self.sender, payload))
        thread.start()
        self.addCleanup(thread.join)

    def test_send_and_recv_round_trips_payload(self) -> None:
        send_framed(self.sender, b"hello world")

        self.assertEqual(recv_framed(self.receiver), b"hello world")

    def test_round_trips_empty_payload(self) -> None:
        send_framed(self.sender, b"")

        self.assertEqual(recv_framed(self.receiver), b"")

    def test_round_trips_large_payload_across_multiple_reads(self) -> None:
        # Larger than a typical socket buffer, so TCP delivers it in several
        # segments and recv() must loop to reassemble the full frame.
        payload = b"x" * (256 * 1024)
        self._send_in_background(payload)

        self.assertEqual(recv_framed(self.receiver), payload)

    def test_round_trips_payload_of_exactly_max_frame(self) -> None:
        # MAX_FRAME is the largest *accepted* size (the guard is a strict ">").
        payload = b"x" * MAX_FRAME
        self._send_in_background(payload)

        self.assertEqual(recv_framed(self.receiver), payload)

    def test_send_rejects_oversize_payload(self) -> None:
        with self.assertRaises(FramingError):
            send_framed(self.sender, b"x" * (MAX_FRAME + 1))

    def test_recv_rejects_oversize_frame(self) -> None:
        # A malicious/broken peer announces a huge length; recv must refuse
        # before attempting to allocate/read the body.
        self.sender.sendall(struct.pack(">I", MAX_FRAME + 1))

        with self.assertRaises(FramingError):
            recv_framed(self.receiver)

    def test_recv_raises_peer_disconnected_on_clean_close(self) -> None:
        # Peer closes at a frame boundary (no partial frame): normal shutdown.
        self.sender.close()

        with self.assertRaises(PeerDisconnected):
            recv_framed(self.receiver)

    def test_recv_raises_framing_error_on_truncated_frame(self) -> None:
        # Header promises 10 bytes but only 3 arrive before close: truncation.
        self.sender.sendall(struct.pack(">I", 10) + b"abc")
        self.sender.close()

        with self.assertRaises(FramingError):
            recv_framed(self.receiver)


if __name__ == "__main__":
    unittest.main()
