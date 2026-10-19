#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
# Parses waybar style sheets with GTK 3, as waybar does: a rule GTK refuses
# ends waybar, and with it the session (2.0.1: background-position).
#   check-css.py FILE...
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

failed = False
for path in sys.argv[1:]:
    errors = []
    provider = Gtk.CssProvider()
    provider.connect("parsing-error",
                     lambda _p, sec, err: errors.append((sec.get_start_line() + 1, err.message)))
    try:
        provider.load_from_path(path)
    except Exception as exc:  # GLib.Error carries the first error too
        errors.append((0, str(exc)))
    for line, message in errors:
        print("%s:%d: %s" % (path, line, message))
    failed = failed or bool(errors)
    print("%s: %s" % (path, "refused" if errors else "ok"))
sys.exit(1 if failed else 0)
