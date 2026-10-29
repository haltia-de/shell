# SPDX-License-Identifier: GPL-2.0
"""haltia-sleep: two short taps on the dark screen, or KEY_WAKEUP from a
device, turn the lamp on (double_tap_wake=1 in device.conf).

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    path = os.path.join(ROOT, "libexec/haltia-sleep")
    loader = importlib.machinery.SourceFileLoader("haltia_sleep", path)
    spec = importlib.util.spec_from_loader("haltia_sleep", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


S = load()


def taps(events):
    """Feed (value, time) presses; the times at which a double tap ends."""
    t = S.DoubleTap()
    return [now for value, now in events if t.feed(value, now)]


class DoubleTapTest(unittest.TestCase):
    def test_two_short_taps(self):
        self.assertEqual(taps([(1, 0.0), (0, 0.1), (1, 0.3), (0, 0.4)]), [0.4])

    def test_one_tap_is_not_enough(self):
        self.assertEqual(taps([(1, 0.0), (0, 0.1)]), [])

    def test_taps_too_far_apart(self):
        self.assertEqual(taps([(1, 0.0), (0, 0.1), (1, 0.6), (0, 0.7)]), [])

    def test_a_long_touch_is_no_tap(self):
        self.assertEqual(taps([(1, 0.0), (0, 0.5), (1, 0.6), (0, 0.7)]), [])

    def test_third_tap_starts_again(self):
        self.assertEqual(taps([(1, 0.0), (0, 0.1), (1, 0.2), (0, 0.3),
                               (1, 0.4), (0, 0.5)]), [0.3])

    def test_key_wakeup_wakes(self):
        r, w = os.pipe()
        ev = S.InputEvent()
        ev.type, ev.code, ev.value = S.EV_KEY, S.KEY_WAKEUP, 1
        os.write(w, bytes(ev))
        try:
            self.assertTrue(S.woken_by(r, None))
        finally:
            os.close(r)
            os.close(w)


class Filter(unittest.TestCase):
    """haltia-touchguard lets the double tap through while the screen is
    dark, and passes the chip's KEY_WAKEUP on (#81 review). The filter is C
    and needs root and uinput: these look at its source."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "tools/haltia-touchguard.c")) as fh:
            cls.src = fh.read()

    def test_no_repeat_drop_while_dark(self):
        at = self.src.index("int repeat = ")
        rule = self.src[at:self.src.index(";", at)]
        self.assertIn("!screen_dark()", rule)
        self.assertIn('"/run/haltia/screen-dark"', self.src)
        self.assertIn(S.DARK_PATH, self.src)

    def test_key_wakeup_goes_through(self):
        self.assertIn("UI_SET_KEYBIT, KEY_WAKEUP", self.src)
        self.assertIn("emit(EV_KEY, KEY_WAKEUP, ev->value)", self.src)



class LidTest(unittest.TestCase):
    def events(self, *values):
        r, w = os.pipe()
        for v in values:
            ev = S.InputEvent()
            ev.type, ev.code, ev.value = S.EV_SW, S.SW_LID, v
            os.write(w, bytes(ev))
        try:
            return S.lid_closed(r)
        finally:
            os.close(r)
            os.close(w)

    def test_closed(self):
        self.assertIs(self.events(1), True)

    def test_opened(self):
        self.assertIs(self.events(0), False)

    def test_last_state_wins(self):
        self.assertIs(self.events(1, 0), False)

    def test_other_events_are_no_change(self):
        r, w = os.pipe()
        ev = S.InputEvent()
        ev.type, ev.code, ev.value = S.EV_KEY, S.KEY_POWER, 1
        os.write(w, bytes(ev))
        try:
            self.assertIsNone(S.lid_closed(r))
        finally:
            os.close(r)
            os.close(w)


if __name__ == "__main__":
    unittest.main()
