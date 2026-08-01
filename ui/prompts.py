"""Keyboard-driven setup wizard built on questionary."""

from __future__ import annotations

import questionary

from networking.addressing import local_ipv4

HOST = "host"
JOIN = "join"
LOCAL = "local"
LAN = "lan"

DEFAULT_PORT = 5050


def main_menu() -> str | None:
    """Ask whether to host or join. Returns HOST, JOIN, or None if cancelled."""
    return questionary.select(
        "What would you like to do?",
        choices=[
            questionary.Choice("Host a bubble", value=HOST),
            questionary.Choice("Join a bubble", value=JOIN),
        ],
    ).ask()


def host_network() -> tuple[str, int] | None:
    """Choose Local or LAN and return the (ip, port) to bind, or None."""
    choice = questionary.select(
        "Where should peers reach you?",
        choices=[
            questionary.Choice("Local only  (this machine)", value=LOCAL),
            questionary.Choice(f"LAN  ({local_ipv4()})", value=LAN),
        ],
    ).ask()
    if choice is None:
        return None
    ip = "127.0.0.1" if choice == LOCAL else local_ipv4()
    return ip, DEFAULT_PORT


def ask_name() -> str | None:
    """Prompt for a display name, defaulting to 'anon'. None if cancelled."""
    name = questionary.text("Your display name:").ask()
    if name is None:
        return None
    return name.strip() or "anon"


def ask_address() -> tuple[str, int] | None:
    """Prompt for HOST:PORT and parse it. Re-asks on malformed input."""
    while True:
        raw = questionary.text("Host address (IP:PORT):").ask()
        if raw is None:
            return None
        host, _, port = raw.strip().rpartition(":")
        if host and port.isdigit():
            return host, int(port)
        questionary.print("  Enter as IP:PORT, e.g. 192.168.3.198:5050")


def ask_code() -> str | None:
    """Prompt for the pairing code with hidden input. None if cancelled."""
    return questionary.password("Pairing code:").ask()
