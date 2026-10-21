# SPDX-License-Identifier: GPL-2.0
"""haltia-badges' BackStep: the front program's GTK action app.back, followed
over org.gtk.Actions on a private session bus, ends up in
haltia/launch/back as "APP_ID 1", "APP_ID 0" or "APP_ID -".

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import shutil
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ID = "io.github.haltia_de.BackTest"

try:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
except (ImportError, ValueError):
    Gio = None


def badges():
    path = os.path.join(ROOT, "libexec/haltia-badges")
    loader = importlib.machinery.SourceFileLoader("haltia_badges", path)
    spec = importlib.util.spec_from_loader("haltia_badges", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@unittest.skipIf(Gio is None or not shutil.which("dbus-daemon"), "needs PyGObject and dbus-daemon")
class BackStep(unittest.TestCase):
    def setUp(self):
        self.run_dir = tempfile.mkdtemp(prefix="haltia-back-test.")
        self.addCleanup(shutil.rmtree, self.run_dir)
        old = os.environ.get("XDG_RUNTIME_DIR")
        os.environ["XDG_RUNTIME_DIR"] = self.run_dir
        self.addCleanup(lambda: os.environ.__setitem__("XDG_RUNTIME_DIR", old) if old
                        else os.environ.pop("XDG_RUNTIME_DIR", None))
        self.dbus = Gio.TestDBus.new(Gio.TestDBusFlags.NONE)
        self.dbus.up()
        self.addCleanup(self.dbus.down)
        self.bus = Gio.DBusConnection.new_for_address_sync(
            self.dbus.get_bus_address(),
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        self.launch = os.path.join(self.run_dir, "haltia", "launch")
        os.makedirs(self.launch)
        self.module = badges()

    def program(self):
        """The actions a GApplication with app.back puts on the bus, under
        APP_ID at its object path (a plain group: an application must be
        registered to answer)."""
        group = Gio.SimpleActionGroup()
        action = Gio.SimpleAction.new(self.module.BACK, None)
        action.set_enabled(False)
        group.add_action(action)
        self.conn = Gio.DBusConnection.new_for_address_sync(
            self.dbus.get_bus_address(),
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        self.conn.export_action_group(self.module.object_path(APP_ID), group)
        self.own(True)
        self.addCleanup(self.conn.close_sync, None)
        return group, action

    def own(self, take):
        self.conn.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
                            "org.freedesktop.DBus", "RequestName" if take else "ReleaseName",
                            GLib.Variant("(su)", (APP_ID, 0)) if take
                            else GLib.Variant("(s)", (APP_ID,)), None,
                            Gio.DBusCallFlags.NONE, -1, None)

    def front(self, app_id):
        path = os.path.join(self.launch, "front")
        with open(path + ".new", "w") as fh:
            fh.write(app_id + "\n")
        os.replace(path + ".new", path)

    def wait_for(self, text, seconds=3):
        path = os.path.join(self.launch, "back")
        ctx = GLib.MainContext.default()
        end = time.monotonic() + seconds
        got = None
        while time.monotonic() < end:
            while ctx.pending():
                ctx.iteration(False)
            try:
                with open(path) as fh:
                    got = fh.read()
            except OSError:
                got = None
            if got == text:
                return
            time.sleep(0.02)
        self.fail("launch/back is %r, not %r" % (got, text))

    def test_follows_the_action(self):
        _group, action = self.program()
        self.front(APP_ID)
        self.module.BackStep(self.bus)
        self.wait_for(APP_ID + " 0\n")
        action.set_enabled(True)
        self.wait_for(APP_ID + " 1\n")
        action.set_enabled(False)
        self.wait_for(APP_ID + " 0\n")

    def test_action_removed_and_added(self):
        group, action = self.program()
        self.front(APP_ID)
        self.module.BackStep(self.bus)
        self.wait_for(APP_ID + " 0\n")
        group.remove_action(self.module.BACK)
        self.wait_for(APP_ID + " -\n")
        action.set_enabled(True)
        group.add_action(action)
        self.wait_for(APP_ID + " 1\n")

    def test_program_leaves_the_bus_and_comes_back(self):
        _group, action = self.program()
        action.set_enabled(True)
        self.front(APP_ID)
        self.module.BackStep(self.bus)
        self.wait_for(APP_ID + " 1\n")
        self.own(False)
        self.wait_for(APP_ID + " -\n")
        action.set_enabled(False)  # started again, on its first screen
        self.own(True)
        self.wait_for(APP_ID + " 0\n")

    def test_new_front_is_looked_up(self):
        _group, action = self.program()
        action.set_enabled(True)
        self.front("firefox")
        self.module.BackStep(self.bus)
        self.wait_for("firefox -\n")  # not a bus name, not named foreign
        self.front(APP_ID)
        self.wait_for(APP_ID + " 1\n")

    def test_program_without_the_action(self):
        self.front("io.github.haltia_de.Nobody")
        self.module.BackStep(self.bus)
        self.wait_for("io.github.haltia_de.Nobody -\n")

    def test_foreign_program_always_has_the_button(self):
        with open(os.path.join(self.run_dir, "haltia", "apps.conf"), "w") as fh:
            fh.write("[calc]\napp_ids = galculator Galculator\nback = none\n")
        self.front("galculator")
        self.module.BackStep(self.bus)
        self.wait_for("galculator 0\n")


if __name__ == "__main__":
    unittest.main()
