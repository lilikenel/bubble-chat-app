"""A single chat message: an immutable value object plus its wire format.

Serialization is canonical JSON (UTF-8), which replaces the original
``" % "``-delimited format that broke whenever a message contained ``%``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Message:
    """One message; immutable so it can be freely shared and compared."""

    text: str
    sender_name: str
    sender_id: UUID
    timestamp: datetime

    def to_bytes(self) -> bytes:
        """Serialize to canonical UTF-8 JSON for sending over the channel."""
        return json.dumps(
            {
                "text": self.text,
                "sender_name": self.sender_name,
                "sender_id": str(self.sender_id),
                "timestamp": self.timestamp.isoformat(),
            }
        ).encode("utf-8")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Message":
        """Rebuild a Message from its bytes; raises ValueError if malformed."""
        try:
            data = json.loads(raw)
            return cls(
                text=data["text"],
                sender_name=data["sender_name"],
                sender_id=UUID(data["sender_id"]),
                timestamp=datetime.fromisoformat(data["timestamp"]),
            )
        except (KeyError, ValueError, TypeError) as error:
            raise ValueError(f"malformed message: {error}") from error

    def __str__(self) -> str:
        # Timestamps travel on the wire as UTC; render each in the reader's own
        # local time so both peers see their wall clock, not the sender's.
        local_time: datetime = self.timestamp.astimezone()
        return f"[{local_time:%H:%M}] {self.sender_name}: {self.text}"
