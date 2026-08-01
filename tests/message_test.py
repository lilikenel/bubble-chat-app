"""Tests for the Message value object and its wire serialization."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from dom.message import Message


class MessageTest(unittest.TestCase):
    def _sample(self, text: str = "hello") -> Message:
        return Message(
            text=text,
            sender_name="Alice",
            sender_id=uuid4(),
            timestamp=datetime(2026, 8, 1, 14, 30, tzinfo=timezone.utc),
        )

    def test_to_bytes_from_bytes_round_trips(self) -> None:
        message = self._sample()

        self.assertEqual(Message.from_bytes(message.to_bytes()), message)

    def test_round_trip_preserves_unicode_and_percent(self) -> None:
        # The old "%"-delimited format broke on these; JSON must not.
        message = self._sample(text="50% off café - 🎉 % %")

        restored = Message.from_bytes(message.to_bytes())

        self.assertEqual(restored.text, "50% off café - 🎉 % %")

    def test_str_is_human_readable(self) -> None:
        message = self._sample(text="hi")
        local_time: str = f"{message.timestamp.astimezone():%H:%M}"

        self.assertEqual(str(message), f"[{local_time}] Alice: hi")

    def test_from_bytes_rejects_malformed_data(self) -> None:
        with self.assertRaises(ValueError):
            Message.from_bytes(b"not valid json")


if __name__ == "__main__":
    unittest.main()
