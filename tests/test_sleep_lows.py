# SPDX-License-Identifier: GPL-2.0
"""haltia-sleep's low findings from the second audit (#31): charging from
sysfs (SH2-26), the inhibitor look kept and bounded (SH2-27), no crash on
an unwritable /var (SH2-28), the session's programs started without
preexec_fn (SH2-25), only key-sending devices as activity (SH2-32), and the
loop's backoff and stop (SH2-18).

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import pwd
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    path = os.path.join(ROOT, "libexec/haltia-sleep")
    loader = importlib.machinery.SourceFileLoader("haltia_sleep_lows", path)
    spec = importlib.util.spec_from_loader("haltia_sleep_lows", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


hs = load()


class Lows(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-sleep-lows.")
        self.addCleanup(shutil.rmtree, self.dir)
        p = mock.patch.object(hs, "log", lambda _m: None)
        p.start()
        self.addCleanup(p.stop)

    def supplies(self, **kinds):
        root = tempfile.mkdtemp(prefix="power_supply.", dir=self.dir)
        for name, kind in kinds.items():
            os.makedirs(os.path.join(root, name))
            with open(os.path.join(root, name, "type"), "w") as fh:
                fh.write(kind + "\n")
        return root

    def test_charging_from_sysfs(self):
        root = self.supplies(battery="Battery", charger="USB")
        with mock.patch.object(hs, "POWER_SUPPLY", root):
            with mock.patch.object(hs, "external_power", lambda: True):
                self.assertTrue(hs.charging())
            with mock.patch.object(hs, "external_power", lambda: False):
                self.assertFalse(hs.charging())
        with mock.patch.object(hs, "POWER_SUPPLY", self.supplies(ac="Mains")), \
                mock.patch.object(hs, "external_power", lambda: False):
            self.assertTrue(hs.charging())  # no battery at all: a desktop

    def test_a_failed_inhibitor_look_keeps_the_last_answer(self):
        class Bus:
            fail = False

            def is_closed(self):
                return False

            def call_sync(self, *_a):
                if Bus.fail:
                    raise RuntimeError("slow")
                from gi.repository import GLib
                return GLib.Variant("(a(ssssuu))", ([("idle:sleep", "mpv", "plays",
                                                       "block", 1000, 42)],))
        with mock.patch.dict(hs._inhibit, {"bus": Bus(), "last": {}}):
            self.assertTrue(hs.inhibited("idle"))
            Bus.fail = True
            self.assertTrue(hs.inhibited("idle"))  # not dropped by a slow bus
            self.assertFalse(hs.inhibited("handle-lid-switch"))

    def test_an_unwritable_var_does_not_end_the_daemon(self):
        blocker = os.path.join(self.dir, "not-a-folder")
        open(blocker, "w").close()
        with mock.patch.object(hs, "UPDATE_STATE", os.path.join(blocker, "update")), \
                mock.patch.object(hs, "charging", lambda: True), \
                mock.patch.object(hs.os, "access", lambda *_a: True), \
                mock.patch.object(hs.subprocess, "Popen") as popen:
            hs.updates_when_dark()  # no OSError out of it
        popen.assert_not_called()

    def test_session_programs_start_without_preexec_fn(self):
        me = pwd.getpwuid(os.getuid())
        env = {"USER": me.pw_name, "HOME": self.dir}
        with mock.patch.object(hs, "session_env", lambda: (env, me.pw_uid, me.pw_gid)), \
                mock.patch.object(hs.subprocess, "Popen") as popen:
            self.assertTrue(hs.as_session_user(["true"]))
        kw = popen.call_args.kwargs
        self.assertNotIn("preexec_fn", kw)
        self.assertEqual((kw["user"], kw["group"]), (me.pw_uid, me.pw_gid))
        self.assertTrue(kw["start_new_session"])

    def test_only_key_sending_devices_are_activity(self):
        caps = {"/sys/class/input/event2/device/capabilities/ev": "b\n",  # SYN KEY ABS
                "/sys/class/input/event7/device/capabilities/ev": "9\n"}  # SYN ABS

        def fake_open(path, *a, **k):
            if path in caps:
                return mock.mock_open(read_data=caps[path])()
            raise FileNotFoundError(path)
        with mock.patch("builtins.open", fake_open):
            self.assertTrue(hs.has_keys("event2"))
            self.assertFalse(hs.has_keys("event7"))
            self.assertTrue(hs.has_keys("event9"))  # unknown: counted


class Loop(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-sleep-loop.")
        self.addCleanup(shutil.rmtree, self.dir)
        with open(os.path.join(ROOT, "libexec/haltia-sleep-loop")) as fh:
            src = fh.read().replace("/run/haltia", os.path.join(self.dir, "run"))
        self.loop = os.path.join(self.dir, "loop")
        with open(self.loop, "w") as fh:
            fh.write(src)
        os.makedirs(os.path.join(self.dir, "bin"))
        self.count = os.path.join(self.dir, "count")

    def fake_python(self, body):
        path = os.path.join(self.dir, "bin", "python3")
        with open(path, "w") as fh:
            fh.write("#!/bin/sh\necho x >>%s\n%s\n" % (self.count, body))
        os.chmod(path, 0o755)

    def run_loop(self, seconds):
        env = dict(os.environ, PATH=os.path.join(self.dir, "bin") + os.pathsep + os.environ["PATH"])
        proc = subprocess.Popen(["sh", self.loop], env=env)
        try:
            return proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return None

    def starts(self):
        try:
            with open(self.count) as fh:
                return len(fh.readlines())
        except FileNotFoundError:
            return 0

    def test_nothing_to_do_ends_the_loop(self):
        self.fake_python("exit 3")
        self.assertEqual(self.run_loop(5), 0)
        self.assertEqual(self.starts(), 1)

    def test_quick_ends_wait_longer_each_time(self):
        self.fake_python("exit 1")
        self.run_loop(6.5)  # 1 + 2 s of pauses fit, the next 4 s does not
        self.assertEqual(self.starts(), 3)


if __name__ == "__main__":
    unittest.main()
