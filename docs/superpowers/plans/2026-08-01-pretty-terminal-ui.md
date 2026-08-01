# Pretty Terminal UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **PROJECT RULE - DO NOT COMMIT.** The user commits manually. Every task ends with a **Checkpoint** (run the suite) instead of a commit step. Never run `git commit`.

**Goal:** Turn Bubble into a friendly animated terminal app - banner splash, keyboard-driven menus, a live waiting countdown, and a colourful chat view - without touching the crypto/security model.

**Architecture:** A new `ui/` package quarantines `rich` and `questionary` so the domain, networking, and crypto layers stay dependency-free and unit-testable. `ChatSession` renders through an injected `ChatRenderer` protocol instead of `print`. `Listener.accept` gains an `on_wait` callback to drive the countdown without extra threads. `main.py` unifies CLI args and the interactive wizard into one `run_session(config)`.

**Tech Stack:** Python 3.13, `rich` (rendering), `questionary` (menus), `PyNaCl` (unchanged), `unittest`.

---

## File Structure

- Create: `networking/addressing.py` - `local_ipv4()` LAN IP detection.
- Create: `ui/__init__.py`, `ui/palette.py`, `ui/chat_view.py`, `ui/banner.py`, `ui/prompts.py`, `ui/waiting.py`.
- Create: `start.cmd`, `start.sh` - no-arg launchers.
- Create tests: `tests/addressing_test.py`, `tests/palette_test.py`.
- Modify: `networking/peer.py` - add `on_wait` to `accept`.
- Modify: `session.py` - `ChatRenderer` protocol, `_NullRenderer`, inject renderer, local echo.
- Modify: `main.py` - `SessionConfig`, `gather_config`, `run_session`, no-arg wizard.
- Modify tests: `tests/peer_test.py`, `tests/session_test.py`, `tests/main_test.py`.
- Modify: `requirements.txt`, `CHANGELOG.md`, `README.md`, `main.py` (`__version__`).

Run the full suite anywhere with:
`python -m unittest discover -s tests -p "*_test.py"`

---

## Task 1: Add dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add rich and questionary**

Edit `requirements.txt` to read:

```
PyNaCl>=1.6.2
rich>=13.7
questionary>=2.0
```

- [ ] **Step 2: Install**

Run: `pip install -r requirements.txt`
Expected: `rich`, `questionary`, and `prompt_toolkit` install successfully.

- [ ] **Step 3: Checkpoint - imports resolve**

Run: `python -c "import rich, questionary; print('ok')"`
Expected: prints `ok`.

---

## Task 2: LAN IP detection (`networking/addressing.py`)

**Files:**
- Create: `networking/addressing.py`
- Test: `tests/addressing_test.py`

- [ ] **Step 1: Write the failing test**

Create `tests/addressing_test.py`:

```python
"""Tests for local IPv4 detection."""

from __future__ import annotations

import socket
import unittest
from unittest import mock

from networking.addressing import local_ipv4


class LocalIpv4Test(unittest.TestCase):
    def test_returns_socket_source_address(self) -> None:
        fake_sock = mock.MagicMock()
        fake_sock.getsockname.return_value = ("192.168.3.198", 51234)
        with mock.patch("socket.socket", return_value=fake_sock):
            self.assertEqual(local_ipv4(), "192.168.3.198")
        fake_sock.close.assert_called_once()

    def test_falls_back_to_loopback_on_error(self) -> None:
        fake_sock = mock.MagicMock()
        fake_sock.connect.side_effect = OSError("no network")
        with mock.patch("socket.socket", return_value=fake_sock):
            self.assertEqual(local_ipv4(), "127.0.0.1")
        fake_sock.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.addressing_test -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'networking.addressing'`.

- [ ] **Step 3: Write minimal implementation**

Create `networking/addressing.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.addressing_test -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Checkpoint - full suite green**

Run: `python -m unittest discover -s tests -p "*_test.py"`
Expected: OK.

---

## Task 3: `Listener.accept` gains an `on_wait` callback

**Files:**
- Modify: `networking/peer.py` (the `accept` method)
- Test: `tests/peer_test.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/peer_test.py` inside `ListenerTest` (imports `time` and `concurrent.futures` already present):

```python
    def test_on_wait_is_called_with_decreasing_remaining(self) -> None:
        listener = Listener((LOOPBACK, 0))
        self.addCleanup(listener.close)
        seen: list[float] = []

        with self.assertRaises(TimeoutError):
            listener.accept(
                timeout=Listener._ACCEPT_POLL_SECONDS * 2,
                on_wait=seen.append,
            )

        self.assertTrue(seen)
        self.assertEqual(seen, sorted(seen, reverse=True))

    def test_on_wait_still_accepts_a_peer(self) -> None:
        listener = Listener((LOOPBACK, 0))
        self.addCleanup(listener.close)
        seen: list[float] = []
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.addCleanup(executor.shutdown)
        accept_future = executor.submit(
            listener.accept, None, seen.append
        )

        client = Peer.join(listener.address)
        self.addCleanup(client.close)
        server = accept_future.result(timeout=5)
        self.addCleanup(server.close)

        client.send_bytes(b"hi")
        self.assertEqual(server.recv_bytes(), b"hi")
        self.assertTrue(seen)  # infinite remaining, but callback fired
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.peer_test -v`
Expected: FAIL - `accept()` got an unexpected keyword argument `on_wait`.

- [ ] **Step 3: Update `accept`**

In `networking/peer.py`, add `from collections.abc import Callable` to the imports (top of file, after `import time`), and replace the `accept` method with:

```python
    def accept(
        self,
        timeout: float | None = None,
        on_wait: Callable[[float], None] | None = None,
    ) -> Peer:
        """Block until one peer connects and wrap it in a :class:`Peer`.

        Polls with a short timeout so a Ctrl-C is delivered promptly (see
        ``_ACCEPT_POLL_SECONDS``). If ``timeout`` seconds elapse with no peer,
        raises :class:`TimeoutError`. ``on_wait`` is called once per poll with
        the seconds remaining (``inf`` when no timeout), to drive a countdown.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        self._sock.settimeout(self._ACCEPT_POLL_SECONDS)
        while True:
            if deadline is None:
                remaining = float("inf")
            else:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"no peer connected within {timeout:.0f}s")
            if on_wait is not None:
                on_wait(remaining)
            try:
                conn, _ = self._sock.accept()
            except TimeoutError:
                continue  # no peer yet - loop so a pending SIGINT can fire
            conn.settimeout(None)  # hand back a plain blocking peer socket
            return Peer(conn)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.peer_test -v`
Expected: PASS (all Listener + Peer tests).

- [ ] **Step 5: Checkpoint - full suite green**

Run: `python -m unittest discover -s tests -p "*_test.py"`
Expected: OK.

---

## Task 4: Presentation seam in `ChatSession`

Decouple `ChatSession` from `print` via a `ChatRenderer` protocol, and echo the sender's own messages.

**Files:**
- Modify: `session.py`
- Test: `tests/session_test.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/session_test.py` a new test class (after `ChatSessionTest`):

```python
class _RecordingRenderer:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bool]] = []
        self.notices: list[str] = []

    def show_message(self, message: Message, is_local: bool) -> None:
        self.messages.append((message.text, is_local))

    def notice(self, text: str) -> None:
        self.notices.append(text)


class RendererSeamTest(unittest.TestCase):
    def _pair_with_renderers(self) -> SimpleNamespace:
        host_sock, joiner_sock = socket.socketpair()
        self.addCleanup(host_sock.close)
        self.addCleanup(joiner_sock.close)
        h2j, j2h = random_bytes(32), random_bytes(32)
        host_render, joiner_render = _RecordingRenderer(), _RecordingRenderer()
        host = ChatSession(
            Peer(host_sock), SecureChannel(h2j, j2h), Bubble(User("Host")),
            renderer=host_render,
        )
        joiner = ChatSession(
            Peer(joiner_sock), SecureChannel(j2h, h2j), Bubble(User("Joiner")),
            renderer=joiner_render,
        )
        return SimpleNamespace(
            host=host, joiner=joiner,
            host_render=host_render, joiner_render=joiner_render,
        )

    def test_sender_sees_own_message_as_local(self) -> None:
        ctx = self._pair_with_renderers()

        ctx.host.send_text("mine")

        self.assertIn(("mine", True), ctx.host_render.messages)

    def test_receiver_sees_peer_message_as_remote(self) -> None:
        ctx = self._pair_with_renderers()

        ctx.host.send_text("yours")
        ctx.joiner.receive_message()

        self.assertIn(("yours", False), ctx.joiner_render.messages)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.session_test -v`
Expected: FAIL - `ChatSession.__init__` got an unexpected keyword argument `renderer`.

- [ ] **Step 3: Add the protocol and null renderer**

In `session.py`, add to the imports near the top:

```python
from typing import Protocol
```

and after the module constants (below `QUIT_COMMAND`) add:

```python
class ChatRenderer(Protocol):
    """How a session surfaces messages and notices to the user."""

    def show_message(self, message: Message, is_local: bool) -> None: ...

    def notice(self, text: str) -> None: ...


class _NullRenderer:
    """A renderer that discards everything - the default for tests/headless use."""

    def show_message(self, message: Message, is_local: bool) -> None:
        pass

    def notice(self, text: str) -> None:
        pass
```

- [ ] **Step 4: Inject the renderer and echo local sends**

In `session.py`, change `ChatSession.__init__` signature and body:

```python
    def __init__(
        self,
        peer: Peer,
        channel: SecureChannel,
        bubble: Bubble,
        renderer: ChatRenderer | None = None,
    ) -> None:
        self._peer = peer
        self._channel = channel
        self._bubble = bubble
        self._bubble.channel = channel  # so pop() wipes the same channel
        self._renderer: ChatRenderer = renderer or _NullRenderer()
        self._send_sequence = 0
        self._last_received_sequence = -1
        self._stop = threading.Event()
```

In `send_text`, after `self._bubble.add(message)` and before `return message`, add:

```python
        self._renderer.show_message(message, is_local=True)
```

In `_receive_loop`, replace:

```python
                print(sanitize_for_terminal(str(message)))
```

with:

```python
                self._renderer.show_message(message, is_local=False)
```

In `_note`, replace `print(f"\n({text})")` with:

```python
            self._renderer.notice(text)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest tests.session_test -v`
Expected: PASS (existing + 2 new tests).

- [ ] **Step 6: Checkpoint - full suite green**

Run: `python -m unittest discover -s tests -p "*_test.py"`
Expected: OK. (Existing tests still pass because `renderer` defaults to the null renderer.)

---

## Task 5: Per-session name colours (`ui/palette.py`)

**Files:**
- Create: `ui/__init__.py`, `ui/palette.py`
- Test: `tests/palette_test.py`

- [ ] **Step 1: Create the package marker**

Create `ui/__init__.py`:

```python
"""Terminal presentation layer (rich + questionary). Kept out of the core."""
```

- [ ] **Step 2: Write the failing test**

Create `tests/palette_test.py`:

```python
"""Tests for per-session name colour assignment."""

from __future__ import annotations

import unittest

from ui.palette import NameColours, PALETTE


class NameColoursTest(unittest.TestCase):
    def test_same_name_keeps_its_colour(self) -> None:
        colours = NameColours()

        first = colours.for_name("nomfundo")
        second = colours.for_name("nomfundo")

        self.assertEqual(first, second)

    def test_colours_come_from_the_palette(self) -> None:
        colours = NameColours()

        self.assertIn(colours.for_name("lilike"), PALETTE)

    def test_distinct_names_get_tracked_separately(self) -> None:
        colours = NameColours()

        colours.for_name("a")
        colours.for_name("b")

        self.assertEqual(len(colours._assigned), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m unittest tests.palette_test -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'ui.palette'`.

- [ ] **Step 4: Write minimal implementation**

Create `ui/palette.py`:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.palette_test -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Checkpoint - full suite green**

Run: `python -m unittest discover -s tests -p "*_test.py"`
Expected: OK.

---

## Task 6: Rich chat renderer (`ui/chat_view.py`)

Renders messages with colour + local time, sanitising peer text. Rendering is exercised manually (rich output is not unit-tested), but the class is importable and pure enough to smoke-test.

**Files:**
- Create: `ui/chat_view.py`

- [ ] **Step 1: Implement the renderer**

Create `ui/chat_view.py`:

```python
"""Rich implementation of the session's ChatRenderer: colour + timestamps."""

from __future__ import annotations

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

    def show_message(self, message: Message, is_local: bool) -> None:
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
        self._console.print(f"\n[dim]({sanitize_for_terminal(text)})[/dim]")
```

- [ ] **Step 2: Smoke-test rendering manually**

Run:

```bash
python -c "
from datetime import datetime, timezone
from uuid import uuid4
from dom.message import Message
from ui.chat_view import RichChatRenderer
r = RichChatRenderer()
r.show_message(Message('hello there', 'nomfundo', uuid4(), datetime.now(timezone.utc)), False)
r.show_message(Message('hi back', 'lilike', uuid4(), datetime.now(timezone.utc)), True)
r.notice('peer disconnected - press enter to exit')
"
```

Expected: two coloured `[HH:MM] name  text` lines (different name colours) in your local time, then a dim notice.

- [ ] **Step 3: Checkpoint - full suite green**

Run: `python -m unittest discover -s tests -p "*_test.py"`
Expected: OK (no new automated tests; existing suite unaffected).

---

## Task 7: Splash banner (`ui/banner.py`)

**Files:**
- Create: `ui/banner.py`

- [ ] **Step 1: Implement the banner (Style B)**

Create `ui/banner.py`:

```python
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
```

- [ ] **Step 2: Smoke-test manually**

Run: `python -c "from rich.console import Console; from ui.banner import show_splash; show_splash(Console(), '1.1.0', 'Leelee')"`
Expected: screen clears, cyan BUBBLE banner with tagline, version, author.

- [ ] **Step 3: Checkpoint - full suite green**

Run: `python -m unittest discover -s tests -p "*_test.py"`
Expected: OK.

---

## Task 8: Interactive wizard (`ui/prompts.py`)

**Files:**
- Create: `ui/prompts.py`

- [ ] **Step 1: Implement the questionary wizard**

Create `ui/prompts.py`. Each function returns `None` when the user aborts (Ctrl-C/Esc), which callers treat as a cancel.

```python
"""Keyboard-driven setup wizard built on questionary."""

from __future__ import annotations

import questionary

from networking.addressing import local_ipv4

HOST = "host"
JOIN = "join"
LOCAL = "local"
LAN = "lan"


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
    return ip, 5050


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
```

- [ ] **Step 2: Smoke-test the menu manually (optional, interactive)**

Run: `python -c "from ui.prompts import main_menu; print(main_menu())"`
Expected: an arrow-key menu; selecting prints `host` or `join`. (Ctrl-C prints `None`.)

- [ ] **Step 3: Checkpoint - full suite green**

Run: `python -m unittest discover -s tests -p "*_test.py"`
Expected: OK.

---

## Task 9: Live waiting countdown (`ui/waiting.py`)

**Files:**
- Create: `ui/waiting.py`

- [ ] **Step 1: Implement the countdown driver**

Create `ui/waiting.py`:

```python
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
        row = Table.grid(padding=(0, 1))
        row.add_row(
            self._spinner,
            f"Waiting for someone to join…  closing in "
            f"[white]{_format_remaining(remaining)}[/white]",
        )
        self._live.update(row)
```

- [ ] **Step 2: Smoke-test manually**

Run:

```bash
python -c "
import time
from rich.console import Console
from ui.waiting import WaitingScreen
with WaitingScreen(Console()) as tick:
    for r in (120, 119, 118):
        tick(r); time.sleep(0.4)
"
```

Expected: an animated spinner with `closing in 02:00 → 01:59 → 01:58`, then it clears.

- [ ] **Step 3: Checkpoint - full suite green**

Run: `python -m unittest discover -s tests -p "*_test.py"`
Expected: OK.

---

## Task 10: Wire it together in `main.py`

Unify args + wizard into `SessionConfig` / `gather_config`, and run through one `run_session`. Splash, menus, waiting screen, and the rich renderer are plugged in here.

**Files:**
- Modify: `main.py`
- Test: `tests/main_test.py`

- [ ] **Step 1: Write the failing tests**

Replace `tests/main_test.py` with:

```python
"""Tests for main.py argument parsing and config gathering."""

from __future__ import annotations

import unittest
from unittest import mock

from main import SessionConfig, gather_config, parse_args


class ParseArgsTest(unittest.TestCase):
    def test_parses_host_mode(self) -> None:
        self.assertEqual(
            parse_args(["host", "127.0.0.1:5050"]),
            ("host", ("127.0.0.1", 5050)),
        )

    def test_parses_join_mode(self) -> None:
        self.assertEqual(
            parse_args(["join", "localhost:9000"]),
            ("join", ("localhost", 9000)),
        )

    def test_rejects_unknown_mode(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["serve", "127.0.0.1:5050"])

    def test_rejects_address_without_port(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["host", "127.0.0.1"])


class GatherConfigTest(unittest.TestCase):
    def test_args_bypass_the_wizard(self) -> None:
        config = gather_config(["host", "127.0.0.1:5050"], name="cli")

        self.assertEqual(
            config,
            SessionConfig(mode="host", address=("127.0.0.1", 5050), display_name="cli"),
        )

    def test_no_args_runs_the_host_wizard(self) -> None:
        with mock.patch("main.prompts") as prompts:
            prompts.HOST = "host"
            prompts.main_menu.return_value = "host"
            prompts.host_network.return_value = ("192.168.3.198", 5050)
            prompts.ask_name.return_value = "lilike"

            config = gather_config([], name=None)

        self.assertEqual(
            config,
            SessionConfig(
                mode="host",
                address=("192.168.3.198", 5050),
                display_name="lilike",
            ),
        )

    def test_cancelled_wizard_returns_none(self) -> None:
        with mock.patch("main.prompts") as prompts:
            prompts.main_menu.return_value = None

            self.assertIsNone(gather_config([], name=None))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.main_test -v`
Expected: FAIL - cannot import `SessionConfig` / `gather_config` from `main`.

- [ ] **Step 3: Rewrite `main.py`**

Replace the whole of `main.py` with:

```python
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
        console.print("\n[red]Handshake failed - wrong code or tampering. Aborting.[/red]")
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.main_test -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Checkpoint - full suite green**

Run: `python -m unittest discover -s tests -p "*_test.py"`
Expected: OK.

---

## Task 11: Launch wrappers (`start.cmd`, `start.sh`)

**Files:**
- Create: `start.cmd`, `start.sh`

- [ ] **Step 1: Create the Windows wrapper**

Create `start.cmd`:

```bat
@echo off
python "%~dp0main.py" %*
```

- [ ] **Step 2: Create the POSIX wrapper**

Create `start.sh`:

```bash
#!/usr/bin/env bash
exec python "$(dirname "$0")/main.py" "$@"
```

- [ ] **Step 3: Make it executable (POSIX)**

Run: `chmod +x start.sh`
Expected: no output; `start.sh` is now executable.

- [ ] **Step 4: Manual smoke-test (interactive)**

Run: `./start.sh` (or `start` in a Windows terminal).
Expected: screen clears, banner shows, arrow-key Host/Join menu appears. `Ctrl-C` exits with `Cancelled.` and no traceback.

- [ ] **Step 5: Checkpoint - full suite green**

Run: `python -m unittest discover -s tests -p "*_test.py"`
Expected: OK.

---

## Task 12: Version bump and docs

**Files:**
- Modify: `CHANGELOG.md`, `README.md` (`main.py` `__version__` already set to `1.1.0` in Task 10)

- [ ] **Step 1: Add the changelog entry**

Insert into `CHANGELOG.md` above the `## [1.0.1]` section:

```markdown
## [1.1.0] - 2026-08-01

**The "pretty" release.** A friendly terminal UI - no arguments required.

### Added

- **Interactive launcher.** Type `start` (or run `python main.py` with no
  arguments) for a cleared screen, a BUBBLE banner, and keyboard-driven menus.
- **Host: Local vs LAN.** Choose loopback or your auto-detected LAN IPv4.
- **Live waiting screen** with an animated spinner and an `mm:ss` countdown to
  the 2-minute timeout.
- **Colourful chat.** Each display name gets its own colour (assigned locally
  per session); your own messages now echo with your name and timestamp.

### Changed

- `rich` and `questionary` are now dependencies (presentation only; the crypto
  and networking layers stay dependency-free).
- The `python main.py host|join HOST:PORT` form still works as a shortcut.

[1.1.0]: https://github.com/lilikenel/bubble-chat-app/releases/tag/v1.1.0
```

- [ ] **Step 2: Update the README badge and usage**

In `README.md`, change the badge line to `v1.1.0`, and update the usage/quick-start section to show `start` (or `python main.py` with no args) as the primary path, documenting `python main.py host|join HOST:PORT` as the shortcut. Update the changelog note to reference **v1.1.0** as the latest release. (Match the existing README's wording and structure.)

- [ ] **Step 3: Verify version references are consistent**

Run: `grep -rn "1\.1\.0\|1\.0\.1" main.py README.md CHANGELOG.md`
Expected: `main.py` shows `__version__ = "1.1.0"`; README badge and changelog note show `v1.1.0`; CHANGELOG has both `[1.1.0]` and `[1.0.1]` sections.

- [ ] **Step 4: Final checkpoint - full suite green + manual run**

Run: `python -m unittest discover -s tests -p "*_test.py"`
Expected: OK.

Then manually run `./start.sh`, host a Local bubble, join from a second terminal, exchange a couple of messages, and confirm: coloured names, local-time timestamps, your own echoed messages, and a clean `/quit`.

---

## Self-Review Notes

- **Spec coverage:** launcher/no-args (T10–11), Style B banner (T7), Host/Join menu (T8), Local/LAN + auto IP (T2, T8), waiting countdown (T3, T9), colours + local echo + timestamps (T4–6), deps (T1), version/docs (T12). All spec sections map to a task.
- **Out of scope honoured:** no history sync, no type-while-waiting - the host `accept` blocks behind the waiting screen and the input loop only starts after `SecureChannel.establish`.
- **Type consistency:** `SessionConfig(mode, address, display_name)`, `gather_config(argv, name)`, `Listener.accept(timeout, on_wait)`, `ChatRenderer.show_message(message, is_local)` / `notice(text)`, `NameColours.for_name(name)`, and `prompts.HOST/JOIN` constants are used identically across tasks.
- **Known manual-only coverage:** the interactive rendering (banner, Live spinner, questionary keypresses) is smoke-tested by hand, not unit-tested - a deliberate, documented gap.
```
