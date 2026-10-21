# SPDX-License-Identifier: GPL-2.0
"""haltia-sleep keeps the system up on the charger: external_power reads
the power supplies, not the battery's status.

    python3 -m unittest discover -s tests
"""
import os
import shutil
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def functions():
    src = open(os.path.join(ROOT, "libexec/haltia-sleep")).read()
    start = src.index("_power = {")
    end = src.index("def charging():")
    ns = {"SCREEN_CHECK": 30.0, "log": lambda _m: None}
    exec("import os, time\n" + src[start:end], ns)
    return ns


class Charger(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-power-test.")
        self.addCleanup(shutil.rmtree, self.dir)
        self.ns = functions()
        self.ns["POWER_SUPPLY"] = self.dir

    def supply(self, name, kind, online=None, status=None):
        d = os.path.join(self.dir, name)
        os.makedirs(d)
        for key, value in (("type", kind), ("online", online), ("status", status)):
            if value is not None:
                with open(os.path.join(d, key), "w") as fh:
                    fh.write(value + "\n")

    def test_usb_charger_online(self):
        self.supply("battery", "Battery", status="Full")
        self.supply("bq24190-charger", "USB", online="1", status="Full")
        self.assertTrue(self.ns["external_power"]())

    def test_unplugged(self):
        self.supply("battery", "Battery", status="Discharging")
        self.supply("bq24190-charger", "USB", online="0")
        self.assertFalse(self.ns["external_power"]())

    def test_mains_while_not_charging(self):
        self.supply("BAT0", "Battery", status="Not charging")
        self.supply("AC", "Mains", online="1")
        self.assertTrue(self.ns["external_power"]())

    def test_looked_at_once_in_a_while(self):
        self.supply("AC", "Mains", online="1")
        self.assertTrue(self.ns["external_power"]())
        with open(os.path.join(self.dir, "AC", "online"), "w") as fh:
            fh.write("0\n")
        self.assertTrue(self.ns["external_power"]())  # within SCREEN_CHECK
        self.ns["_power"]["at"] = time.monotonic() - 31
        self.assertFalse(self.ns["external_power"]())


if __name__ == "__main__":
    unittest.main()
