# SPDX-License-Identifier: GPL-2.0
"""haltia-launch starts one Firefox: its icon (open firefox) and a link from
a program (url) share one lock, and either waits for a Firefox that is still
starting instead of running a second one on the same profile (#31, FFX2-1).
A start removes only its own curtain marker (SH2-46).
Run on a copy with Firefox and haltia-focus as stand-ins.

    python3 -m unittest discover -s tests
"""
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The stand-in's process name, so that a real Firefox on the machine
# running the tests is not counted.
PROC = "tffx-firefox"

FIREFOX = """#!/bin/sh
# Stand-in: a second start hands the link to the running one and ends, as
# Firefox's remote service does, but only once that one has its window;
# before, it is a second Firefox on the same profile (logged as a start).
# A first one shows its window %(delay)s s on.
if pidof %(proc)s >/dev/null && [ -e "%(dir)s/window" ]; then
	echo "remote $*" >>"%(dir)s/firefox.log"
	exit 0
fi
echo "start $*" >>"%(dir)s/firefox.log"
( sleep %(delay)s; touch "%(dir)s/window" ) &
exec "%(dir)s/real/%(proc)s" 20
"""
FOCUS = """#!/bin/sh
# Stand-in: Firefox's window is there once the stand-in made it.
[ -e "%(dir)s/window" ] || exit 1
[ "$1" = activate ] && echo activate >>"%(dir)s/focus.log"
exit 0
"""


class LaunchCopy(unittest.TestCase):
    """A copy of haltia-launch with stand-ins; no tests of its own."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-firefox-lock.")
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(self.stop_firefox)
        d = self.dir
        self.bin = os.path.join(d, "bin")
        os.makedirs(self.bin)
        os.makedirs(os.path.join(d, "real"))
        os.symlink(shutil.which("sleep"), os.path.join(d, "real", PROC))
        os.makedirs(os.path.join(d, "run/haltia/launch"))
        os.makedirs(os.path.join(d, "home"))
        with open(os.path.join(d, "run/haltia/apps.conf"), "w") as fh:
            fh.write("[firefox]\nlabel = Firefox\nsignal = 1\n"
                     "app_ids = firefox Firefox org.mozilla.firefox\nexec = firefox\n")
        self.write("firefox", FIREFOX, delay="1.5")
        self.write("haltia-focus", FOCUS)
        self.write("haltia-firefox-profile", "#!/bin/sh\nexit 0\n")
        with open(os.path.join(ROOT, "bin/haltia-launch")) as fh:
            src = fh.read()
        self.assertIn('pidof "$1"', src)
        src = src.replace('pidof "$1"', 'pidof "tffx-$1"')
        src = src.replace("FIREFOX_TRIES=80", "FIREFOX_TRIES=20")
        src = src.replace("/usr/bin/haltia-focus", os.path.join(self.bin, "haltia-focus"))
        src = src.replace("/usr/libexec/haltia/", self.bin + "/")
        self.launch = os.path.join(d, "haltia-launch")
        with open(self.launch, "w") as fh:
            fh.write(src)

    def write(self, name, body, **extra):
        path = os.path.join(self.bin, name)
        with open(path, "w") as fh:
            fh.write(body % dict(dir=self.dir, proc=PROC, **extra))
        os.chmod(path, 0o755)

    def stop_firefox(self):
        out = subprocess.run(["pidof", PROC], capture_output=True, text=True).stdout
        for pid in out.split():
            try:
                os.kill(int(pid), signal.SIGTERM)
            except OSError:
                pass

    def env(self):
        return dict(os.environ, HOME=os.path.join(self.dir, "home"),
                    XDG_RUNTIME_DIR=os.path.join(self.dir, "run"),
                    PATH=self.bin + os.pathsep + os.environ["PATH"])

    def launch_bg(self, *args):
        return subprocess.Popen(["sh", self.launch, *args], env=self.env(),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def log(self):
        try:
            with open(os.path.join(self.dir, "firefox.log")) as fh:
                return fh.read().splitlines()
        except FileNotFoundError:
            return []

    def starts(self):
        return [line for line in self.log() if line.startswith("start")]


class FirefoxLock(LaunchCopy):
    def test_link_while_icon_starts_firefox(self):
        icon = self.launch_bg("open", "firefox")
        time.sleep(0.3)
        link = self.launch_bg("url", "https://example.org/story")
        self.assertEqual(icon.wait(timeout=15), 0)
        self.assertEqual(link.wait(timeout=20), 0)
        self.assertEqual(len(self.starts()), 1, self.log())
        self.assertIn("remote https://example.org/story", self.log())

    def test_icon_while_link_starts_firefox(self):
        link = self.launch_bg("url", "https://example.org/story")
        time.sleep(0.3)
        icon = self.launch_bg("open", "firefox")
        self.assertEqual(link.wait(timeout=15), 0)
        self.assertEqual(icon.wait(timeout=15), 0)
        self.assertEqual(self.starts(), ["start https://example.org/story"])

    def test_icon_waits_for_a_firefox_without_a_window(self):
        # A Firefox started some other way, still without its window.
        other = subprocess.Popen(["sh", os.path.join(self.bin, "firefox")], env=self.env())
        self.addCleanup(other.wait)
        self.addCleanup(other.kill)
        time.sleep(0.3)
        icon = self.launch_bg("open", "firefox")
        self.assertEqual(icon.wait(timeout=15), 0)
        self.assertEqual(len(self.starts()), 1, self.log())
        self.assertFalse([line for line in self.log() if line.startswith("remote")])
        with open(os.path.join(self.dir, "focus.log")) as fh:
            self.assertIn("activate", fh.read())

    def test_same_link_after_a_long_start_only_raises(self):
        # Repeated taps on a link while Firefox starts wait for it and then
        # only raise it: no second tab with the same page.
        self.write("firefox", FIREFOX, delay="2")
        first = self.launch_bg("url", "https://example.org/story")
        time.sleep(0.3)
        again = self.launch_bg("url", "https://example.org/story")
        self.assertEqual(first.wait(timeout=15), 0)
        self.assertEqual(again.wait(timeout=15), 0)
        self.assertEqual(self.starts(), ["start https://example.org/story"])
        self.assertFalse([line for line in self.log() if line.startswith("remote")])


class Starting(LaunchCopy):
    """Two programs starting at once: the one that gets its window first
    leaves the other's curtain marker alone (#31: SH2-46)."""

    def setUp(self):
        super().setUp()
        d = self.dir
        with open(os.path.join(d, "run/haltia/apps.conf"), "a") as fh:
            for name in ("quick", "slow"):
                fh.write("[%s]\nlabel = %s\napp_ids = %s.App\nexec = %s\n" % (name, name, name, name))
        for name, delay in (("quick", "0.3"), ("slow", "2.5")):
            self.write(name, "#!/bin/sh\n( sleep %s; touch \"%%(dir)s/win-%s.App\" ) &\n"
                       "exec sleep 6\n" % (delay, name))
        self.write("haltia-focus", '#!/bin/sh\n[ "$1" = has ] || exit 1\nshift\n'
                   'for n in "$@"; do [ -e "%(dir)s/win-$n" ] && exit 0; done\nexit 1\n')

    def test_one_start_leaves_the_others_marker(self):
        starting = os.path.join(self.dir, "run/haltia/launch/starting")
        quick = self.launch_bg("open", "quick")
        time.sleep(0.1)
        slow = self.launch_bg("open", "slow")  # writes its line over quick's
        self.assertEqual(quick.wait(timeout=10), 0)
        with open(starting) as fh:
            self.assertTrue(fh.read().startswith("slow "))
        self.assertEqual(slow.wait(timeout=10), 0)
        self.assertFalse(os.path.exists(starting))


if __name__ == "__main__":
    unittest.main()
