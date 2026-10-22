# SPDX-License-Identifier: GPL-2.0
"""The calculator's and Cards' themes give them the standard 104 px header
with the shell's «домой» and «✕» inside (#50): galculator's GTK title bar
88 px plus 8 px above and below, Aisleriot's toolbar 104 px with its tools
112 px from either edge. The heights were measured on the tablet.

    python3 -m unittest discover -s tests
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rule(css, selector):
    m = re.search(re.escape(selector) + r"[^{]*\{([^}]*)\}", css)
    assert m, selector
    return dict((k.strip(), v.strip()) for k, v in
                (d.split(":", 1) for d in m.group(1).split(";") if ":" in d))


def read(path):
    with open(os.path.join(ROOT, path)) as fh:
        return re.sub(r"/\*.*?\*/", "", fh.read(), flags=re.S)


class SideThemes(unittest.TestCase):
    def test_galculator_title_bar_is_the_header(self):
        css = read("themes/Haltia-Galculator/gtk-3.0/gtk.css")
        bar = rule(css, ".titlebar:not(headerbar), .default-decoration")
        self.assertEqual(bar["min-height"], "88px")
        self.assertEqual(bar["padding"], "8px 0")
        self.assertEqual(bar["background"], "#dcdcda")
        self.assertNotIn("textview", css)  # the display needs no side room now

    def test_cards_toolbar_is_the_header(self):
        css = read("themes/Haltia-Cards/gtk-3.0/gtk.css")
        bar = rule(css, "\ntoolbar ")
        self.assertEqual(bar["min-height"], "98px")  # + 6 px = 104 on the tablet
        self.assertEqual(bar["padding"], "0 112px")
        self.assertEqual(bar["background-color"], "#dcdcda")


if __name__ == "__main__":
    unittest.main()
