# Bubble v1.1.0 - "Pretty" Terminal UI

**Status:** approved design, ready for planning
**Date:** 2026-08-01
**Scope:** presentation layer only. No changes to the crypto handshake, framing,
replay protection, or the in-memory/fail-closed security model.

## 1. Goal

Turn Bubble from an argument-driven CLI into a friendly, animated terminal app:
a splash banner, keyboard-driven menus, a live waiting screen with a countdown,
and a colourful chat view - built with [`rich`](https://rich.readthedocs.io/) for
rendering and [`questionary`](https://questionary.readthedocs.io/) for menus.

### Explicitly out of scope (dropped during brainstorming)

- Chat-history sync to a late-joining peer.
- Typing before a peer connects. The host **waits only**; the input loop starts
  once the secure channel is established.

## 2. User-visible behaviour

### Launch
- New `start.cmd` (Windows) and `start.sh` (POSIX) wrappers run `python main.py`
  with no arguments so the user can just type `start` in the project directory.
- `python main.py` with **no arguments** clears the screen and opens the
  interactive wizard.
- The existing `python main.py host|join HOST:PORT` form still works
  (backwards-compatible) and skips straight past the menu into the same flow.

### Splash (Style B)
On boot the screen clears and shows a thin outline "BUBBLE" banner with bubble
accents, then `the chat app that forgets`, `v1.1.0`, and `by Leelee`.

### Menu → Host
1. Arrow-key select: **Host a bubble** / **Join a bubble**.
2. Host → arrow-key select: **Local only** (`127.0.0.1`) / **LAN** (auto-detected
   primary IPv4; falls back to `127.0.0.1` with a note if detection fails).
3. Waiting screen: pairing code, the joinable `IP:PORT`, an animated spinner, and
   a live `mm:ss` countdown from 2:00. `Ctrl-C` cancels; timeout exits with the
   existing "No peer joined in time." message.

### Menu → Join
1. Prompt display name.
2. Prompt host address (`IP:PORT`).
3. Prompt pairing code (hidden input, as today).
4. Connect.

### Chat view
- Header: `✓ secure channel established` and `/quit to leave`.
- Each message renders as `[HH:MM] name  text`, timestamp in the **reader's local
  time** (already implemented in v1.0.1).
- **Your own sent messages are echoed** in the same `[HH:MM] name text` format -
  new behaviour; today the local echo is just the raw typed line.
- Each distinct display name gets a colour chosen randomly per session from a
  fixed, readable palette. Colours are assigned locally, so the two peers need
  not agree on them.
- Peer text stays sanitised against terminal control characters (unchanged).

## 3. Architecture

Introduce a `ui/` package (rich/questionary live here and **nowhere else**, so the
domain, crypto, and networking layers stay dependency-free and testable).

```
ui/
  __init__.py
  banner.py     show_splash()            - clear screen, render Style B banner
  prompts.py    the questionary wizard   - main_menu(), host_network(),
                                           ask_name(), ask_address(), ask_code()
  waiting.py    render a Live spinner + mm:ss countdown, driven by a callback
  chat_view.py  ChatRenderer             - colours + formats messages/notices
  palette.py    NameColours              - stable per-session name→colour map
```

### Presentation seam (keeps `ChatSession` free of rich)
`ChatSession` currently calls `print(...)` directly. Replace those calls with an
injected renderer implementing a small protocol:

```python
class ChatRenderer(Protocol):
    def show_message(self, message: Message, is_local: bool) -> None: ...
    def notice(self, text: str) -> None: ...
```

- `ChatSession.__init__` gains a `renderer: ChatRenderer` parameter (default kept
  simple for tests - a no-op/collecting double).
- `_receive_loop` calls `renderer.show_message(message, is_local=False)` instead
  of `print(sanitize_for_terminal(str(message)))`.
- `send_text` calls `renderer.show_message(message, is_local=True)` so the sender
  sees their own name + timestamp.
- `_note(...)` calls `renderer.notice(...)`.

The rich implementation, `ui/chat_view.RichChatRenderer`, owns a `NameColours`
instance and does the sanitising + colouring. Sanitisation stays in `session.py`
as the single source of truth; the renderer calls it.

### LAN IP detection
Add `networking.addressing.local_ipv4() -> str`: open a UDP socket, "connect" to
a public address (no packets sent), read `getsockname()[0]`. On `OSError` return
`"127.0.0.1"`. Pure function, unit-testable via monkeypatching the socket.

### Waiting countdown without extra threads
Extend `Listener.accept` with an optional per-poll callback:

```python
def accept(self, timeout: float | None = None,
           on_wait: Callable[[float], None] | None = None) -> Peer:
```

Each poll iteration invokes `on_wait(remaining_seconds)`. `ui/waiting.py` passes a
callback that updates a `rich.live.Live` spinner + countdown. No background
thread; `Ctrl-C` still fires between polls (as in v1.0.1). The default `on_wait`
is `None`, so existing callers and tests are unaffected.

### Config gathering
`main.py` gains `gather_config(argv) -> SessionConfig` where `SessionConfig`
carries only `mode`, `address`, and `display_name`.
- args present → parse as today.
- no args → run the questionary wizard.
Both paths converge on one `run_session(config)` that does handshake → chat, so
the connection/teardown logic is written once. The pairing code is **not** stored
on the config: `run_session` generates it for a host and prompts for it on join,
keeping the secret's lifetime as short as today.

## 4. Error handling

- Keep the v1.0.1 handlers: `KeyboardInterrupt`/`EOFError` → `Cancelled.`,
  `TimeoutError` → `No peer joined in time.`, `OSError` → `could not connect`.
- `questionary` returns `None` when the user aborts a prompt (Ctrl-C/Esc); treat
  `None` as a cancel and exit cleanly with `Cancelled.`.
- LAN detection failure is handled by falling back to loopback, not raising.
- Rendering must never crash the session: `RichChatRenderer` sanitises first and
  formats defensively.

## 5. Dependencies

Add to `requirements.txt`: `rich` and `questionary` (the latter pulls in
`prompt_toolkit`). Both are widely used and actively maintained. `PyNaCl` stays.

## 6. Testing

Follow the house standard (`unittest`, `tests/*_test.py`, loopback-only, no disk).

- `palette_test.py` - a name maps to a stable colour within a session; different
  names generally differ; unknown names get assigned on first use.
- `addressing_test.py` - `local_ipv4()` returns the socket's address; returns
  `127.0.0.1` when the socket raises `OSError` (monkeypatched).
- `peer_test.py` - extend: `on_wait` is called with a decreasing remaining time
  and still accepts a peer / still times out.
- `session_test.py` - extend: inject a collecting fake renderer; assert
  `show_message(is_local=True)` fires on send and `is_local=False` on receive.
- `main_test.py` - extend: `gather_config` parses args correctly; the no-arg path
  is covered by monkeypatching the wizard functions.
- The interactive rich/questionary rendering itself (banner, Live animation,
  actual keypress capture) is exercised manually, not unit-tested - documented as
  a deliberate gap.

## 7. Versioning & docs

- Minor bump to **1.1.0** (new features, backwards-compatible): `__version__`,
  `CHANGELOG.md` (new `Added` section), and README (badge, usage, run-with-`start`).
- Update README usage to show `start` / the interactive menu as the primary path,
  with the `host|join HOST:PORT` form documented as the power-user shortcut.
```
