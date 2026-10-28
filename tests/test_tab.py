# SPDX-License-Identifier: GPL-2.0
"""haltia-apps ends a «›» tab (haltia-tab) before it reloads waybar, and
waits for it (#31, SH2-3): a tab left over a reload could hide the rebuilt
panel with nothing to bring it back. Its runs take turns (SH2-42).

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock

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
        # Ended (a zombie: the test, like waybar, has not reaped it yet),
        # and seen as ended at once rather than after the 1 s limit.
        self.assertLess(time.monotonic() - start, 0.5)
        self.assertIsNotNone(proc.poll())


class OneRunAtATime(unittest.TestCase):
    def test_runs_at_once_take_turns(self):
        # SH2-42: Настройки' reload, haltia-rotate's panel and a pin at once
        # wrote the same .new files.
        folder = tempfile.mkdtemp(prefix="haltia-apps-lock.")
        self.addCleanup(shutil.rmtree, folder)
        mod = apps()
        inside, most = [0], [0]
        guard = threading.Lock()

        def build():
            with guard:
                inside[0] += 1
                most[0] = max(most[0], inside[0])
            time.sleep(0.2)
            with guard:
                inside[0] -= 1
            return {}, [], [], []
        with mock.patch.object(mod, "out_dir", return_value=folder), \
                mock.patch.object(mod, "build", build), \
                mock.patch.object(mod.sys, "argv", ["haltia-apps", "list"]):
            runs = [threading.Thread(target=mod.main) for _ in range(4)]
            for t in runs:
                t.start()
            for t in runs:
                t.join(10)
        self.assertEqual(most[0], 1)


if __name__ == "__main__":
    unittest.main()
