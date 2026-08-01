"""Tests for the Bubble conversation and its pop() wipe."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from nacl.utils import random as random_bytes

from dom.bubble import Bubble
from dom.message import Message
from dom.user import User
from security.secure_channel import SecureChannel


class BubbleTest(unittest.TestCase):
    def _message(self, text: str = "hi") -> Message:
        return Message(
            text=text,
            sender_name="Alice",
            sender_id=uuid4(),
            timestamp=datetime(2026, 8, 1, 14, 30, tzinfo=timezone.utc),
        )

    def test_add_and_history_preserve_order(self) -> None:
        bubble = Bubble(User("Alice"))
        first, second = self._message("one"), self._message("two")

        bubble.add(first)
        bubble.add(second)

        self.assertEqual(bubble.history(), [first, second])

    def test_history_returns_a_copy(self) -> None:
        bubble = Bubble(User("Alice"))
        bubble.add(self._message())

        bubble.history().clear()  # mutating the copy must not empty the bubble

        self.assertEqual(len(bubble.history()), 1)

    def test_pop_clears_messages_and_wipes_channel(self) -> None:
        channel = SecureChannel(
            send_key=random_bytes(32), receive_key=random_bytes(32)
        )
        bubble = Bubble(User("Alice"), channel=channel)
        bubble.add(self._message())

        bubble.pop()

        self.assertEqual(bubble.history(), [])
        with self.assertRaises(RuntimeError):  # channel was wiped
            channel.encrypt(b"gone")

    def test_add_after_pop_raises(self) -> None:
        bubble = Bubble(User("Alice"))
        bubble.pop()

        with self.assertRaises(RuntimeError):
            bubble.add(self._message())


if __name__ == "__main__":
    unittest.main()
