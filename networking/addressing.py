"""Discover the machine's primary LAN IPv4 address."""

from __future__ import annotations

import socket

_LOOPBACK = "127.0.0.1"
# Any routable address works; UDP "connect" sends no packets, it just makes the
# OS pick the source interface it would use to reach the internet.
_PROBE_TARGET = ("8.8.8.8", 80)


def local_ipv4() -> str:
    """Return this host's primary LAN IPv4, or loopback if none is reachable."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(_PROBE_TARGET)
        return sock.getsockname()[0]
    except OSError:
        return _LOOPBACK  # no network -> fall back to loopback, never raise
    finally:
        sock.close()
