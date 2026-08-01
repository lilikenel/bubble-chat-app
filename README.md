# Bubble 🫧

**The chat app that forgets.** Start a Bubble with a friend, chat end-to-end
encrypted over a direct peer-to-peer connection, then pop the Bubble - every
message and key vanishes. Nothing is ever written to disk.

This is an app I wrote to teach myself more about Diffie-Hellman key exchange. Don't use it to replace Signal.

`v1.1.0` · Python 3.10+ · terminal · GPL-3.0

---

## What it is

Bubble is a small, security-first **terminal** chat for **two people**. There is
**no server and no accounts** - the two peers connect directly. You authenticate
the connection with a one-time **pairing code** you share out-of-band (say it
over the phone), and from then on every message is end-to-end encrypted. When you
leave, the conversation and all secrets are wiped from memory.

## How it works (the short version)

1. One person **hosts** (waits for a connection); the other **joins**.
2. Bubble generates a random **pairing code**; you read it to your friend over a
   separate, trusted channel.
3. A handshake uses that code to derive a shared key **and** prove you're talking
   to the right person (not an impostor in the middle).
4. Messages are sealed with authenticated encryption and shown in your terminals.
5. On exit, everything is wiped - there's nothing left to recover.

See [Security model](#security-model) for the details.

## Requirements

- **Python 3.10 or newer**
- **[PyNaCl](https://pypi.org/project/PyNaCl/)** (libsodium bindings) - the crypto
- **[rich](https://pypi.org/project/rich/)** and
  **[questionary](https://pypi.org/project/questionary/)** - the terminal UI

## Install

```bash
git clone https://github.com/lilikenel/bubble-chat-app.git
cd bubble-chat-app
pip install -r requirements.txt
```

---

## How to use

You need **two terminals** (on one machine to try it out, or two machines on the
same network). One side hosts, the other joins.

### Start the app

```bash
python main.py
```

The screen clears and shows the BUBBLE banner and a keyboard-driven menu (use
`↑`/`↓` and `enter`):

1. **Host a bubble** or **Join a bubble**.
2. **Host** then picks **Local only** (`127.0.0.1`) or **LAN** (your
   auto-detected IPv4). Bubble prints a **pairing code** and shows a live
   countdown while it waits for a peer (it gives up after 2 minutes).
3. **Join** asks for your display name, the host's address, and the pairing code
   (entered hidden).

**Read the pairing code to your friend over a separate, trusted channel** (phone,
in person). Don't send it over an untrusted network - it's what keeps out
impostors.

Once the codes match, both sides see `✓ secure channel established` and can chat.
Messages appear as `[14:30] Alice  hi`, each name in its own colour, timestamps
in **your** local time - including your own messages.

Type **`/quit`** (or press `Ctrl-C`) to end the Bubble: the connection closes and
the conversation plus all keys are wiped. If your peer leaves first, you'll be
told to press enter to exit.

### Shortcut form (skip the menu)

```bash
python main.py host 127.0.0.1:5050
python main.py join 192.168.1.20:5050
```

Use the host's LAN IP to connect across machines, and make sure that port is
reachable. Over the internet the host must be reachable directly (port-forwarding
or a VPN); Bubble does not use a relay.

---

## Security model

| Property | How |
|---|---|
| **End-to-end encryption** | XSalsa20-Poly1305 authenticated encryption (NaCl `SecretBox`), a separate key per direction. |
| **Key agreement** | Ephemeral **X25519** Diffie–Hellman - a fresh key pair every session. |
| **Authentication (anti-MITM)** | The pairing code is mixed into the key via **Argon2id**, then a **key-confirmation** step (constant-time compare) proves both sides derived the same key. Wrong code or tampering → the handshake **fails closed**. |
| **Forward secrecy** | Per session - recording today's ciphertext and stealing a key later still can't decrypt it. |
| **Replay protection** | A monotonic per-direction sequence number inside each encrypted message; re-injected or reordered frames are dropped. |
| **Ephemerality** | Messages live only in RAM; keys are held in `bytearray`s and overwritten on exit. **Nothing is written to disk** - no logs, no history, no config. |

All cryptography is provided by **libsodium via PyNaCl** - no hand-rolled
primitives. The handshake was checked with an automated security review.

### Known limitations (by design)

- **Two participants** per Bubble.
- Safety depends on the **pairing code being high-entropy and shared over a
  trusted channel**.
- **Best-effort** memory wiping - Python cannot guarantee full zeroization.
- **Per-session** forward secrecy (no per-message ratchet).

---

## Development

Run the test suite (59 tests - transport, handshake, domain, session, addressing,
UI palette, end-to-end):

```bash
python -m unittest discover -s tests -p "*_test.py"
```

Coding standards live in [`.agents/coding-standards.md`](.agents/coding-standards.md)
and the design in [`.agents/plans/secure-chat-design.md`](.agents/plans/secure-chat-design.md).

## Changelog

See [CHANGELOG.md](CHANGELOG.md). **v1.1.0** is the latest release.

## License

GPL-3.0 - see [LICENSE](LICENSE).
