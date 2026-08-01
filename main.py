"""Entry point: run a Bubble chat as host or joiner.

Usage:
    python main.py host 127.0.0.1:5050   # generates a pairing code, waits for a peer
    python main.py join 127.0.0.1:5050   # prompts for the pairing code, connects
"""

from __future__ import annotations

import sys
from getpass import getpass

from dom.bubble import Bubble
from dom.user import User
from networking.framing import FramingError, PeerDisconnected
from networking.peer import Listener, Peer
from security.pairing import make_pairing_code
from security.secure_channel import HOST, JOINER, HandshakeError, SecureChannel
from session import ChatSession

__version__ = "1.0.0"


def parse_args(argv: list[str]) -> tuple[str, tuple[str, int]]:
    """Parse ['host'|'join', 'HOST:PORT'] into (mode, (host, port))."""
    if len(argv) != 2 or argv[0] not in ("host", "join"):
        raise SystemExit("usage: python main.py [host|join] HOST:PORT")
    host, _, port = argv[1].rpartition(":")
    if not host or not port.isdigit():
        raise SystemExit("address must be HOST:PORT, e.g. 127.0.0.1:5050")
    return argv[0], (host, int(port))


def _connect(mode: str, address: tuple[str, int]) -> tuple[Peer, str, bytes]:
    """Open the connection and obtain the pairing code (which is never persisted)."""
    if mode == "host":
        code = make_pairing_code()
        print("Share this pairing code with your peer (it is never stored):")
        print(f"\n    {code}\n")
        listener = Listener(address)
        print(f"Waiting for a peer to join on {address[0]}:{address[1]} ...")
        try:
            peer = listener.accept()
        finally:
            listener.close()
        return peer, HOST, code.encode("utf-8")
    code = getpass("Enter the pairing code: ").strip()
    return Peer.join(address), JOINER, code.encode("utf-8")


def main(argv: list[str]) -> None:
    mode, address = parse_args(argv)
    print(f"Bubble v{__version__} — the chat app that forgets\n")
    name = input("Display name: ").strip() or "anon"
    try:
        peer, role, code = _connect(mode, address)
    except OSError as error:
        raise SystemExit(f"could not connect: {error}")

    bubble = Bubble(User(name))
    session: ChatSession | None = None
    try:
        channel = SecureChannel.establish(peer, role, code)
        session = ChatSession(peer, channel, bubble)
        print("\nSecure channel established. Type messages; /quit to leave.\n")
        session.run()
    except HandshakeError:
        print("\nHandshake failed — wrong pairing code or tampering. Aborting.")
    except (PeerDisconnected, FramingError, OSError) as error:
        print(f"\nConnection error: {error}")
    finally:
        if session is not None:
            session.close()
        else:
            peer.close()
            bubble.pop()


if __name__ == "__main__":
    main(sys.argv[1:])
