# SPDX-License-Identifier: GPL-2.0
"""haltia-sleep's loop on a dark screen: KEY_WAKEUP and touches count only
with double_tap_wake=1, and the power key's press that came with such a
wake-up leaves the lamp on (#81 review). The loop runs against pipes for
the power key, an input device and the grabbed touch screen.

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import select
import shutil
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    path = os.path.join(ROOT, "libexec/haltia-sleep")
    loader = importlib.machinery.SourceFileLoader("haltia_sleep_loop", path)
    spec = importlib.util.spec_from_loader("haltia_sleep_loop", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


S = load()


class Stop(Exception):
    pass


class FakeLamp:
    def __init__(self, touch):
        self.asleep = True
        self.touch = [touch]
        self.suspender = None
        self.did = []

    def press(self):
        self.did.append("press")
        self.asleep = not self.asleep

    def wake(self):
        self.did.append("wake")
        self.asleep = False

    def sleep(self):
        self.did.append("sleep")
        self.asleep = True

    def suspend_due(self):
        return None

    def _grab_touch(self):
        pass


class Loop(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-sleep-loop.")
        self.addCleanup(shutil.rmtree, self.dir)
        self.power_path = os.path.join(self.dir, "power")
        os.mkfifo(self.power_path)
        # Opened for writing first, so listen's open does not block.
        self.power_w = os.open(self.power_path, os.O_RDWR)
        self.addCleanup(os.close, self.power_w)
        self.act_r, self.act_w = os.pipe()
        self.touch_r, self.touch_w = os.pipe()
        for fd in (self.act_r, self.act_w, self.touch_r, self.touch_w):
            self.addCleanup(os.close, fd)
        for fd in (self.act_r, self.touch_r):
            os.set_blocking(fd, False)  # as haltia-sleep opens real devices
        self.lamp = FakeLamp(self.touch_r)
        self.stop = threading.Event()

    def start(self, double_tap):
        stop = self.stop

        def short_select(r, w, x, timeout=None):
            if stop.is_set():
                raise Stop()
            # Short waits, so the loop sees the stop; a held key's wait is
            # left as it is.
            if len(r) == 1 and timeout is not None:
                return select.select(r, w, x, timeout)
            return select.select(r, w, x, min(timeout if timeout is not None else 0.05, 0.05))
        conf = {"double_tap_wake": "1" if double_tap else None}
        patches = [
            mock.patch.object(S, "find_power_key", return_value=self.power_path),
            mock.patch.object(S, "open_home_forward", side_effect=OSError(1, "no uinput")),
            mock.patch.object(S, "Lamp", lambda: self.lamp),
            mock.patch.object(S, "open_wake_socket", side_effect=OSError(1, "no socket")),
            mock.patch.object(S, "file_id", return_value=None),
            mock.patch.object(S, "activity_nodes", return_value=[self.act_r]),
            mock.patch.object(S, "event_nodes", return_value=[]),
            mock.patch.object(S, "idle_off", return_value=None),
            mock.patch.object(S, "updates_when_kept_on", return_value=(None, None)),
            mock.patch.object(S, "device_conf", lambda key: conf.get(key)),
            mock.patch.object(S, "power_menu", lambda: None),
            mock.patch.object(S, "log", lambda _m: None),
            mock.patch.object(S, "select", types.SimpleNamespace(select=short_select)),
        ]
        for p in patches:
            p.start()
        thread = threading.Thread(target=self.run_listen, daemon=True)
        thread.start()

        def end():
            stop.set()
            thread.join(5)
            for p in patches:
                p.stop()
        self.addCleanup(end)

    def run_listen(self):
        try:
            S.listen()
        except Stop:
            pass

    def send(self, fd, *events):
        data = b""
        for etype, code, value in events:
            ev = S.InputEvent()
            ev.type, ev.code, ev.value = etype, code, value
            data += bytes(ev)
        os.write(fd, data)

    def settle(self):
        time.sleep(0.4)

    def test_key_wakeup_then_the_power_key_leaves_the_lamp_on(self):
        self.start(double_tap=True)
        self.send(self.act_w, (S.EV_KEY, S.KEY_WAKEUP, 1), (S.EV_SYN, 0, 0))
        time.sleep(0.15)
        self.send(self.power_w, (S.EV_KEY, S.KEY_POWER, 1))
        self.send(self.power_w, (S.EV_KEY, S.KEY_POWER, 0))
        self.settle()
        self.assertEqual(self.lamp.did, ["wake"])
        self.assertFalse(self.lamp.asleep)

    def test_a_later_press_still_turns_it_off(self):
        self.start(double_tap=True)
        self.send(self.act_w, (S.EV_KEY, S.KEY_WAKEUP, 1))
        time.sleep(S.WAKE_GRACE + 0.2)
        self.send(self.power_w, (S.EV_KEY, S.KEY_POWER, 1))
        self.send(self.power_w, (S.EV_KEY, S.KEY_POWER, 0))
        self.settle()
        self.assertEqual(self.lamp.did, ["wake", "press"])
        self.assertTrue(self.lamp.asleep)

    def test_a_double_tap_wakes(self):
        self.start(double_tap=True)
        self.send(self.touch_w, (S.EV_KEY, S.BTN_TOUCH, 1), (S.EV_KEY, S.BTN_TOUCH, 0),
                  (S.EV_KEY, S.BTN_TOUCH, 1), (S.EV_KEY, S.BTN_TOUCH, 0))
        self.settle()
        self.assertEqual(self.lamp.did, ["wake"])

    def test_without_double_tap_wake_nothing_but_the_power_key_counts(self):
        self.start(double_tap=False)
        self.send(self.act_w, (S.EV_KEY, S.KEY_WAKEUP, 1))
        self.send(self.touch_w, (S.EV_KEY, S.BTN_TOUCH, 1), (S.EV_KEY, S.BTN_TOUCH, 0),
                  (S.EV_KEY, S.BTN_TOUCH, 1), (S.EV_KEY, S.BTN_TOUCH, 0))
        self.settle()
        self.assertEqual(self.lamp.did, [])
        # The dark screen's touches were not even read.
        self.assertTrue(select.select([self.touch_r], [], [], 0)[0])
        self.send(self.power_w, (S.EV_KEY, S.KEY_POWER, 1))
        self.send(self.power_w, (S.EV_KEY, S.KEY_POWER, 0))
        self.settle()
        self.assertEqual(self.lamp.did, ["press"])
        self.assertFalse(self.lamp.asleep)


if __name__ == "__main__":
    unittest.main()
