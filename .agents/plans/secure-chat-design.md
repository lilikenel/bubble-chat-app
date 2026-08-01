# Bubble — Secure, Ephemeral, Peer-to-Peer Terminal Chat

> Design + implementation plan. Approved 2026-08-01. Source of truth for the security
> architecture — do not re-litigate these decisions without cause (see "Decisions locked").
>
> Naming follows [.agents/coding-standards.md](../coding-standards.md) (PEP 8): module files are
> `snake_case`, classes are `PascalCase`.

## Context

`bubble-chat-app` started as a skeleton: real-ish TCP bring-up in `networking/`, but the
domain models (`Bubble`, `User`) and all of `security/Security.py` were empty stubs, and the
networking had real defects (broken imports, mis-wired threads, single-client `accept`,
constructors that do I/O). The product goal is a small chat with three properties:

1. **Two users can communicate** — 1:1 chat.
2. **As secure as possible** — the primary non-functional goal.
3. **Everything in-memory** — the conversation and all secrets vanish when the chat closes.
   In-terminal for now.

Discovery settled the security architecture. The most important outcome: choosing
**peer-to-peer** *structurally removes* the "untrusted relay/server" threat (there is no third
party), and choosing an **app-generated high-entropy pairing code** lets us build the whole
thing on **PyNaCl alone** — no unmaintained crypto dependencies (`spake2`/`hkdf` avoided).

## Decisions locked during discovery

| Axis | Decision | Consequence |
|---|---|---|
| Topology | **Direct P2P** (host listens, joiner dials) | No relay → collapse `Server`/`Client`/`ClientHandler` into one `Peer`; "untrusted server" threat gone. |
| Trust / identity | **App-generated high-entropy pairing code**, shared out-of-band | Authenticates the key exchange; defeats MITM; nothing persisted. |
| Threats in scope | eavesdropper, MITM, local device access (untrusted-server N/A) | Drives E2E crypto + authenticated handshake + in-memory-only + best-effort wipe. |
| Crypto library | **PyNaCl only** (pinned) | Single, actively-maintained, misuse-resistant dep. Drop `cryptography`; do **not** add `spake2`. |
| Handshake | Ephemeral **X25519** + **Argon2id**-over-code + **key confirmation**, then **SecretBox** messages | Forward secrecy per session; fail-closed on wrong code / tamper. |

## Architecture

Four layers, each independently testable:

- **Transport** (`networking/`) — TCP sockets + length-prefixed framing.
- **Secure channel** (`security/`) — the *only* place raw keys live; handshake + encrypt/decrypt/wipe.
- **Domain** (`dom/`) — `Message`, `User`, `Bubble` (owns all ephemeral state).
- **Terminal UI / entry** (`main.py`) — arg parsing, code display/input, wiring, guaranteed teardown.

P2P means one side opens a `Listener` (bind + accept exactly one connection) while the other calls
`Peer.join`; both then hold a symmetric `Peer`. The `HOST` / `JOINER` labels only seed the
handshake — after `SECURE` the two peers are identical.

```
HOST                                             JOINER
  listen(); accept() one peer  <---------------  connect()
                    [ TCP up ]
  ===== authenticated handshake (shared code) =====
     ephemeral X25519  +  Argon2id(code)  +  key-confirmation MAC
     mismatch (wrong code / MITM / tamper) -> BOTH abort, close
  ===================== SECURE =====================
  <---- length-prefixed SecretBox frames (nonce+MAC+ciphertext) ---->
        receiver thread decrypts & prints; main thread reads stdin & sends
  Ctrl-C or /quit -> Bubble.pop(): clear messages, zeroize keys, close socket
                     (nothing was ever written to disk)
```

## Libraries / dependencies

- **`PyNaCl` (pin `>=1.6.2`)** — the entire crypto core:
  - `nacl.public` — ephemeral X25519 keypairs; `nacl.bindings.crypto_box_beforenm` for the raw ECDH shared secret.
  - `nacl.pwhash.argon2id.kdf` — slow, memory-hard KDF over the pairing code.
  - `nacl.hash.blake2b` — keyed hashing for key derivation + confirmation tags.
  - `nacl.secret.SecretBox` — per-message AEAD (XSalsa20-Poly1305, auto random nonce).
  - `nacl.utils.random`, `nacl.bindings.sodium_memcmp` — CSPRNG, constant-time compare.
- **stdlib** — `socket`, `threading`, `struct` (framing), `secrets` (code generation),
  `getpass` (no-echo code entry), `uuid`, `datetime`, `enum`.
- **Remove** `cryptography` from `requirements.txt` (unused under this design).
- **Do NOT add** `spake2` — verified unmaintained (~6 yrs) with a decade-stale `hkdf` dep; the
  high-entropy code makes a true PAKE unnecessary.

## The handshake (security-critical — run `/security-review` before trusting it)

Both peers already share `code` (bytes, from the same displayed string). `role ∈ {HOST, JOINER}`.

```
establish(sock, role, code) -> SecureChannel:
  1. eph_sk = PrivateKey.generate();  eph_pk = eph_sk.public_key
  2. send_framed(sock, eph_pk.encode())          # 32 bytes
     peer_pk = PublicKey(recv_framed(sock))
  3. lo, hi   = sorted([eph_pk.encode(), peer_pk.encode()])   # order-independent
     transcript = blake2b(lo + hi, digest_size=32)            # binds both keys
  4. k_ecdh = crypto_box_beforenm(peer_pk.encode(), eph_sk.encode())   # X25519 secret
  5. k_code = argon2id.kdf(32, code, salt=transcript[:16],
                           opslimit=MODERATE, memlimit=MODERATE)       # slow over the code
  6. session = blake2b(k_ecdh + k_code, digest_size=32,
                       person=b"bubble-chat-v1", salt=transcript[:16])
  7. # mutual key confirmation (fail-closed):
     k_conf   = blake2b(session, digest_size=32, person=b"bubble-conf")
     my_tag   = blake2b(role.encode(),      key=k_conf, digest_size=32)
     peer_exp = blake2b(other_role.encode(), key=k_conf, digest_size=32)
     send_framed(sock, my_tag);  got = recv_framed(sock)
     if not sodium_memcmp(got, peer_exp): raise HandshakeError   # wrong code / MITM / tamper
  8. # directional keys so a message can't be reflected back:
     k_send = blake2b(session, person=b"H2J" if HOST else b"J2H", digest_size=32)
     k_recv = blake2b(session, person=b"J2H" if HOST else b"H2J", digest_size=32)
  9. zeroize(eph_sk, k_ecdh, k_code, code, session)     # best-effort (see limitations)
     return SecureChannel(SecretBox(k_send), SecretBox(k_recv))
```

Messages after `SECURE`: `encrypt = send_box.encrypt(plaintext)` (random nonce auto-added);
`decrypt = recv_box.decrypt(frame)` which **raises `CryptoError` on any tamper** → caller closes.

## Files to create / change

New module files use `snake_case` (PEP 8; see [coding-standards.md](../coding-standards.md)). Rename
the existing PascalCase stubs (`Bubble.py`, `Server.py`, …) to `snake_case` as they're replaced. Add
missing `__init__.py` and a top-level entry point so imports resolve (run from repo root).

- **New** `main.py` — role/address arg parsing; `make_pairing_code()` (host) or `getpass` (joiner);
  print code for host; wire `Peer` + `SecureChannel` + `Bubble`; `try/finally` → guaranteed `pop()`.
- **New** `security/secure_channel.py` — `SecureChannel` class + the handshake above (replaces the
  RSA-oriented `security/Security.py`, which is deleted).
- **New** `security/pairing.py` — `make_pairing_code()` (high-entropy words via `secrets`).
- **✅ Done** `networking/framing.py` — `send_framed()` / `recv_framed()` (4-byte big-endian length,
  `MAX_FRAME` guard, exact-read loop via `_recv_exactly`).
- **✅ Done (transport)** `networking/peer.py` — `Listener` (bind / `address` / `accept()` → `Peer`)
  plus `Peer` (`join()`, `send_bytes()`, `recv_bytes()`, `close()`). Bind is split into `Listener`
  (separate from the blocking `accept`) for testability. The `Peer.host()` convenience and the
  higher-level session API (`run_session()`, `_rx_loop()`, `send(text)`, `ConnState`) arrive in later
  phases once `SecureChannel`/`Bubble`/`main.py` exist. **Deleted** `networking/Server.py`,
  `networking/Client.py`, `networking/ClientHandler.py`.
- **Rewrite** `dom/message.py` (from `dom/Message.py`) — immutable value object;
  `to_bytes()`/`from_bytes()` canonical serialization (JSON→utf8); drop the fragile `" % "` `__str__`
  wire format (keep a display `__str__`).
- **Rewrite** `dom/user.py` (from `dom/User.py`) — `display_name` + `user_id: UUID` only;
  **remove RSA key fields**.
- **Implement** `dom/bubble.py` (from `dom/Bubble.py`) — instance fields (not class-level);
  `messages: list`, `channel`, `state`; `add()`, `history()`, `pop()` (the wipe).
- **Add** `__init__.py` to `dom/`, `networking/`, `security/`, `tests/`.
- **Edit** `requirements.txt` — replace `cryptography` with `PyNaCl>=1.6.2`.
- **Tests** — new `tests/*_test.py` files (matches the `.vscode/settings.json` unittest pattern);
  delete the broken `tests/ServerTests.py`.

## Pseudocode by module

```
# dom/message.py
Message(text, sender_name, sender_id:UUID, timestamp:datetime)   # immutable
  to_bytes() -> bytes            # json({t,n,id,ts}).encode()
  from_bytes(b) -> Message       # classmethod, validates fields
  __str__ -> "[HH:MM] name: text"

# dom/user.py
User(display_name:str)  ->  fields: display_name, user_id = uuid4()

# dom/bubble.py
Bubble(local_user:User)
  fields set in __init__: bubble_id, local_user, remote_name=None,
                          messages=[], channel=None, state=DISCONNECTED
  add(msg)     -> messages.append(msg)
  history()    -> list(messages)
  pop()        -> messages.clear(); channel.wipe() if channel; state=CLOSED

# security/secure_channel.py
SecureChannel(send_box, recv_box)
  establish(sock, role, code) -> SecureChannel     # the handshake above; raises HandshakeError
  encrypt(pt:bytes) -> bytes                        # send_box.encrypt(pt)
  decrypt(frame:bytes) -> bytes                     # recv_box.decrypt(frame); raises on tamper
  wipe() -> None                                    # drop boxes; overwrite any bytearrays

# networking/framing.py
send_framed(sock, payload)  -> sock.sendall(struct.pack(">I", len(payload)) + payload)
recv_framed(sock) -> bytes  -> read 4-byte len (<= MAX_FRAME), then recv exactly len bytes

# networking/peer.py  — transport (implemented)
Listener(address)              # bind + listen(1)
  address -> (host, port)      # property; resolves an OS-assigned port when 0 is passed
  accept() -> Peer             # block for one connection, wrap it
  close()
Peer(sock)
  join(address) -> Peer        # classmethod: socket.create_connection
  send_bytes(payload: bytes)   # send_framed(sock, payload)
  recv_bytes() -> bytes        # recv_framed(sock)
  close()

# networking/peer.py  — session layer (later phases, once channel/bubble exist)
ConnState = enum(DISCONNECTED, HANDSHAKING, SECURE, CLOSED)
  run_session():               # spawn _rx_loop thread; run tx loop over input()
  _rx_loop():  while not stop.is_set(): f=recv_bytes(); pt=channel.decrypt(f)
                                        m=Message.from_bytes(pt); bubble.add(m); print(m)
  send(text):  m=Message(text, me, my_id, now_utc()); send_bytes(channel.encrypt(m.to_bytes()))
  close():     stop.set(); bubble.pop(); sock.close()

# main.py
role, addr = parse_args()
name = input("Display name: ")
code = make_pairing_code() if role==HOST else getpass("Pairing code: ")
if role==HOST: print("Read this to your peer (never stored):", code)
sock = Peer.host(addr) if role==HOST else Peer.join(addr)
try:
    channel = SecureChannel.establish(sock, role, code)     # fail-closed gate
    peer = Peer(sock, role, Bubble(User(name)), channel)
    peer.run_session()
finally:
    peer.close()        # pop() wipes RAM on every exit path
```

## In-memory / ephemerality guarantees

- **No disk writes anywhere** — no logs, no history files, no config persistence. Messages live
  only in `Bubble.messages` (RAM).
- **Best-effort secret wipe** — hold key material in `bytearray`, overwrite with zeros and `del`
  on teardown; `SecureChannel.wipe()` drops the boxes.
- **No echo / no shell history** — pairing code is generated in-process or read via `getpass`;
  never passed on argv.
- **Guaranteed teardown** — `try/finally` in `main.py` ensures `pop()` runs on `/quit`, `Ctrl-C`,
  and errors alike.

## Build phasing (TDD-friendly, each phase testable in isolation)

1. **Transport** — `framing` + `Peer.host/join` + threaded echo over loopback (plaintext).
2. **Handshake** — `SecureChannel.establish` + key confirmation; test matching vs. mismatched code.
3. **Message crypto** — `SecretBox` directional boxes end-to-end; `Message` serialization round-trip.
4. **Ephemerality/hardening** — `Bubble.pop()` wipe, `getpass`, `try/finally`, no-disk audit.
5. **Polish** — `/quit` command, clean shutdown, error messages, fail-closed on decrypt errors,
   `TCP_NODELAY` on the connected sockets (lower per-message latency for interactive chat).

## Testing & verification

- **Unit (`unittest`, files `tests/*_test.py`)**:
  - `secure_channel_test.py` — matching codes derive equal keys + confirm; **mismatched codes
    raise `HandshakeError`**; tampered ciphertext raises on `decrypt`.
  - `framing_test.py` — round-trip, partial reads, oversize frame rejected.
  - `message_test.py` — `to_bytes`/`from_bytes` round-trip incl. unicode and `%`.
  - `bubble_test.py` — `add`/`history`; `pop()` empties `messages` and wipes the channel.
  - Run: `python -m unittest discover -s tests -p "*_test.py"`
- **End-to-end (manual, two terminals)** from repo root:
  - Terminal A: `python main.py host 127.0.0.1:5050` → prints a pairing code.
  - Terminal B: `python main.py join 127.0.0.1:5050` → paste the code → chat both directions.
  - Negative: enter a wrong code in B → both sides must abort before any message (fail-closed).
  - Ephemerality: exit both → confirm no files created (`git status` clean, no logs).
- **Security review**: run `/security-review` on the `security/` handshake before trusting it —
  it is an assembled protocol (standard "mix pre-shared secret into KDF + key confirmation"
  pattern) built from a vetted primitive library, but assembled crypto warrants a review pass.

## Deviations from the original stub (calling out, per standards)

- **Drop RSA** (`keygen/encrypt/decrypt/sign/validate`, `User` keypair) — redundant with a shared
  SecretBox key between exactly two peers. Flag if signatures/non-repudiation are actually wanted.
- **Collapse `Server`/`Client`/`ClientHandler` into `Peer`** — P2P has no relay.
- **Replace `Message` `" % "` serialization** — fragile if text contains `%`.
- **No-I/O constructors** — construct then `.start()`; fixes the current test-hostile pattern.
- **Naming normalized to PEP 8** — module files to `snake_case` (`Bubble.py` → `bubble.py`),
  functions/methods to `snake_case` (original stubs mixed `sendMessage`/`removeSelf` with lowercase).

## Known limitations (honest)

- Python cannot guarantee true zeroization (immutable `bytes`/`str`, GC copies); wipe is best-effort.
- Per-**session** forward secrecy only — no per-message Double-Ratchet (out of scope / YAGNI).
- The out-of-band code channel is trusted (users read it to each other); the app can't verify that.
- No DoS/abuse hardening beyond a max-frame guard (single known peer, in-terminal).
