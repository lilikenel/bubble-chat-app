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
from typing import Protocol

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


class ChatRenderer(Protocol):
    """How a session surfaces messages and notices to the user."""

    def show_message(self, message: Message, is_local: bool) -> None: ...

    def notice(self, text: str) -> None: ...


class _NullRenderer:
    """A renderer that discards everything - the default for tests/headless use."""

    def show_message(self, message: Message, is_local: bool) -> None:
        pass

    def notice(self, text: str) -> None:
        pass


class ChatSession:
    """Drives one secure conversation until /quit or the peer disconnects."""

    def __init__(
        self,
        peer: Peer,
        channel: SecureChannel,
        bubble: Bubble,
        renderer: ChatRenderer | None = None,
    ) -> None:
        self._peer = peer
        self._channel = channel
        self._bubble = bubble
        self._bubble.channel = channel  # so pop() wipes the same channel
        self._renderer: ChatRenderer = renderer or _NullRenderer()
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
        self._renderer.show_message(message, is_local=True)
        return message

    def receive_message(self) -> Message | None:
        """Receive one message; returns None for a replayed or reordered frame."""
        payload = self._channel.decrypt(self._peer.recv_bytes())
        if len(payload) < _SEQUENCE.size:
            raise ValueError("message payload too short")  # fail closed
        sequence = _SEQUENCE.unpack(payload[: _SEQUENCE.size])[0]
        if sequence <= self._last_received_sequence:
            return None  # replay or reorder -> drop
        self._last_received_sequence = sequence
        message = Message.from_bytes(payload[_SEQUENCE.size :])
        self._bubble.add(message)
        self._renderer.show_message(message, is_local=False)
        return message

    def run(self) -> None:
        """Run until /quit, EOF, Ctrl-C, or the peer disconnects (blocks on stdin)."""
        receiver = threading.Thread(target=self._receive_loop, daemon=True)
        receiver.start()
        try:
            while not self._stop.is_set():
                line = input()
                if self._stop.is_set():
                    break  # the peer left while we were waiting for input
                stripped = line.strip()
                if stripped == QUIT_COMMAND:
                    break
                if not stripped:
                    continue  # ignore blank lines
                self.send_text(line)
        except (EOFError, KeyboardInterrupt):
            pass
        except OSError:
            pass  # peer went away mid-send; shut down cleanly
        finally:
            self._stop.set()

    def _receive_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.receive_message()
            except PeerDisconnected:
                self._note("peer disconnected - press enter to exit")
                break
            except (CryptoError, FramingError, ValueError, OSError, RuntimeError):
                self._note("dropped a tampered message - press enter to exit")
                break  # fail closed
            # receive_message() renders and records the message (if it wasn't a
            # dropped replay); bubble.add there and in send_text() run on
            # different threads, but CPython's GIL keeps list.append atomic.
        self._stop.set()

    def _note(self, text: str) -> None:
        # Stay quiet when we're the ones shutting down.
        if not self._stop.is_set():
            self._renderer.notice(text)

    def close(self) -> None:
        """Stop the session, close the socket, and wipe all secrets."""
        self._stop.set()
        self._peer.close()
        self._bubble.pop()
