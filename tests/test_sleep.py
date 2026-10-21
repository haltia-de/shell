# SPDX-License-Identifier: GPL-2.0
"""haltia-sleep (#31): while dark it grabs the touch filter's device rather
than the screen under it (SH2-12), marks the screen dark for
haltia-brightness --restore (SH2-10), and kills a suspend hook that is
still running past its deadline (SH2-13).

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
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    path = os.path.join(ROOT, "libexec/haltia-sleep")
    loader = importlib.machinery.SourceFileLoader("haltia_sleep", path)
    spec = importlib.util.spec_from_loader("haltia_sleep", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


hs = load()


class Sleep(unittest.TestCase):
    def test_the_filter_is_grabbed_not_the_screen_under_it(self):
        names = {"event1": "gpio-keys", "event3": "Synaptics Blade10",
                 "event5": "haltia-touchguard touchscreen"}
        with mock.patch.object(hs.os, "listdir", lambda _p: sorted(names)), \
                mock.patch.object(hs, "input_name", names.get):
            self.assertEqual(hs.touch_nodes(), ["/dev/input/event5"])
        del names["event5"]  # the filter is away: the screen itself
        with mock.patch.object(hs.os, "listdir", lambda _p: sorted(names)), \
                mock.patch.object(hs, "input_name", names.get):
            self.assertEqual(hs.touch_nodes(), ["/dev/input/event3"])

    def test_the_dark_mark(self):
        folder = tempfile.mkdtemp(prefix="haltia-sleep-test.")
        self.addCleanup(shutil.rmtree, folder)
        mark = os.path.join(folder, "haltia", "screen-dark")
        with mock.patch.object(hs, "DARK_PATH", mark):
            hs.mark_dark(True)
            self.assertTrue(os.path.exists(mark))
            hs.mark_dark(False)
            self.assertFalse(os.path.exists(mark))
            hs.mark_dark(False)  # twice is fine

    def test_a_stuck_suspend_hook_is_killed(self):
        lamp = object.__new__(hs.Lamp)
        lamp.asleep, lamp.since, lamp.stuck_told = True, time.monotonic(), False
        # A hook with a child, both stuck.
        lamp.suspender = subprocess.Popen(["sh", "-c", "sleep 60 & sleep 60"],
                                          start_new_session=True)
        self.addCleanup(lambda: lamp.suspender and lamp.suspender.poll())
        lamp.suspend_started = time.monotonic()
        with mock.patch.object(hs, "suspend_command", lambda: ["hook"]), \
                mock.patch.object(hs, "external_power", lambda: False), \
                mock.patch.object(hs, "awake_held", lambda _k: False), \
                mock.patch.object(hs, "log", lambda _m: None):
            self.assertIsNone(lamp.suspend_due())  # still within its time
            lamp.suspend_started -= hs.SUSPEND_DEADLINE + 1
            pid = lamp.suspender.pid
            left = lamp.suspend_due()
        self.assertIsNotNone(left)  # free to suspend again later
        self.assertIsNone(lamp.suspender)
        time.sleep(0.2)
        with self.assertRaises(ProcessLookupError):
            os.killpg(pid, 0)  # the whole group is gone


if __name__ == "__main__":
    unittest.main()
