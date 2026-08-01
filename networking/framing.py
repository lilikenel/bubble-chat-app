"""Length-prefixed framing over a stream socket.

TCP is a byte stream with no message boundaries, so every payload is sent as a
4-byte big-endian length header followed by exactly that many bytes.
"""

from __future__ import annotations

import socket
import struct

_HEADER = struct.Struct(">I")

# Largest frame we will send or accept. Bounds memory a peer can make us
# allocate, so a malformed or hostile length header can't exhaust the process.
MAX_FRAME = 1 << 20  # 1 MiB


class FramingError(Exception):
    """A frame violated the protocol: too large, or truncated mid-transfer."""


class PeerDisconnected(Exception):
    """The peer closed the connection cleanly at a frame boundary."""


def send_framed(sock: socket.socket, payload: bytes) -> None:
    """Send ``payload`` as a single length-prefixed frame."""
    if len(payload) > MAX_FRAME:
        raise FramingError(f"payload of {len(payload)} bytes exceeds MAX_FRAME")
    sock.sendall(_HEADER.pack(len(payload)) + payload)


def recv_framed(sock: socket.socket) -> bytes:
    """Receive one length-prefixed frame and return its payload.

    Raises ``PeerDisconnected`` if the peer closes cleanly between frames, and
    ``FramingError`` if a frame is oversize or truncated part-way through.
    """
    header = _recv_exactly(sock, _HEADER.size, at_frame_start=True)
    (length,) = _HEADER.unpack(header)
    if length > MAX_FRAME:
        raise FramingError(f"frame of {length} bytes exceeds MAX_FRAME")
    return _recv_exactly(sock, length)


def _recv_exactly(
    sock: socket.socket, count: int, *, at_frame_start: bool = False
) -> bytes:
    """Read exactly ``count`` bytes, looping until the stream delivers them all.

    A clean close before any byte of a new frame (``at_frame_start``) is a normal
    shutdown and raises ``PeerDisconnected``; a close part-way through means a
    truncated frame and raises ``FramingError``.
    """
    chunks: list[bytes] = []
    remaining = count
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            if at_frame_start and remaining == count:
                raise PeerDisconnected("peer closed the connection")
            raise FramingError("connection closed mid-frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
