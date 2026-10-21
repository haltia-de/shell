# SPDX-License-Identifier: GPL-2.0
"""haltia-touchguard-conf (#31, SH2-9): a value set is only tried (TRY, read
over CONF), reaches CONF on keep with its comments kept, goes on drop, and
goes by itself TRY_S seconds on when nobody keeps it. Run on a copy with
its paths in a temporary folder and a stand-in for the filter's pid.

    python3 -m unittest discover -s tests
"""
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = "# The touch filter.\nhold_ms = 40\n# a comment\ntap_radius = 6.27%\n"


class TouchConf(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-touch-conf-test.")
        self.addCleanup(shutil.rmtree, self.dir)
        p = lambda n: os.path.join(self.dir, n)
        self.conf, self.try_, self.pidfile = p("touchguard.conf"), p("touchguard.try"), p("pid")
        with open(self.conf, "w") as fh:
            fh.write(CONF)
        # The filter: takes SIGHUP and goes on.
        self.filter = subprocess.Popen(["sh", "-c", "trap '' HUP; sleep 60"])
        self.addCleanup(self.filter.wait)
        self.addCleanup(self.filter.kill)
        with open(self.pidfile, "w") as fh:
            fh.write("%d\n" % self.filter.pid)
        with open(os.path.join(ROOT, "libexec/haltia-touchguard-conf")) as fh:
            src = fh.read()
        src = re.sub(r"^CONF=.*$", "CONF=%s" % self.conf, src, count=1, flags=re.M)
        src = src.replace("[ -e \"$CONF\" ] || [ ! -e /etc/b8k/touchguard.conf ] || "
                          "CONF=/etc/b8k/touchguard.conf", ":")
        src = re.sub(r"^PIDFILE=.*$", "PIDFILE=%s" % self.pidfile, src, count=1, flags=re.M)
        src = re.sub(r"^EVENTS=.*$", "EVENTS=%s" % p("events"), src, count=1, flags=re.M)
        src = re.sub(r"^TRY=.*$", "TRY=%s" % self.try_, src, count=1, flags=re.M)
        src = re.sub(r"^TRY_S=.*$", "TRY_S=1", src, count=1, flags=re.M)
        self.helper = p("helper")
        with open(self.helper, "w") as fh:
            fh.write(src)

    def run_helper(self, *args):
        return subprocess.run(["sh", self.helper] + list(args), capture_output=True, text=True)

    def read(self, path):
        try:
            with open(path) as fh:
                return fh.read()
        except FileNotFoundError:
            return None

    def test_set_tries_and_leaves_the_file(self):
        self.assertEqual(self.run_helper("set", "hold_ms=80", "tap_radius=900").returncode, 0)
        self.assertEqual(self.read(self.conf), CONF)
        tried = self.read(self.try_)
        self.assertIn("hold_ms = 80\n", tried)
        self.assertIn("tap_radius = 9.00%\n", tried)

    def test_keep_writes_the_file_with_its_comments(self):
        self.run_helper("set", "hold_ms=80", "long_ms=900")
        self.assertEqual(self.run_helper("keep", "hold_ms=80", "long_ms=900").returncode, 0)
        self.assertEqual(self.read(self.conf),
                         "# The touch filter.\nhold_ms = 80\n# a comment\n"
                         "tap_radius = 6.27%\nlong_ms = 900\n")
        self.assertIsNone(self.read(self.try_))

    def test_drop_forgets(self):
        self.run_helper("set", "hold_ms=80")
        self.assertEqual(self.run_helper("drop").returncode, 0)
        self.assertIsNone(self.read(self.try_))
        self.assertEqual(self.read(self.conf), CONF)

    def test_keep_with_nothing_tried_leaves_the_file(self):
        self.assertEqual(self.run_helper("keep").returncode, 0)
        self.assertEqual(self.read(self.conf), CONF)

    def test_keep_after_the_watch_dropped_the_try_still_saves(self):
        self.run_helper("set", "hold_ms=80")
        time.sleep(2.5)  # the watch has dropped it
        self.assertEqual(self.run_helper("keep", "hold_ms=80").returncode, 0)
        self.assertIn("hold_ms = 80\n", self.read(self.conf))

    def test_keep_with_the_filter_down_saves_and_succeeds(self):
        self.filter.kill()
        self.filter.wait()
        res = self.run_helper("keep", "hold_ms=70")
        self.assertEqual(res.returncode, 0)
        self.assertIn("hold_ms = 70\n", self.read(self.conf))

    def test_set_with_the_filter_down_leaves_no_try(self):
        self.filter.kill()
        self.filter.wait()
        self.assertNotEqual(self.run_helper("set", "hold_ms=80").returncode, 0)
        time.sleep(2.5)
        self.assertIsNone(self.read(self.try_))

    def test_one_token_and_values_together(self):
        self.run_helper("set", "hold_ms=80")
        self.run_helper("set", "long_ms=900")
        tried = self.read(self.try_)
        self.assertEqual(tried.count("# token "), 1)
        self.assertTrue(tried.rstrip("\n").splitlines()[-1].startswith("# token "))
        self.assertIn("hold_ms = 80\n", tried)

    def test_a_try_nobody_keeps_goes_by_itself(self):
        self.run_helper("set", "hold_ms=80")
        time.sleep(2.5)
        self.assertIsNone(self.read(self.try_))
        self.assertEqual(self.read(self.conf), CONF)

    def test_trying_again_renews_the_watch(self):
        self.run_helper("set", "hold_ms=80")
        time.sleep(0.6)
        self.run_helper("set", "hold_ms=90")
        time.sleep(0.6)  # the first watch is over, the second is not
        self.assertIn("hold_ms = 90\n", self.read(self.try_) or "")

    def test_out_of_range_is_refused(self):
        res = self.run_helper("set", "tap_radius=50")
        self.assertEqual(res.returncode, 2)
        self.assertIsNone(self.read(self.try_))


if __name__ == "__main__":
    unittest.main()
