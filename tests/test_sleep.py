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


class SelfRestart(unittest.TestCase):
    """#24: a new version of haltia-sleep takes over in the same process."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-sleep-restart.")
        self.addCleanup(shutil.rmtree, self.dir)
        self.self_path = os.path.join(self.dir, "haltia-sleep")
        self.sock_path = os.path.join(self.dir, "wake.sock")
        patches = [mock.patch.object(hs, "SELF", self.self_path),
                   mock.patch.object(hs, "WAKE_SOCKET", self.sock_path),
                   mock.patch.object(hs, "log", lambda _m: None)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def write(self, text):
        with open(self.self_path, "w") as fh:
            fh.write(text)

    def test_a_file_that_does_not_compile_is_not_run(self):
        self.write("def broken(:\n")
        with mock.patch.object(hs.os, "execve") as execve:
            hs.restart_self(None)
        execve.assert_not_called()

    def test_the_new_version_gets_the_wake_socket(self):
        self.write("print('new')\n")
        waker = hs.open_wake_socket()
        self.addCleanup(waker.close)
        with mock.patch.object(hs.os, "execve") as execve:
            hs.restart_self(waker)
        exe, argv, env = execve.call_args[0]
        self.assertEqual(argv[1:], [self.self_path])
        self.assertEqual(env[hs.WAKE_FD_ENV], str(waker.fileno()))
        self.assertTrue(os.get_inheritable(waker.fileno()))

    def test_the_passed_socket_is_taken_over(self):
        first = hs.open_wake_socket()
        fd = first.detach()
        with mock.patch.dict(hs.os.environ, {hs.WAKE_FD_ENV: str(fd)}):
            again = hs.open_wake_socket()
            self.assertNotIn(hs.WAKE_FD_ENV, hs.os.environ)
        self.addCleanup(again.close)
        self.assertEqual(again.fileno(), fd)
        self.assertFalse(os.get_inheritable(fd))
        # Still listening at the same path: a client queued meanwhile is heard.
        client = hs.socket.socket(hs.socket.AF_UNIX, hs.socket.SOCK_STREAM)
        self.addCleanup(client.close)
        client.connect(self.sock_path)

    def test_grabbed_touch_devices_come_over_open(self):
        self.write("print('new')\n")
        dev = os.path.join(self.dir, "event4")
        open(dev, "w").close()
        fd = os.open(dev, os.O_RDONLY)
        self.addCleanup(os.close, fd)
        with mock.patch.object(hs.os, "execve") as execve:
            hs.restart_self(None, [fd])
        env = execve.call_args[0][2]
        self.assertEqual(env[hs.TOUCH_FDS_ENV], "%d:%s" % (fd, dev))
        self.assertTrue(os.get_inheritable(fd))
        # The new version takes it while it is still that device.
        self.assertEqual(hs.adopt_fds(env[hs.TOUCH_FDS_ENV]), [fd])
        self.assertFalse(os.get_inheritable(fd))
        self.assertEqual(hs.adopt_fds("%d:/dev/input/event9" % fd), [])
        self.assertEqual(hs.adopt_fds("x:y,,"), [])

    def test_a_changed_file_has_a_new_id(self):
        self.write("a\n")
        before = hs.file_id(self.self_path)
        os.replace(self._other("b\n"), self.self_path)  # as apk installs it
        self.assertNotEqual(hs.file_id(self.self_path), before)

    def _other(self, text):
        path = self.self_path + ".new"
        with open(path, "w") as fh:
            fh.write(text)
        return path


if __name__ == "__main__":
    unittest.main()
