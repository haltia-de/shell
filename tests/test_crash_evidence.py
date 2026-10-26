# SPDX-License-Identifier: GPL-2.0
"""A segfault's evidence reaches the report (#70): the kernel's fatal-signal
dump is kept from far above dmesg's tail, the MT6628 driver's spam is
counted instead of kept, keep_syslog's mark survives clean(), haltia-keep
gives its Python daemons a faulthandler, and the package turns on
kernel.print-fatal-signals.

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, os.path.join(ROOT, path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


hr = load("haltia_report_c", "libexec/haltia-report")
root = load("haltia_report_root_c", "libexec/haltia-report-root")

FATAL = """\
[ 4100.000001] haltia-rotate: potentially unexpected fatal signal 11.
[ 4100.000002] CPU: 1 PID: 2412 Comm: haltia-rotate Not tainted 3.4.67 #1
[ 4100.000003] PC is at 0xb6f1c2a0
[ 4100.000004] pc : [<b6f1c2a0>]    lr : [<b6f1c1f8>]    psr: 60000010
[ 4100.000005] sp : be9ff8a8  ip : 00000000  fp : 00000000
[ 4100.000006] r10: 00000000  r9 : b6fd3000  r8 : 00000001"""


def fwdl(n, t=5000):
    return ["[%d.%06d] wlan_mt6628: FWDL resp: 0x%x" % (t, i, i) for i in range(n)]


def alloc(n, t=5001):
    return ["[%d.%06d] [MT6628]: buffer %d allocated" % (t, i, i) for i in range(n)]


class Dmesg(unittest.TestCase):
    def test_a_fatal_signal_far_above_the_tail_stays(self):
        before = ["[%d.0] usb 1-1: early line %d" % (i, i) for i in range(500)]
        after = ["[%d.0] usb 1-1: later line %d" % (5000 + i, i) for i in range(400)]
        out = root.dmesg_text("\n".join(before + FATAL.splitlines() + after))
        for line in FATAL.splitlines():
            self.assertIn(line, out)
        self.assertIn("later line 399", out)
        self.assertNotIn("early line 3\n", out)
        self.assertIn("[... 500 lines ...]", out)
        self.assertIn("[last 300 lines]", out)

    def test_the_driver_spam_is_counted(self):
        tail = ["[6000.0] usb 1-1: line %d" % i for i in range(10)]
        out = root.dmesg_text("\n".join(fwdl(150) + alloc(80) + FATAL.splitlines() + tail))
        self.assertEqual(out.count("FWDL resp"), 1)
        self.assertIn("[x150 such lines]", out)
        self.assertEqual(out.count("allocated"), 1)
        self.assertIn("[x80 such lines]", out)
        self.assertIn("fatal signal 11", out)
        # All of it fits the tail: nothing above it to show.
        self.assertNotIn("[last", out)

    def test_interleaved_spam_is_one_line_each(self):
        lines = []
        for a, b in zip(fwdl(50), alloc(50)):
            lines += [a, b]
        out = root.collapse(lines + ["[7000.0] kept"])
        self.assertEqual(len(out), 3)
        self.assertEqual(out[-1], "[7000.0] kept")

    def test_the_dump_survives_clean(self):
        out = hr.clean(root.dmesg_text(FATAL))
        self.assertIn("pc : [<b6f1c2a0>]", out)
        self.assertIn("fatal signal 11", out)


class HiddenMark(unittest.TestCase):
    def test_keep_syslog_mark_survives_clean(self):
        log = ("Oct 22 11:54:59 b8000h daemon.info NetworkManager[874]: <info> state up\n"
               "Oct 22 11:55:01 b8000h user.info logger: my diary entry\n")
        out = hr.clean(hr.keep_syslog(log))
        self.assertIn("[строки скрыты]", out)
        self.assertNotIn("[[текст]]", out)


class Faulthandler(unittest.TestCase):
    def test_keep_exports_it(self):
        env = dict(os.environ)
        env.pop("PYTHONFAULTHANDLER", None)
        # A clean exit at once: the keeper leaves it off and ends.
        out = subprocess.run(["sh", os.path.join(ROOT, "libexec/haltia-keep"),
                              "sh", "-c", 'echo "$PYTHONFAULTHANDLER"'],
                             env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(out.stdout.strip(), "1")


class FatalSignals(unittest.TestCase):
    def test_the_package_sets_and_applies_it(self):
        with open(os.path.join(ROOT, "etc/sysctl-haltia.conf")) as fh:
            self.assertRegex(fh.read(), r"(?m)^kernel\.print-fatal-signals = 1$")
        with open(os.path.join(ROOT, "install.sh")) as fh:
            self.assertIn('"$root/etc/sysctl.d/90-haltia.conf"', fh.read())
        for name in ("post-install", "post-upgrade"):
            with open(os.path.join(ROOT, "packaging/alpine/haltia-shell." + name)) as fh:
                self.assertIn("sysctl -q -p /etc/sysctl.d/90-haltia.conf", fh.read())


if __name__ == "__main__":
    unittest.main()
