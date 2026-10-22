# SPDX-License-Identifier: GPL-2.0
"""«Почта для отчётов» in «Для помощника»: the address «Почта» is signed in
to, read from its config only.

    python3 -m unittest discover -s tests
"""
import configparser
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def function(conf):
    with open(os.path.join(ROOT, "bin/haltia-settings")) as fh:
        src = fh.read()
    start = src.index("def mail_address(")
    end = src.index("\n\n\n", start)
    ns = {"configparser": configparser, "MAIL_CONF": conf}
    exec(src[start:end], ns)
    return ns["mail_address"]


class MailAddress(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.conf = os.path.join(self.dir, "mail.conf")

    def test_signed_in(self):
        with open(self.conf, "w") as fh:
            fh.write("[mail]\naddress = helper@example.org\nimap = imap.example.org\n")
        self.assertEqual(function(self.conf)(), "helper@example.org")

    def test_none_or_broken(self):
        self.assertEqual(function(self.conf)(), "")
        with open(self.conf, "w") as fh:
            fh.write("not a config\n")
        self.assertEqual(function(self.conf)(), "")
        with open(self.conf, "w") as fh:
            fh.write("[mail]\nimap = imap.example.org\n")
        self.assertEqual(function(self.conf)(), "")


if __name__ == "__main__":
    unittest.main()
