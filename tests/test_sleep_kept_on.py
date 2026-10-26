# SPDX-License-Identifier: GPL-2.0
"""haltia-sleep looks for updates on the charger when the screen is kept on
(«on while charging», #74): once the idle-off time passes without input,
as it does when the screen goes off.

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    path = os.path.join(ROOT, "libexec/haltia-sleep")
    loader = importlib.machinery.SourceFileLoader("haltia_sleep_kept_on", path)
    spec = importlib.util.spec_from_loader("haltia_sleep_kept_on", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


hs = load()
OFF = 600.0


class KeptOn(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-sleep-kept-on.")
        self.addCleanup(shutil.rmtree, self.dir)
        self.lines = []
        self.stamp = os.path.join(self.dir, "last-look")
        for patch in (mock.patch.object(hs, "log", self.lines.append),
                      mock.patch.object(hs, "UPDATE_STATE", self.dir),
                      mock.patch.object(hs, "awake_held", lambda _k: False),
                      mock.patch.object(hs.os, "access", lambda *_a: True),
                      mock.patch.dict(hs._screen)):
            patch.start()
            self.addCleanup(patch.stop)
        p = mock.patch.object(hs.subprocess, "Popen")
        self.popen = p.start()
        self.addCleanup(p.stop)
        self.power(True)

    def power(self, on):
        """«On while charging» set; on: the tablet is on the charger."""
        hs._screen.update(at=time.monotonic() + 3600, off=OFF, keep=True, charging=on)
        p = mock.patch.object(hs, "charging", lambda: on)
        p.start()
        self.addCleanup(p.stop)

    def stale(self, hours=21):
        open(self.stamp, "w").close()
        then = time.time() - hours * 3600
        os.utime(self.stamp, (then, then))

    def test_idle_past_the_time_with_a_stale_stamp_looks_once(self):
        self.stale()
        last_input = time.monotonic() - OFF - 1
        wait, looked = hs.updates_when_kept_on(last_input, None)
        self.assertIsNone(wait)
        self.assertEqual(looked, last_input)
        self.assertEqual(self.popen.call_count, 1)
        self.assertIn("check", self.popen.call_args.args[0][-1])
        self.assertTrue(any(line.startswith("UPDATES ") for line in self.lines))
        # The same stretch without input, even with the stamp stale again.
        self.stale()
        self.assertEqual(hs.updates_when_kept_on(last_input, looked), (None, looked))
        self.assertEqual(self.popen.call_count, 1)

    def test_a_fresh_stamp_does_not_look(self):
        self.stale(hours=1)
        hs.updates_when_kept_on(time.monotonic() - OFF - 1, None)
        self.popen.assert_not_called()

    def test_on_battery_it_does_not_look(self):
        self.power(False)
        self.stale()
        self.assertEqual(hs.updates_when_kept_on(time.monotonic() - OFF - 1, None),
                         (None, None))
        self.popen.assert_not_called()

    def test_input_before_the_timer_does_not_look(self):
        self.stale()
        wait, looked = hs.updates_when_kept_on(time.monotonic() - 10, None)
        self.assertIsNone(looked)
        self.assertGreater(wait, OFF - 20)
        self.assertLessEqual(wait, OFF - 10)
        self.popen.assert_not_called()

    def test_a_video_holding_the_screen_does_not_look(self):
        self.stale()
        with mock.patch.object(hs, "awake_held", lambda _k: True):
            hs.updates_when_kept_on(time.monotonic() - OFF - 1, None)
        self.popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
