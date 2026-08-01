# Changelog

All notable changes to Bubble are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-08-01

**The "pretty" release.** A friendly terminal UI - no arguments required.

### Added

- **Interactive launcher.** Run `python main.py` with no arguments for a
  cleared screen, a BUBBLE banner, and keyboard-driven menus.
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

## [1.0.1] - 2026-08-01

**Bug-fix release.** Correct timestamps and cleaner start-up behaviour; no
protocol or on-the-wire changes.

### Fixed

- **Timestamps now show in your local time.** Messages are still stamped in UTC
  on the wire, but each side renders them in its own local timezone, so the
  clock matches your wall clock instead of showing UTC.
- **Graceful cancel before connecting.** Pressing `Ctrl-C` (or `EOF`) at the
  display-name or pairing-code prompt now exits cleanly with `Cancelled.`
  instead of printing a traceback.
- **`Ctrl-C` works while the host waits.** The host's accept loop now polls, so
  a `Ctrl-C` while waiting for a peer is delivered promptly (previously the
  blocking `accept()` swallowed it on Windows until a peer connected).

### Added

- **Host wait timeout.** The host now gives up after 2 minutes if no peer
  connects, exiting with `No peer joined in time.` instead of waiting forever.

## [1.0.0] - 2026-08-01

**First official release.** A secure, ephemeral, peer-to-peer terminal chat
for two people.

### Added

- **Direct peer-to-peer chat** over TCP - one side hosts, the other joins. No
  server, no relay, no accounts.
- **Out-of-band pairing code** (128-bit, CSPRNG) that authenticates the
  connection.
- **Authenticated handshake**: ephemeral X25519 key exchange + Argon2id over the
  pairing code + mutual key confirmation. Per-session forward secrecy; a wrong
  code, tampering, or an impostor fails closed.
- **End-to-end encrypted messages** (XSalsa20-Poly1305 via NaCl `SecretBox`),
  one key per direction, with **replay/reorder protection** (a monotonic
  sequence number sealed inside each message).
- **In-memory only**: nothing is written to disk. Conversation and keys are
  wiped on exit (`/quit`, `Ctrl-C`, or peer disconnect).
- **Terminal UI**: `python main.py host|join HOST:PORT`, hidden pairing-code
  entry, `/quit` to leave.

[1.0.1]: https://github.com/lilikenel/bubble-chat-app/releases/tag/v1.0.1
[1.0.0]: https://github.com/lilikenel/bubble-chat-app/releases/tag/v1.0.0
