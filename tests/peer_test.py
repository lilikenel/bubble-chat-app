"""Tests for the peer transport (Listener + Peer) over loopback."""

from __future__ import annotations

import concurrent.futures
import time
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
        accept_future = executor.submit(listener.accept, None, seen.append)

        client = Peer.join(listener.address)
        self.addCleanup(client.close)
        server = accept_future.result(timeout=5)
        self.addCleanup(server.close)

        client.send_bytes(b"hi")
        self.assertEqual(server.recv_bytes(), b"hi")
        self.assertTrue(seen)  # infinite remaining, but callback fired

    def test_accept_polls_then_accepts_a_late_peer(self) -> None:
        # A peer that connects after several poll intervals must still be
        # accepted; the polling loop must not give up or lose the connection.
        listener = Listener((LOOPBACK, 0))
        self.addCleanup(listener.close)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.addCleanup(executor.shutdown)
        accept_future = executor.submit(listener.accept)

        time.sleep(Listener._ACCEPT_POLL_SECONDS * 2)  # force at least one poll
        client = Peer.join(listener.address)
        self.addCleanup(client.close)
        server = accept_future.result(timeout=5)
        self.addCleanup(server.close)

        client.send_bytes(b"late")
        self.assertEqual(server.recv_bytes(), b"late")

    def test_accept_times_out_when_no_peer_connects(self) -> None:
        # With a deadline and no peer, accept() must give up instead of blocking.
        listener = Listener((LOOPBACK, 0))
        self.addCleanup(listener.close)

        with self.assertRaises(TimeoutError):
            listener.accept(timeout=Listener._ACCEPT_POLL_SECONDS)


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
