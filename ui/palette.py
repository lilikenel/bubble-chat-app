"""Assign each display name a stable, readable colour for one session."""

from __future__ import annotations

import random

# Readable rich colour names that show up well on a dark terminal.
PALETTE: tuple[str, ...] = (
    "cyan",
    "magenta",
    "green",
    "yellow",
    "bright_blue",
    "orange1",
    "hot_pink",
    "spring_green2",
    "turquoise2",
    "medium_purple",
)


class NameColours:
    """Maps display names to colours, consistently within a single session."""

    def __init__(self) -> None:
        self._assigned: dict[str, str] = {}

    def for_name(self, name: str) -> str:
        """Return this name's colour, assigning a random one on first sight."""
        if name not in self._assigned:
            self._assigned[name] = random.choice(PALETTE)
        return self._assigned[name]
