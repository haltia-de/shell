# SPDX-License-Identifier: GPL-2.0
"""haltia-volume: lost events stop a held key's slope, an unplugged keypad
leaves the others working, and a machine without volume keys ends with
NOTHING, which haltia-keep leaves off (#31: SH2-34, SH2-36).

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    path = os.path.join(ROOT, "libexec/haltia-volume")
    loader = importlib.machinery.SourceFileLoader("haltia_volume", path)
    spec = importlib.util.spec_from_loader("haltia_volume", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


hv = load()


class VolumeKeys(unittest.TestCase):
    def setUp(self):
        self.steps = []
        for p in (mock.patch.object(hv, "step", lambda level, by: self.steps.append(by) or level),
                  mock.patch.object(hv, "volume", lambda: 50)):
            p.start()
            self.addCleanup(p.stop)

    def keypads(self, n):
        pads, ends = {}, []
        for i in range(n):
            r, w = os.pipe()
            pads[os.fdopen(r, "rb", buffering=0)] = "/dev/input/event%d" % i
            ends.append(w)
        return pads, ends

    def send(self, fd, etype, code, value):
        os.write(fd, hv.EVENT.pack(0, 0, etype, code, value))

    def run_main(self, pads):
        result = []
        with mock.patch.object(hv, "open_keypads", return_value=pads):
            t = threading.Thread(target=lambda: result.append(hv.main()), daemon=True)
            t.start()
        return t, result

    def test_lost_events_end_a_held_key(self):
        pads, (w,) = self.keypads(1)
        t, result = self.run_main(pads)
        self.send(w, hv.EV_KEY, hv.KEY_VOLUMEUP, 1)
        self.send(w, hv.EV_SYN, hv.SYN_DROPPED, 0)  # the release was lost
        time.sleep(hv.HOLD + 0.3)
        os.close(w)
        t.join(5)
        self.assertEqual(self.steps, [hv.STEP])  # the press, no slope after it
        self.assertEqual(result, [1])  # its only keypad gone

    def test_an_unplugged_keypad_leaves_the_others(self):
        pads, (usb, builtin) = self.keypads(2)
        t, result = self.run_main(pads)
        os.close(usb)
        time.sleep(0.2)
        self.assertTrue(t.is_alive())
        self.send(builtin, hv.EV_KEY, hv.KEY_VOLUMEDOWN, 1)
        self.send(builtin, hv.EV_KEY, hv.KEY_VOLUMEDOWN, 0)
        time.sleep(0.2)
        os.close(builtin)
        t.join(5)
        self.assertEqual(self.steps, [-hv.STEP])
        self.assertEqual(result, [1])

    def test_no_keypad_is_nothing_to_do(self):
        with mock.patch.object(hv, "find_keypads", return_value=[]), \
                mock.patch.object(hv, "DEVICE_WAIT", 0):
            self.assertEqual(hv.main(), hv.NOTHING)

    def test_keep_leaves_nothing_to_do_off(self):
        # Ends with 3 after QUIET seconds: still left off, not restarted.
        out = subprocess.run(["sh", os.path.join(ROOT, "libexec/haltia-keep"),
                              "sh", "-c", "echo ran; sleep 3.2; exit 3"],
                             capture_output=True, text=True, timeout=15)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.split(), ["ran"])
        self.assertIn("nothing to do", out.stderr)


if __name__ == "__main__":
    unittest.main()
