# Coding Standards

House coding standards for `bubble-chat-app`. These are binding for all code in this repo.

This project **follows [PEP 8](https://peps.python.org/pep-0008/)** (style) and
[PEP 257](https://peps.python.org/pep-0257/) (docstrings). Where this document is silent, defer to
PEP 8. Enforce it with tooling rather than by hand (see [Tooling](#tooling)).

---

## 1. Naming conventions (PEP 8)

| Element | Convention | Example |
|---|---|---|
| Repo / asset folders (non-package) | `kebab-case` (outside PEP's scope; matches the repo name) | `dev-notes/`, `.agents/` |
| **Python packages** (importable dirs) | short, all-lowercase, no underscores if avoidable | `dom/`, `networking/`, `security/` |
| Modules (`.py` files) | all-lowercase, underscores if it aids readability | `secure_channel.py`, `message.py` |
| Classes / Exceptions / Enums | `PascalCase` (CapWords) | `SecureChannel`, `HandshakeError`, `ConnState` |
| Functions & methods | `snake_case` | `send_framed()`, `establish_channel()` |
| Variables & parameters | `snake_case`, **descriptive** (no cryptic abbreviations) | `session_key`, `pairing_code` |
| Constants (module-level, immutable) | `UPPER_SNAKE_CASE` | `MAX_FRAME`, `SERVER_PORT` |
| Non-public members | single leading underscore | `_rx_loop()`, `_stop_event` |
| Booleans / boolean methods | `is_` / `has_` / `should_` prefix | `is_secure`, `has_handshaked` |
| Enum members | `UPPER_SNAKE_CASE` | `ConnState.DISCONNECTED` |
| Test files | `*_test.py` (matches unittest discovery in `.vscode/settings.json`) | `secure_channel_test.py` |
| Test methods | `test_` prefix, `snake_case` | `test_rejects_wrong_code()` |

- **Prefer full words over abbreviations.** `pairing_code`, not `pc`. Well-known short forms (`id`,
  `msg`, `addr`, `pk`/`sk` for public/secret key) are fine when unambiguous.
- **Existing files** in the skeleton use `PascalCase` names (`Bubble.py`, `Server.py`); rename them
  to `snake_case` when you next touch them so the tree converges on PEP 8.
- Avoid single-character names except for short-lived counters/indices; never use `l`, `O`, or `I`.

## 2. Type annotations

- **Every** function/method signature is fully annotated — parameters and return type.
- Annotate class attributes and non-obvious locals.
- Use modern typing: built-in generics (`list[str]`, `dict[str, int]`), `X | None` over
  `Optional[X]`. Add `from __future__ import annotations` at the top of each module.
- Prefer precise types (`bytes`, `SecretBox`, `UUID`) over `Any`.

```python
def send_message(self, plaintext: bytes) -> None: ...

@classmethod
def from_bytes(cls, raw: bytes) -> "Message": ...
```

## 3. Docstrings & comments (PEP 257)

- Module, public class, and public function/method get a triple-quoted docstring stating **purpose**.
- One-line docstrings fit on one line with the quotes; multi-line docstrings put the summary on the
  first line, a blank line, then details.
- Comments explain **why**, not **what** — the code already says what it does.
- Delete dead code and commented-out blocks; git is the history.

```python
# DON'T
counter += 1  # increment counter

# DO
# Reset after a full frame so a slow peer can't exhaust the buffer.
counter = 0
```

## 4. Formatting

- 4-space indentation, no tabs.
- Max line length **88** (Ruff/Black default; PEP 8 permits up to 99 by team agreement).
- One statement per line; one import per line.
- Two blank lines around top-level definitions, one between methods.
- Run the formatter before committing (see [Tooling](#tooling)) — no hand-formatting debates.

## 5. Imports

- **Absolute imports only** (`from dom.message import Message`). No implicit relative imports.
- **Never** use wildcard imports (`from x import *`) — they hide names and shadow builtins.
- Group in PEP 8 order, separated by a blank line: (1) `__future__`, (2) standard library,
  (3) third-party, (4) local/first-party. Sort within groups (let `ruff`/`isort` do it).
- Every package directory has an `__init__.py`.

## 6. Error handling

- Catch **specific** exceptions; never a bare `except:` or a blanket `except Exception` that
  swallows and continues.
- Raise domain-specific errors with actionable messages (`HandshakeError("key confirmation failed")`).
- Let unexpected errors propagate rather than hiding them.
- **Fail closed** on any security-relevant failure — see §7.

```python
try:
    plaintext = channel.decrypt(frame)
except CryptoError:
    self.close()            # tamper/wrong key -> tear down, never fall back to plaintext
    raise
```

## 7. Security conventions

This is a security-first app; these are non-negotiable.

- **No hardcoded secrets** — no keys, codes, or tokens in source or version control.
- **Never log or print secrets or plaintext key material.** No message contents in logs either.
- **Validate all network input** (length, type, bounds) *before* acting on it; enforce `MAX_FRAME`.
- **Fail closed:** any crypto/handshake/decrypt failure tears the connection down — no plaintext
  fallback, no silent retry.
- **In-memory only:** never persist messages, keys, or the pairing code to disk. Hold secrets in
  `bytearray` and overwrite them on teardown (best-effort; documented limitation).
- Constant-time compares for authentication tags (`sodium_memcmp`), never `==`.

## 8. Design & structure

- One primary class per module; keep files focused and small enough to hold in your head.
- Functions do one thing; extract helpers rather than nesting deeply.
- Constructors don't do I/O — construct, then call an explicit `start()`/`connect()` (keeps code testable).
- Prefer immutable value objects for data (e.g., `Message`); don't mutate shared state across threads
  without a guard.
- Isolate crypto behind one interface (`SecureChannel`) — the rest of the code never touches raw keys.

## 9. Testing

- Framework: `unittest`. Test files live in `tests/` as `*_test.py`.
- One behavior per test; follow **Arrange → Act → Assert**.
- Cover the unhappy paths, especially security fail-closed cases (wrong code, tampered ciphertext).
- Tests must not touch the network beyond loopback, and must not write to disk.
- Run: `python -m unittest discover -s tests -p "*_test.py"`

## 10. Commits

Follow the existing `type(Scope): summary` style (imperative mood, present tense):

```
feat(secure_channel): add X25519 handshake with key confirmation
fix(framing): reject frames larger than MAX_FRAME
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`. Scope is the class or module touched.

## 11. Tooling

- Use **[Ruff](https://docs.astral.sh/ruff/)** for linting + formatting (or `black` + `flake8`).
- Enable the `pep8-naming` (`N`) rules so naming is enforced automatically. Example `pyproject.toml`:

```toml
[tool.ruff]
line-length = 88

[tool.ruff.lint]
# E/W: pycodestyle, F: pyflakes, I: isort, N: pep8-naming, UP: pyupgrade, B: bugbear
select = ["E", "W", "F", "I", "N", "UP", "B"]
```
