# SPDX-License-Identifier: GPL-2.0
"""Guards for two fixes from the second audit (#31) that have no runtime
test here: the home screen's minute timer wakes on a clock change (SH2-14),
and the on-screen keyboard runs under haltia-keep (SH2-15). Both were
checked on the tablet.

    python3 -m unittest discover -s tests
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path)) as fh:
        return fh.read()


class Guards(unittest.TestCase):
    def test_minute_timer_cancels_on_clock_set(self):
        body = read("tools/haltia-home.c")
        arm = body[body.index("static void arm_minute"):]
        arm = arm[:arm.index("\n}\n")]
        self.assertIn("TFD_TIMER_CANCEL_ON_SET", arm)

    def test_keyboard_is_kept(self):
        launcher = read("bin/haltia-launcher")
        self.assertRegex(launcher, re.compile(
            r"haltia-keep --session /usr/libexec/haltia/haltia-keyboard"))


if __name__ == "__main__":
    unittest.main()
