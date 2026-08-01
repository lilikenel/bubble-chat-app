"""End-to-end test: real TCP + real handshake + session message exchange.

Exercises the whole stack (Listener/Peer transport, the Argon2id handshake, and
ChatSession) the same way main.py wires it, minus the interactive terminal loop.
"""

from __future__ import annotations

import concurrent.futures
import unittest

from dom.bubble import Bubble
from dom.user import User
from networking.peer import Listener, Peer
from security.secure_channel import HOST, JOINER, SecureChannel
from session import ChatSession


class EndToEndTest(unittest.TestCase):
    def test_full_stack_message_exchange_both_directions(self) -> None:
        listener = Listener(("127.0.0.1", 0))
        self.addCleanup(listener.close)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.addCleanup(executor.shutdown)

        accept_future = executor.submit(listener.accept)
        joiner_peer = Peer.join(listener.address)
        self.addCleanup(joiner_peer.close)
        host_peer = accept_future.result(timeout=10)
        self.addCleanup(host_peer.close)

        code = b"a-shared-pairing-code"
        host_future = executor.submit(SecureChannel.establish, host_peer, HOST, code)
        joiner_future = executor.submit(
            SecureChannel.establish, joiner_peer, JOINER, code
        )
        host = ChatSession(
            host_peer, host_future.result(timeout=15), Bubble(User("Host"))
        )
        joiner = ChatSession(
            joiner_peer, joiner_future.result(timeout=15), Bubble(User("Joiner"))
        )

        host.send_text("hello over TCP")
        joiner.send_text("hi back")

        self.assertEqual(joiner.receive_message().text, "hello over TCP")
        self.assertEqual(host.receive_message().text, "hi back")


if __name__ == "__main__":
    unittest.main()
