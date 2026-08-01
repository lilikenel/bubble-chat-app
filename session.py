"""The running chat session: ties transport, crypto, and the conversation together.

Wraps a Peer (framed transport), a SecureChannel (encryption), and a Bubble
(in-memory history). Each outbound message is prefixed with a monotonic sequence
number *inside* the encrypted payload; the receiver drops any frame whose sequence
is not strictly greater than the last accepted, defeating replay/reorder by an
on-path attacker.
"""

from __future__ import annotations

import re
import struct
import threading
from datetime import datetime, timezone

from nacl.exceptions import CryptoError

from dom.bubble import Bubble
from dom.message import Message
from networking.framing import FramingError, PeerDisconnected
from networking.peer import Peer
from security.secure_channel import SecureChannel

_SEQUENCE = struct.Struct(">Q")  # 8-byte monotonic per-direction counter
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")

QUIT_COMMAND = "/quit"


def sanitize_for_terminal(text: str) -> str:
    """Remove control/escape characters so a peer can't drive the local terminal."""
    return _CONTROL_CHARS.sub("", text)


class ChatSession:
    """Drives one secure conversation until /quit or the peer disconnects."""

    def __init__(self, peer: Peer, channel: SecureChannel, bubble: Bubble) -> None:
        self._peer = peer
        self._channel = channel
        self._bubble = bubble
        self._bubble.channel = channel  # so pop() wipes the same channel
        self._send_sequence = 0
        self._last_received_sequence = -1
        self._stop = threading.Event()

    def send_text(self, text: str) -> Message:
        """Encrypt and send one message, and record it in our own history."""
        user = self._bubble.local_user
        message = Message(
            text=text,
            sender_name=user.display_name,
            sender_id=user.user_id,
            timestamp=datetime.now(timezone.utc),
        )
        payload = _SEQUENCE.pack(self._send_sequence) + message.to_bytes()
        self._send_sequence += 1
        self._peer.send_bytes(self._channel.encrypt(payload))
        self._bubble.add(message)
        return message

    def receive_message(self) -> Message | None:
        """Receive one message; returns None for a replayed or reordered frame."""
        payload = self._channel.decrypt(self._peer.recv_bytes())
        sequence = _SEQUENCE.unpack(payload[: _SEQUENCE.size])[0]
        if sequence <= self._last_received_sequence:
            return None  # replay or reorder -> drop
        self._last_received_sequence = sequence
        message = Message.from_bytes(payload[_SEQUENCE.size :])
        self._bubble.add(message)
        return message

    def run(self) -> None:
        """Run until /quit, EOF, Ctrl-C, or the peer disconnects (blocks on stdin)."""
        receiver = threading.Thread(target=self._receive_loop, daemon=True)
        receiver.start()
        try:
            while not self._stop.is_set():
                line = input()
                if line.strip() == QUIT_COMMAND:
                    break
                self.send_text(line)
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            self._stop.set()

    def _receive_loop(self) -> None:
        while not self._stop.is_set():
            try:
                message = self.receive_message()
            except PeerDisconnected:
                self._note("peer disconnected")
                break
            except (CryptoError, FramingError, ValueError, OSError, RuntimeError):
                self._note("dropped a tampered or malformed message")
                break  # fail closed
            if message is not None:
                print(sanitize_for_terminal(str(message)))
        self._stop.set()

    def _note(self, text: str) -> None:
        # Stay quiet when we're the ones shutting down.
        if not self._stop.is_set():
            print(f"\n({text})")

    def close(self) -> None:
        """Stop the session, close the socket, and wipe all secrets."""
        self._stop.set()
        self._peer.close()
        self._bubble.pop()
