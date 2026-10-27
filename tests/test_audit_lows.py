# SPDX-License-Identifier: GPL-2.0
"""Small ones from the second audit (#31): haltia-gestures replaces the
user's lisgd by uid (SH2-35); install.sh writes into the person's home only
past no link (SH2-24).

    python3 -m unittest discover -s tests
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(shutil.which("pidof"), "needs pidof")
class Gestures(unittest.TestCase):
    def test_the_old_lisgd_is_ended(self):
        d = tempfile.mkdtemp(prefix="haltia-gestures.")
        self.addCleanup(shutil.rmtree, d)
        os.symlink(shutil.which("sleep"), os.path.join(d, "lisgd"))
        old = subprocess.Popen([os.path.join(d, "lisgd"), "30"])
        self.addCleanup(old.wait)
        self.addCleanup(old.kill)
        time.sleep(0.2)
        env = dict(os.environ, PATH=d + os.pathsep + os.environ["PATH"], XDG_RUNTIME_DIR=d)
        subprocess.run(["sh", os.path.join(ROOT, "libexec/haltia-gestures"), "normal"],
                       env=env, timeout=10, check=True)
        self.assertIsNotNone(old.wait(timeout=5))


class Install(unittest.TestCase):
    def test_no_write_through_a_link(self):
        with open(os.path.join(ROOT, "install.sh")) as fh:
            src = fh.read()
        at = src.index("galculator/galculator.conf\" ]")
        guard = src[src.rindex("\nif ", 0, at):at]
        for path in ('"$root/home/user"', '"$cfg"', '"$cfg/galculator"'):
            self.assertIn("! -L %s" % path, guard)


if __name__ == "__main__":
    unittest.main()
