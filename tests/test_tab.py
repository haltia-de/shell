# SPDX-License-Identifier: GPL-2.0
"""haltia-apps ends a «›» tab (haltia-tab) before it reloads waybar, and
waits for it (#31, SH2-3): a tab left over a reload could hide the rebuilt
panel with nothing to bring it back.

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def apps():
    path = os.path.join(ROOT, "bin/haltia-apps")
    loader = importlib.machinery.SourceFileLoader("haltia_apps", path)
    spec = importlib.util.spec_from_loader("haltia_apps", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class Tab(unittest.TestCase):
    def test_the_tab_ends_before_the_reload(self):
        folder = tempfile.mkdtemp(prefix="haltia-tab-test.")
        self.addCleanup(shutil.rmtree, folder)
        tab = os.path.join(folder, "haltia-tab")  # comm "haltia-tab"
        shutil.copy(shutil.which("sleep"), tab)
        proc = subprocess.Popen([tab, "30"])
        self.addCleanup(proc.kill)
        time.sleep(0.2)
        start = time.monotonic()
        apps().end_tab(os.getuid())
        self.assertIsNotNone(proc.poll())  # gone, not merely signalled
        self.assertLess(time.monotonic() - start, 1.5)


if __name__ == "__main__":
    unittest.main()
