# SPDX-License-Identifier: GPL-2.0
"""haltia-stop takes a pid file only while its process still runs, and
never the shell's processes; haltia-sleep reads the user's file without
trusting it.

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(rel, name):
    loader = importlib.machinery.SourceFileLoader(name, os.path.join(ROOT, rel))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


stop = load("libexec/haltia-stop", "haltia_stop")


class Stop(unittest.TestCase):
    def setUp(self):
        self.run = tempfile.mkdtemp(prefix="haltia-stop-test.")
        self.addCleanup(shutil.rmtree, self.run)
        os.makedirs(os.path.join(self.run, "haltia/launch/pid"))
        p = mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.run})
        p.start()
        self.addCleanup(p.stop)
        self.child = subprocess.Popen(["sleep", "30"])
        self.addCleanup(self.child.wait)
        self.addCleanup(self.child.kill)

    def write(self, text):
        with open(os.path.join(self.run, "haltia/launch/pid/prog"), "w") as fh:
            fh.write(text)

    def test_same_start_time_is_taken(self):
        self.write("%d %d\n" % (self.child.pid, stop.start_time(self.child.pid)))
        self.assertEqual(stop.launched("prog"), self.child.pid)
        self.assertIn(self.child.pid, stop.program("prog", []))

    def test_another_start_time_is_not(self):
        self.write("%d %d\n" % (self.child.pid, stop.start_time(self.child.pid) + 1))
        self.assertIsNone(stop.launched("prog"))
        self.assertNotIn(self.child.pid, stop.program("prog", []))

    def test_old_form_is_not(self):
        self.write("%d\n" % self.child.pid)
        self.assertIsNone(stop.launched("prog"))

    def test_shell_process_is_never_taken(self):
        self.assertTrue(stop.is_shell({"python3", "haltia-focus"}))
        self.assertTrue(stop.is_shell({"waybar"}))
        self.assertFalse(stop.is_shell({"python3", "haltia-messenger"}))
        self.assertFalse(stop.is_shell({"sh"}))
        with mock.patch.object(stop, "processes",
                               return_value={self.child.pid: (1, {"waybar"})}):
            self.write("%d %d\n" % (self.child.pid, stop.start_time(self.child.pid)))
            self.assertEqual(stop.program("prog", []), set())


class StopWhat(unittest.TestCase):
    """SH2-8 and SH2-23: what haltia-stop stops, and what it SIGKILLs."""

    def setUp(self):
        self.run = tempfile.mkdtemp(prefix="haltia-stop-test.")
        self.addCleanup(shutil.rmtree, self.run)
        os.makedirs(os.path.join(self.run, "haltia/launch/pid"))
        with open(os.path.join(self.run, "haltia/apps.conf"), "w") as fh:
            fh.write("[flat]\nlabel = Flat\napp_ids = org.example.Flat\n"
                     "exec = flatpak run --branch=stable org.example.Flat @@u %U @@\n")
        p = mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.run})
        p.start()
        self.addCleanup(p.stop)

    def test_flatpak_exec_is_not_every_flatpak(self):
        other = {4242: (1, {"flatpak"}), 4243: (4242, {"bwrap"})}
        with mock.patch.object(stop, "processes", return_value=other):
            self.assertEqual(stop.program("flat", ["org.example.Flat"]), set())
        self.assertEqual(stop.flatpak_app(
            "flatpak run --branch=stable org.example.Flat @@u %U @@".split()), "org.example.Flat")
        self.assertIsNone(stop.flatpak_app(["firefox"]))

    def test_a_reused_pid_gets_no_sigkill(self):
        times = iter([100, 200])  # chosen at 100; two seconds on, another process
        sent = []
        with mock.patch.object(stop, "start_time", lambda _p: next(times)), \
                mock.patch.object(stop, "alive", lambda _p: True), \
                mock.patch.object(stop, "descendants", lambda _p: set()), \
                mock.patch.object(stop, "TERM_WAIT", 0.1), \
                mock.patch.object(stop.os, "kill", lambda pid, sig: sent.append((pid, sig))):
            self.assertEqual(stop.stop([4242]), [])
        self.assertEqual(sent, [(4242, stop.signal.SIGTERM)])

    def test_children_forked_after_the_choice_go_too(self):
        mark = os.path.join(self.run, "late")
        # Ignores SIGTERM and forks a child when it gets one.
        prog = subprocess.Popen(["sh", "-c", 'trap "sleep 30 & echo \\$! >%s" TERM; '
                                 'while :; do sleep 0.1; done' % mark])
        self.addCleanup(prog.wait)
        self.addCleanup(prog.kill)
        import time
        time.sleep(0.3)
        with mock.patch.object(stop, "TERM_WAIT", 0.5):
            stop.stop([prog.pid])
        prog.wait(timeout=5)
        with open(mark) as fh:
            late = int(fh.read())
        time.sleep(0.2)
        self.assertFalse(stop.alive(late))


class SleepRead(unittest.TestCase):
    """haltia-sleep's read_user_file, without importing the daemon (it
    needs root and devices)."""

    @classmethod
    def setUpClass(cls):
        src = open(os.path.join(ROOT, "libexec/haltia-sleep")).read()
        start = src.index("def read_user_file(")
        end = src.index("\ndef ", start + 1)
        cls.ns = {}
        exec("import errno, os, stat\n" + src[start:end], cls.ns)

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-sleep-test.")
        self.addCleanup(shutil.rmtree, self.dir)
        self.read = self.ns["read_user_file"]

    def test_regular_file_is_read_up_to_the_limit(self):
        path = os.path.join(self.dir, "screen")
        with open(path, "w") as fh:
            fh.write("off_after=60\n" + "x" * 10000)
        text = self.read(path, os.getuid())
        self.assertTrue(text.startswith("off_after=60"))
        self.assertEqual(len(text), 4096)

    def test_fifo_does_not_block(self):
        path = os.path.join(self.dir, "screen")
        os.mkfifo(path)
        with self.assertRaises(OSError):
            self.read(path, os.getuid())

    def test_link_to_a_device_is_refused(self):
        path = os.path.join(self.dir, "screen")
        os.symlink("/dev/zero", path)
        with self.assertRaises(OSError):
            self.read(path, os.getuid())

    def test_link_even_to_the_users_own_file_is_refused(self):
        real = os.path.join(self.dir, "real")
        with open(real, "w") as fh:
            fh.write("off_after=60\n")
        path = os.path.join(self.dir, "screen")
        os.symlink(real, path)
        with self.assertRaises(OSError):
            self.read(path, os.getuid())

    def test_file_of_another_user_is_refused(self):
        path = os.path.join(self.dir, "screen")
        open(path, "w").close()
        with self.assertRaises(OSError):
            self.read(path, os.getuid() + 1)


if __name__ == "__main__":
    unittest.main()
