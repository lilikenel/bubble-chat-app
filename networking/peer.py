"""Peer-to-peer transport over TCP.

One side opens a :class:`Listener` and accepts a single connection; the other
:meth:`Peer.join` connects to it. After that the two :class:`Peer` objects are
symmetric — either may send or receive length-prefixed frames.
"""

from __future__ import annotations

import socket

from networking.framing import recv_framed, send_framed


class Listener:
    """A bound, listening socket that accepts a single incoming peer."""

    def __init__(self, address: tuple[str, int]) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(address)
            self._sock.listen(1)
        except OSError:
            # Don't leak the socket if bind/listen fails (e.g. port in use).
            self._sock.close()
            raise

    @property
    def address(self) -> tuple[str, int]:
        """The bound address (resolves an OS-assigned port when 0 was given)."""
        return self._sock.getsockname()

    def accept(self) -> Peer:
        """Block until one peer connects and wrap it in a :class:`Peer`."""
        conn, _ = self._sock.accept()
        return Peer(conn)

    def close(self) -> None:
        """Close the listening socket; already-accepted peers are unaffected."""
        self._sock.close()


class Peer:
    """A connected peer; sends and receives length-prefixed byte frames."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        try:
            # Send each frame immediately instead of buffering (interactive chat).
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass  # not a TCP socket (e.g. an AF_UNIX socketpair in tests)

    @classmethod
    def join(cls, address: tuple[str, int]) -> Peer:
        """Connect to a listening peer at ``address``."""
        return cls(socket.create_connection(address))

    def send_bytes(self, payload: bytes) -> None:
        """Send one framed payload to the connected peer."""
        send_framed(self._sock, payload)

    def recv_bytes(self) -> bytes:
        """Receive one framed payload from the peer.

        Propagates ``PeerDisconnected`` on clean close and ``FramingError`` on a
        protocol violation (see :func:`networking.framing.recv_framed`).
        """
        return recv_framed(self._sock)

    def close(self) -> None:
        """Close the underlying socket."""
        self._sock.close()
