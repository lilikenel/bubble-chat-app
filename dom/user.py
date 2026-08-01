"""A chat participant's identity.

Purely a display name plus a random per-session id. Session keys come from the
handshake, so no long-lived cryptographic identity is stored here.
"""

from __future__ import annotations

from uuid import UUID, uuid4


class User:
    """One participant: a human-readable name and a random session id."""

    def __init__(self, display_name: str) -> None:
        self.display_name = display_name
        self.user_id: UUID = uuid4()
