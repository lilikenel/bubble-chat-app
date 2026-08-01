"""Entry point: run a Bubble chat as host or joiner.

Run with no arguments for the interactive menu, or use the shortcut form:
    python main.py host 127.0.0.1:5050   # generates a pairing code, waits
    python main.py join 127.0.0.1:5050   # prompts for the pairing code
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from rich.console import Console

from dom.bubble import Bubble
from dom.user import User
from networking.framing import FramingError, PeerDisconnected
from networking.peer import Listener, Peer
from security.pairing import make_pairing_code
from security.secure_channel import HOST, JOINER, HandshakeError, SecureChannel
from session import ChatSession
from ui import prompts
from ui.banner import show_splash
from ui.chat_view import RichChatRenderer
from ui.waiting import WaitingScreen

__version__ = "1.1.0"
__author__ = "Leelee"

# Give up hosting after this long with no peer, rather than waiting forever.
WAIT_FOR_PEER_SECONDS = 120


@dataclass(frozen=True)
class SessionConfig:
    """Everything needed to start a session except the pairing code."""

    mode: str
    address: tuple[str, int]
    display_name: str


def parse_args(argv: list[str]) -> tuple[str, tuple[str, int]]:
    """Parse ['host'|'join', 'HOST:PORT'] into (mode, (host, port))."""
    if len(argv) != 2 or argv[0] not in ("host", "join"):
        raise SystemExit("usage: python main.py [host|join] HOST:PORT")
    host, _, port = argv[1].rpartition(":")
    if not host or not port.isdigit():
        raise SystemExit("address must be HOST:PORT, e.g. 127.0.0.1:5050")
    return argv[0], (host, int(port))


def gather_config(argv: list[str], name: str | None) -> SessionConfig | None:
    """Build a SessionConfig from args, or interactively. None if cancelled."""
    if argv:
        mode, address = parse_args(argv)
        return SessionConfig(mode, address, name or "anon")

    mode = prompts.main_menu()
    if mode is None:
        return None
    if mode == prompts.HOST:
        display_name = prompts.ask_name()
        if display_name is None:
            return None
        address = prompts.host_network()
        if address is None:
            return None
        return SessionConfig(mode="host", address=address, display_name=display_name)

    display_name = prompts.ask_name()
    if display_name is None:
        return None
    address = prompts.ask_address()
    if address is None:
        return None
    return SessionConfig(mode="join", address=address, display_name=display_name)


def _open_connection(
    config: SessionConfig, console: Console
) -> tuple[Peer, str, bytes]:
    """Open the connection and obtain the pairing code (never persisted)."""
    if config.mode == "host":
        code = make_pairing_code()
        console.print("\nShare this pairing code [dim](never stored)[/dim]:")
        console.print(f"\n    [yellow]{code}[/yellow]\n")
        ip, port = config.address
        console.print(f"Peers can join at [bold]{ip}:{port}[/bold]\n")
        listener = Listener(config.address)
        try:
            with WaitingScreen(console) as tick:
                peer = listener.accept(timeout=WAIT_FOR_PEER_SECONDS, on_wait=tick)
        finally:
            listener.close()
        return peer, HOST, code.encode("utf-8")

    code = prompts.ask_code()
    if code is None:
        raise KeyboardInterrupt
    return Peer.join(config.address), JOINER, code.strip().encode("utf-8")


def main(argv: list[str]) -> None:
    console = Console()
    show_splash(console, __version__, __author__)
    try:
        config = gather_config(argv, name=None)
        if config is None:
            raise SystemExit("\nCancelled.")
        peer, role, code = _open_connection(config, console)
    except (KeyboardInterrupt, EOFError):
        raise SystemExit("\nCancelled.")
    except TimeoutError:
        # OSError subclass, so this must precede the generic handler below.
        raise SystemExit("\nNo peer joined in time. Exiting.")
    except OSError as error:
        raise SystemExit(f"could not connect: {error}")

    bubble = Bubble(User(config.display_name))
    session: ChatSession | None = None
    try:
        channel = SecureChannel.establish(peer, role, code)
        session = ChatSession(peer, channel, bubble, renderer=RichChatRenderer(console))
        console.print("\n[green]✓ secure channel established[/green]")
        console.print("[dim]/quit to leave[/dim]\n")
        session.run()
    except HandshakeError:
        console.print(
            "\n[red]Handshake failed - wrong code or tampering. Aborting.[/red]"
        )
    except (PeerDisconnected, FramingError, OSError) as error:
        console.print(f"\n[red]Connection error: {error}[/red]")
    finally:
        if session is not None:
            session.close()
        else:
            peer.close()
            bubble.pop()


if __name__ == "__main__":
    main(sys.argv[1:])
