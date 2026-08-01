"""Tests for the User identity object."""

from __future__ import annotations

import unittest
from uuid import UUID

from dom.user import User


class UserTest(unittest.TestCase):
    def test_stores_display_name(self) -> None:
        self.assertEqual(User("Alice").display_name, "Alice")

    def test_assigns_a_unique_random_id(self) -> None:
        alice = User("Alice")
        bob = User("Bob")

        self.assertIsInstance(alice.user_id, UUID)
        self.assertNotEqual(alice.user_id, bob.user_id)


if __name__ == "__main__":
    unittest.main()
