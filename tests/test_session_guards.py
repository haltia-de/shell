# SPDX-License-Identifier: GPL-2.0
"""Guards for fixes from the second audit (#31) that have no runtime test
here: the home screen's minute timer wakes on a clock change (SH2-14), the
on-screen keyboard runs under haltia-keep (SH2-15), haltia-home starts
lowered and notices every apps.conf replace (SH2-39, SH2-41), and a failed
signalfd ends haltia-home and haltia-close rather than leaving SIGTERM
blocked.

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

    def test_home_starts_lowered_and_sees_every_apps_change(self):
        body = read("tools/haltia-home.c")
        self.assertIn('"%s/haltia/home.raised", runtime_dir())', body)  # SH2-39
        self.assertIn("st.st_ino != apps_ino", body)  # SH2-41
        self.assertIn("st_mtim.tv_nsec != apps_mtim.tv_nsec", body)
        launcher = read("bin/haltia-launcher")
        self.assertIn('"$run"/haltia/home.raised "$run"/haltia/launch/starting', launcher)

    def test_signalfd_failure_ends_the_program(self):
        for path in ("tools/haltia-home.c", "tools/haltia-close.c"):
            self.assertIn("if (sfd < 0) {", read(path), path)

    def test_keyboard_is_kept(self):
        launcher = read("bin/haltia-launcher")
        self.assertRegex(launcher, re.compile(
            r"haltia-keep --session /usr/libexec/haltia/haltia-keyboard"))


if __name__ == "__main__":
    unittest.main()
