"""The startup splash: clear the screen and show the Bubble banner."""

from __future__ import annotations

from rich.console import Console

_BANNER = r"""        .oOo.
   ___  _  _ ___ ___ _    ___
  | _ )| || | _ ) _ ) |  | __|
  | _ \| || | _ \ _ \ |_ | _|
  |___/ \__/|___/___/___||___|
              °oO"""


def show_splash(console: Console, version: str, author: str) -> None:
    """Clear the terminal and render the banner, tagline, version, and author."""
    console.clear()
    console.print(f"[cyan]{_BANNER}[/cyan]")
    console.print()
    console.print("  [dim]the chat app that forgets[/dim]")
    console.print(f"  [dim]v{version} - by {author}[/dim]")
    console.print()
