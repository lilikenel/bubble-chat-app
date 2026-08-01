"""Rich implementation of the session's ChatRenderer: colour + timestamps."""

from __future__ import annotations

import threading

from rich.console import Console
from rich.text import Text

from dom.message import Message
from session import sanitize_for_terminal
from ui.palette import NameColours


class RichChatRenderer:
    """Prints messages as ``[HH:MM] name  text`` with per-name colour."""

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()
        self._colours = NameColours()
        # Serialises the two threads that render through this instance: the main
        # thread (local echo) and the receive thread (incoming messages).
        self._lock = threading.Lock()

    def show_message(self, message: Message, is_local: bool) -> None:
        """Render one message; the sender's own echo replaces their typed line.

        Known limitation: the local echo erases the physical line above the
        cursor, assuming it holds the user's terminal-echoed keystrokes. If a
        peer message arrives *while* the user is mid-line (before they press
        enter), that peer line can be the one erased. Fully avoiding this needs
        per-keystroke input handling, which is out of scope here.
        """
        with self._lock:
            if is_local and self._console.is_terminal:
                # Move up one line, clear it, return to column 0 - so only the
                # formatted echo shows, not the raw keystrokes the terminal drew.
                self._console.file.write("\x1b[1A\x1b[2K\r")
                self._console.file.flush()
            local_time = message.timestamp.astimezone()
            line = Text()
            line.append(f"[{local_time:%H:%M}] ", style="dim")
            line.append(
                f"{message.sender_name}",
                style=f"bold {self._colours.for_name(message.sender_name)}",
            )
            line.append("  ")
            line.append(sanitize_for_terminal(message.text))
            self._console.print(line)

    def notice(self, text: str) -> None:
        """Print a dimmed parenthetical status line (e.g. peer disconnected)."""
        with self._lock:
            self._console.print(f"\n[dim]({sanitize_for_terminal(text)})[/dim]")
