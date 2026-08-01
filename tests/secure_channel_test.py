"""Tests for the encrypted channel and the authenticated handshake."""

from __future__ import annotations

import concurrent.futures
import socket
import unittest

from nacl.exceptions import CryptoError
from nacl.utils import random as random_bytes

from networking.peer import Peer
from security.secure_channel import HOST, JOINER, HandshakeError, SecureChannel


class SecureChannelCryptoTest(unittest.TestCase):
    """The SecretBox layer, exercised with directly-supplied directional keys."""

    def _peer_pair(self) -> tuple[SecureChannel, SecureChannel]:
        key_a2b = random_bytes(32)
        key_b2a = random_bytes(32)
        alice = SecureChannel(send_key=key_a2b, receive_key=key_b2a)
        bob = SecureChannel(send_key=key_b2a, receive_key=key_a2b)
        return alice, bob

    def test_peer_decrypts_what_the_other_encrypts(self) -> None:
        alice, bob = self._peer_pair()

        self.assertEqual(bob.decrypt(alice.encrypt(b"hi bob")), b"hi bob")
        self.assertEqual(alice.decrypt(bob.encrypt(b"hi alice")), b"hi alice")

    def test_decrypt_rejects_tampered_ciphertext(self) -> None:
        alice, bob = self._peer_pair()
        frame = bytearray(alice.encrypt(b"secret"))
        frame[-1] ^= 0x01  # flip a bit in the authentication tag

        with self.assertRaises(CryptoError):
            bob.decrypt(bytes(frame))

    def test_wiped_channel_refuses_further_use(self) -> None:
        alice, _ = self._peer_pair()
        alice.wipe()

        with self.assertRaises(RuntimeError):
            alice.encrypt(b"too late")


class HandshakeTest(unittest.TestCase):
    """The full pairing-code handshake, run between two peers over a socket pair."""

    def _establish_pair(
        self, host_code: bytes, joiner_code: bytes
    ) -> tuple[concurrent.futures.Future, concurrent.futures.Future]:
        host_sock, joiner_sock = socket.socketpair()
        self.addCleanup(host_sock.close)
        self.addCleanup(joiner_sock.close)
        host_peer, joiner_peer = Peer(host_sock), Peer(joiner_sock)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.addCleanup(executor.shutdown)
        establish = SecureChannel.establish
        host_future = executor.submit(establish, host_peer, HOST, host_code)
        joiner_future = executor.submit(establish, joiner_peer, JOINER, joiner_code)
        return host_future, joiner_future

    def test_matching_codes_yield_interoperable_channels(self) -> None:
        code = b"shared-pairing-code-abc"
        host_future, joiner_future = self._establish_pair(code, code)
        host_channel = host_future.result(timeout=15)
        joiner_channel = joiner_future.result(timeout=15)

        self.assertEqual(joiner_channel.decrypt(host_channel.encrypt(b"ping")), b"ping")
        self.assertEqual(host_channel.decrypt(joiner_channel.encrypt(b"pong")), b"pong")

    def test_mismatched_codes_fail_key_confirmation(self) -> None:
        host_future, joiner_future = self._establish_pair(
            b"pairing-code-alpha-111", b"pairing-code-bravo-222"
        )

        with self.assertRaises(HandshakeError):
            host_future.result(timeout=15)
        with self.assertRaises(HandshakeError):
            joiner_future.result(timeout=15)

    def test_rejects_malformed_peer_public_key(self) -> None:
        host_sock, joiner_sock = socket.socketpair()
        self.addCleanup(host_sock.close)
        self.addCleanup(joiner_sock.close)
        host_peer, joiner_peer = Peer(host_sock), Peer(joiner_sock)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.addCleanup(executor.shutdown)

        host_future = executor.submit(
            SecureChannel.establish, host_peer, HOST, b"a-long-enough-pairing-code"
        )
        joiner_peer.recv_bytes()  # consume the host's real public key
        joiner_peer.send_bytes(b"too-short")  # reply with a malformed one

        with self.assertRaises(HandshakeError):
            host_future.result(timeout=15)

    def test_rejects_too_short_pairing_code(self) -> None:
        host_sock, joiner_sock = socket.socketpair()
        self.addCleanup(host_sock.close)
        self.addCleanup(joiner_sock.close)

        # Guard runs before any I/O, so this raises immediately (no live peer needed).
        with self.assertRaises(ValueError):
            SecureChannel.establish(Peer(host_sock), HOST, b"short")


if __name__ == "__main__":
    unittest.main()
