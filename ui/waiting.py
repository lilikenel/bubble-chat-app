"""A live 'waiting for a peer' screen: spinner + mm:ss countdown."""

from __future__ import annotations

from collections.abc import Callable

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table


def _format_remaining(remaining: float) -> str:
    if remaining == float("inf"):
        return "--:--"
    total = max(0, int(remaining))
    return f"{total // 60:02d}:{total % 60:02d}"


class WaitingScreen:
    """Wraps a rich Live; feed it ``update(remaining)`` from accept's on_wait."""

    def __init__(self, console: Console) -> None:
        self._spinner = Spinner("dots", style="cyan")
        self._live = Live(console=console, refresh_per_second=8, transient=True)

    def __enter__(self) -> Callable[[float], None]:
        self._live.start()
        return self.update

    def __exit__(self, *exc: object) -> None:
        self._live.stop()

    def update(self, remaining: float) -> None:
        """Redraw the spinner and countdown for ``remaining`` seconds left."""
        row = Table.grid(padding=(0, 1))
        row.add_row(
            self._spinner,
            f"Waiting for someone to join…  closing in "
            f"[white]{_format_remaining(remaining)}[/white]",
        )
        self._live.update(row)
