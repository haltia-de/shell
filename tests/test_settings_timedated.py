# SPDX-License-Identifier: GPL-2.0
"""Настройки → «Дата и время» asks timedated without waiting: a slow
service (polkit, timedated starting) no longer freezes the window (#31:
SH2-47). DateTime.call against a private bus whose timedate1 is busy.

    python3 -m unittest discover -s tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

try:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
except (ImportError, ValueError):
    Gio = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BUSY = """
import sys, time
import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib
conn = Gio.DBusConnection.new_for_address_sync(
    sys.argv[1], Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
    | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
XML = '''<node><interface name="org.freedesktop.timedate1">
<method name="SetNTP"><arg type="b" direction="in"/><arg type="b" direction="in"/></method>
</interface></node>'''


def call(conn, sender, path, iface, method, params, invocation):
    invocation.return_value(None)


info = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
conn.register_object("/org/freedesktop/timedate1", info, call, None, None)
conn.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
               "RequestName", GLib.Variant("(su)", ("org.freedesktop.timedate1", 0)), None,
               Gio.DBusCallFlags.NONE, -1, None)
open(sys.argv[2], "w").close()
time.sleep(1.5)  # busy (polkit asking, say): its answer waits until then
GLib.MainLoop().run()
"""


def date_time_class():
    with open(os.path.join(ROOT, "bin/haltia-settings")) as fh:
        src = fh.read()
    start = src.index("class DateTime:")
    end = src.index("\n# ---", start)
    ns = {"Gio": Gio, "GLib": GLib, "sys": sys, "os": os, "time": time}
    exec(src[start:end], ns)
    return ns["DateTime"]


@unittest.skipIf(Gio is None or not shutil.which("dbus-daemon"), "needs PyGObject and dbus-daemon")
class TimeDated(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-timedated.")
        self.addCleanup(shutil.rmtree, self.dir)
        self.dbus = Gio.TestDBus.new(Gio.TestDBusFlags.NONE)
        self.dbus.up()
        self.addCleanup(self.dbus.down)
        script = os.path.join(self.dir, "busy.py")
        with open(script, "w") as fh:
            fh.write(BUSY)
        ready = os.path.join(self.dir, "ready")
        proc = subprocess.Popen([sys.executable, script, self.dbus.get_bus_address(), ready])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        end = time.monotonic() + 5
        while not os.path.exists(ready) and time.monotonic() < end:
            time.sleep(0.05)

    def test_a_busy_timedated_does_not_hold_up_the_window(self):
        DateTime = date_time_class()
        notes, answers, refreshed = [], [], []

        class Page:
            BUS = DateTime.BUS
            bus = Gio.DBusConnection.new_for_address_sync(
                self.dbus.get_bus_address(),
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
            note = type("Note", (), {"set_text": lambda _s, t: notes.append(t)})()

            def refresh(self):
                refreshed.append(True)
        start = time.monotonic()
        DateTime.call(Page(), "SetNTP", GLib.Variant("(bb)", (True, False)), answers.append)
        self.assertLess(time.monotonic() - start, 0.3)
        ctx = GLib.MainContext.default()
        end = time.monotonic() + 8
        while not answers and time.monotonic() < end:
            while ctx.pending():
                ctx.iteration(False)
            time.sleep(0.02)
        self.assertEqual(answers, [True])
        self.assertGreater(time.monotonic() - start, 1.0)  # it did wait for the answer
        self.assertEqual(notes, [""])
        self.assertEqual(refreshed, [True])

    def test_no_bus_tells_and_waits_for_nothing(self):
        DateTime = date_time_class()
        notes = []

        class Page:
            BUS = DateTime.BUS
            bus = None
            note = type("Note", (), {"set_text": lambda _s, t: notes.append(t)})()
        DateTime.call(Page(), "SetNTP", GLib.Variant("(bb)", (True, False)), lambda _ok: None)
        self.assertTrue(notes[0].startswith("Не получилось"))


if __name__ == "__main__":
    unittest.main()
