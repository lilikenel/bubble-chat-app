"""Tests for the peer transport (Listener + Peer) over loopback."""

from __future__ import annotations

import concurrent.futures
import unittest

from networking.peer import Listener, Peer

LOOPBACK = "127.0.0.1"


class ListenerTest(unittest.TestCase):
    def test_listener_exposes_its_bound_address(self) -> None:
        listener = Listener((LOOPBACK, 0))
        self.addCleanup(listener.close)

        host, port = listener.address

        self.assertEqual(host, LOOPBACK)
        self.assertNotEqual(port, 0)


class PeerTransportTest(unittest.TestCase):
    def _connected_pair(self) -> tuple[Peer, Peer]:
        """Return a (client, server) pair connected over loopback."""
        listener = Listener((LOOPBACK, 0))
        self.addCleanup(listener.close)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.addCleanup(executor.shutdown)
        accept_future = executor.submit(listener.accept)

        client = Peer.join(listener.address)
        server = accept_future.result(timeout=5)  # re-raises if accept() failed

        self.addCleanup(client.close)
        self.addCleanup(server.close)
        return client, server

    def test_bytes_sent_from_client_are_received_by_server(self) -> None:
        client, server = self._connected_pair()

        client.send_bytes(b"ping")

        self.assertEqual(server.recv_bytes(), b"ping")

    def test_bytes_flow_from_server_to_client(self) -> None:
        client, server = self._connected_pair()

        server.send_bytes(b"pong")

        self.assertEqual(client.recv_bytes(), b"pong")


if __name__ == "__main__":
    unittest.main()
