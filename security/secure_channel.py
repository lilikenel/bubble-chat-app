"""Authenticated, encrypted channel between the two peers.

This is the only module that touches raw key material. A channel is normally
created by :meth:`SecureChannel.establish`, which runs the pairing-code
handshake; the constructor takes the two directional keys it derives.
"""

from __future__ import annotations

import nacl.bindings
from nacl.encoding import RawEncoder
from nacl.hash import blake2b
from nacl.public import PrivateKey
from nacl.pwhash import argon2id
from nacl.secret import SecretBox

from networking.peer import Peer

HOST = "HOST"
JOINER = "JOINER"

_APP_LABEL = b"bubble-chat-v1"
_KEY_BYTES = 32
_PUBLIC_KEY_BYTES = 32


class HandshakeError(Exception):
    """The peers did not derive a matching key: wrong code, tampering, or MITM."""


class SecureChannel:
    """Encrypts with one key and decrypts with the other (one key per direction)."""

    def __init__(self, send_key: bytes, receive_key: bytes) -> None:
        # Keep copies in bytearrays so wipe() can overwrite them.
        self._send_key = bytearray(send_key)
        self._receive_key = bytearray(receive_key)
        # Boxes hold the working keys; wipe() drops them and zeroes the bytearrays.
        self._send_box: SecretBox | None = SecretBox(bytes(self._send_key))
        self._receive_box: SecretBox | None = SecretBox(bytes(self._receive_key))

    @classmethod
    def establish(
        cls, transport: Peer, role: str, pairing_code: bytes
    ) -> "SecureChannel":
        """Run the pairing-code handshake over ``transport`` and return a channel.

        A fresh key pair per session provides forward secrecy; the ``pairing_code``
        authenticates the exchange through a key-confirmation step. Raises
        :class:`HandshakeError` if the two sides derive different keys (wrong code
        or tampering); fail closed.
        """
        if role not in (HOST, JOINER):
            raise ValueError(f"role must be HOST or JOINER, got {role!r}")

        my_private_key = PrivateKey.generate()
        my_public_key = my_private_key.public_key.encode()
        transport.send_bytes(my_public_key)
        their_public_key = transport.recv_bytes()
        if len(their_public_key) != _PUBLIC_KEY_BYTES:
            raise HandshakeError("peer sent a malformed public key")

        # Fingerprint of both public keys, order-independent so both sides match.
        first_key, second_key = sorted((my_public_key, their_public_key))
        keys_fingerprint = blake2b(
            first_key + second_key, digest_size=32, encoder=RawEncoder
        )

        # Diffie-Hellman: my private + their public == their private + my public.
        shared_secret = nacl.bindings.crypto_box_beforenm(
            their_public_key, my_private_key.encode()
        )
        key_from_code = argon2id.kdf(
            _KEY_BYTES,
            pairing_code,
            keys_fingerprint[: argon2id.SALTBYTES],
            opslimit=argon2id.OPSLIMIT_MODERATE,
            memlimit=argon2id.MEMLIMIT_MODERATE,
        )
        session_key = blake2b(
            shared_secret + key_from_code,
            digest_size=32,
            salt=keys_fingerprint[:16],
            person=_APP_LABEL,
            encoder=RawEncoder,
        )

        # Key confirmation: both sides prove they derived the same session key.
        confirmation_key = blake2b(
            session_key, digest_size=32, person=b"bubble-confirm", encoder=RawEncoder
        )
        their_role = JOINER if role == HOST else HOST
        expected_tag = _confirmation_tag(confirmation_key, their_role)
        transport.send_bytes(_confirmation_tag(confirmation_key, role))
        their_tag = transport.recv_bytes()
        if not nacl.bindings.sodium_memcmp(their_tag, expected_tag):
            raise HandshakeError("key confirmation failed: wrong code or tampering")

        # One key per direction so a message can't be reflected back to its sender.
        host_to_joiner_key = blake2b(
            session_key, digest_size=32, person=b"bubble-h2j", encoder=RawEncoder
        )
        joiner_to_host_key = blake2b(
            session_key, digest_size=32, person=b"bubble-j2h", encoder=RawEncoder
        )
        if role == HOST:
            return cls(send_key=host_to_joiner_key, receive_key=joiner_to_host_key)
        return cls(send_key=joiner_to_host_key, receive_key=host_to_joiner_key)

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt one message (result carries its own random nonce + MAC)."""
        if self._send_box is None:
            raise RuntimeError("channel has been wiped")
        return bytes(self._send_box.encrypt(plaintext))

    def decrypt(self, encrypted_message: bytes) -> bytes:
        """Decrypt one message; raises ``nacl.exceptions.CryptoError`` on tamper."""
        if self._receive_box is None:
            raise RuntimeError("channel has been wiped")
        return self._receive_box.decrypt(encrypted_message)

    def wipe(self) -> None:
        """Drop the boxes and overwrite the key bytes."""
        for key_buffer in (self._send_key, self._receive_key):
            for i in range(len(key_buffer)):
                key_buffer[i] = 0
        self._send_box = None
        self._receive_box = None


def _confirmation_tag(confirmation_key: bytes, role: str) -> bytes:
    """Keyed tag proving knowledge of the session key, bound to the peer's role."""
    return blake2b(
        role.encode(), key=confirmation_key, digest_size=32, encoder=RawEncoder
    )
