# SPDX-License-Identifier: GPL-2.0
"""haltia-apps' portrait style: PORTRAIT_CSS takes the button width through
%, so a stray % in it would end haltia-apps and leave the panel unstyled.

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def apps():
    path = os.path.join(ROOT, "bin/haltia-apps")
    loader = importlib.machinery.SourceFileLoader("haltia_apps", path)
    spec = importlib.util.spec_from_loader("haltia_apps", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class Portrait(unittest.TestCase):
    def test_the_style_formats(self):
        css = apps().PORTRAIT_CSS % 87
        self.assertIn(".app { min-width: 87px;", css)
        # The status's three icons stacked: Wi-Fi, speaker, battery.
        self.assertIn("background-position: 50% 0%, 50% 50%, 50% 100%;", css)


if __name__ == "__main__":
    unittest.main()
