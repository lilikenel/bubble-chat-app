"""The in-memory chat session between two users - the "bubble" that forgets.

Holds all ephemeral state (the messages and the secure channel) in RAM only.
``pop()`` is the wipe: it clears the conversation and zeroes the channel keys,
so nothing survives once the chat closes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from dom.message import Message
from dom.user import User

if TYPE_CHECKING:
    from security.secure_channel import SecureChannel


class Bubble:
    """A one-to-one conversation and the secrets that back it, held only in RAM."""

    def __init__(self, local_user: User, channel: SecureChannel | None = None) -> None:
        self.bubble_id: UUID = uuid4()
        self.local_user = local_user
        self.remote_name: str | None = None
        self.channel = channel
        self._messages: list[Message] = []
        self._closed = False

    def add(self, message: Message) -> None:
        """Append a message to the in-memory history."""
        if self._closed:
            raise RuntimeError("bubble is closed")
        self._messages.append(message)

    def history(self) -> list[Message]:
        """Return a copy of the messages so callers can't mutate internal state."""
        return list(self._messages)

    def pop(self) -> None:
        """Forget everything: clear messages, wipe the channel keys, mark closed."""
        self._messages.clear()
        if self.channel is not None:
            self.channel.wipe()
        self._closed = True
