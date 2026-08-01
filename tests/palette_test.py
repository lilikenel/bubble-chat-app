"""Tests for per-session name colour assignment."""

from __future__ import annotations

import unittest

from ui.palette import PALETTE, NameColours


class NameColoursTest(unittest.TestCase):
    def test_same_name_keeps_its_colour(self) -> None:
        colours = NameColours()

        first = colours.for_name("nomfundo")
        second = colours.for_name("nomfundo")

        self.assertEqual(first, second)

    def test_colours_come_from_the_palette(self) -> None:
        colours = NameColours()

        self.assertIn(colours.for_name("lilike"), PALETTE)

    def test_distinct_names_each_get_a_palette_colour(self) -> None:
        colours = NameColours()

        colour_a = colours.for_name("a")
        colour_b = colours.for_name("b")

        self.assertIn(colour_a, PALETTE)
        self.assertIn(colour_b, PALETTE)
        # And each stays stable on re-lookup (two names tracked independently).
        self.assertEqual(colours.for_name("a"), colour_a)
        self.assertEqual(colours.for_name("b"), colour_b)


if __name__ == "__main__":
    unittest.main()
