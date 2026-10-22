# SPDX-License-Identifier: GPL-2.0
"""Настройки' list of system packages for «Системные компоненты», both for
an update on offer and a past one: "name old → new" lines.

    python3 -m unittest discover -s tests
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def function():
    with open(os.path.join(ROOT, "bin/haltia-settings")) as fh:
        src = fh.read()
    start = src.index("def system_versions(")
    end = src.index("\ndef ", start + 1)
    ns = {}
    exec(src[start:end], ns)
    return ns["system_versions"]


class SystemVersions(unittest.TestCase):
    def test_lines(self):
        f = function()
        self.assertEqual(f([["musl", "1.2.6-r2", "1.2.6-r3"]]),
                         [("musl 1.2.6-r2 → 1.2.6-r3", "item")])
        self.assertEqual(f([]), [("Список пакетов не сохранился.", "note")])


if __name__ == "__main__":
    unittest.main()
