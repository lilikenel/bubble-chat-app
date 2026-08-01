"""Tests for ChatSession: encrypted messaging with replay protection."""

from __future__ import annotations

import socket
import struct
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from nacl.utils import random as random_bytes

from dom.bubble import Bubble
from dom.message import Message
from dom.user import User
from networking.peer import Peer
from security.secure_channel import SecureChannel
from session import ChatSession, sanitize_for_terminal


class SanitizeTest(unittest.TestCase):
    def test_strips_control_and_escape_characters(self) -> None:
        self.assertEqual(sanitize_for_terminal("a\x1bb\nc\x00d"), "abcd")

    def test_keeps_normal_text(self) -> None:
        self.assertEqual(sanitize_for_terminal("café 🎉 50%"), "café 🎉 50%")


class ChatSessionTest(unittest.TestCase):
    def _pair(self) -> SimpleNamespace:
        host_sock, joiner_sock = socket.socketpair()
        self.addCleanup(host_sock.close)
        self.addCleanup(joiner_sock.close)
        host_peer, joiner_peer = Peer(host_sock), Peer(joiner_sock)
        h2j, j2h = random_bytes(32), random_bytes(32)
        host_bubble = Bubble(User("Host"))
        host = ChatSession(
            host_peer, SecureChannel(send_key=h2j, receive_key=j2h), host_bubble
        )
        joiner = ChatSession(
            joiner_peer,
            SecureChannel(send_key=j2h, receive_key=h2j),
            Bubble(User("Joiner")),
        )
        return SimpleNamespace(
            host=host,
            joiner=joiner,
            host_bubble=host_bubble,
            host_peer=host_peer,
            host_channel=host._channel,
        )

    def test_send_text_reaches_the_peer(self) -> None:
        ctx = self._pair()

        ctx.host.send_text("hi joiner")
        message = ctx.joiner.receive_message()

        self.assertEqual(message.text, "hi joiner")
        self.assertEqual(message.sender_name, "Host")

    def test_send_text_records_in_sender_history(self) -> None:
        ctx = self._pair()

        ctx.host.send_text("hello")

        self.assertEqual([m.text for m in ctx.host_bubble.history()], ["hello"])

    def test_replayed_frame_is_dropped(self) -> None:
        ctx = self._pair()
        message = Message("once", "Host", uuid4(), datetime.now(timezone.utc))
        payload = struct.pack(">Q", 0) + message.to_bytes()
        frame = ctx.host_channel.encrypt(payload)

        ctx.host_peer.send_bytes(frame)
        ctx.host_peer.send_bytes(frame)  # attacker re-injects the exact ciphertext

        first = ctx.joiner.receive_message()
        second = ctx.joiner.receive_message()

        self.assertEqual(first.text, "once")
        self.assertIsNone(second)


if __name__ == "__main__":
    unittest.main()
