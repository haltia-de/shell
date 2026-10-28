# SPDX-License-Identifier: GPL-2.0
"""haltia-restart's list of programs on their old version: writers at once
lose nothing, and a haltia-stop that hangs leaves the rest to be seen to
(#31: SH2-21).

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    path = os.path.join(ROOT, "libexec/haltia-restart")
    loader = importlib.machinery.SourceFileLoader("haltia_restart", path)
    spec = importlib.util.spec_from_loader("haltia_restart", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


hr = load()


class Pending(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-restart-test.")
        self.addCleanup(shutil.rmtree, self.dir)
        for p in (mock.patch.object(hr, "RUN", self.dir),
                  mock.patch.object(hr, "PENDING", os.path.join(self.dir, "restart-pending")),
                  mock.patch.object(hr, "log", lambda _t: None)):
            p.start()
            self.addCleanup(p.stop)

    def test_writers_at_once_lose_nothing(self):
        threads = [threading.Thread(target=hr.remember, args=("prog%d" % i, "Программа %d" % i))
                   for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(s for s, _l, _t in hr.read_pending()),
                         sorted("prog%d" % i for i in range(30)))
        self.assertEqual(sorted(os.listdir(self.dir)), ["restart-pending", "restart-pending.lock"])

    def test_a_hanging_stop_leaves_the_rest_done(self):
        known = {"a": {"app_ids": "a.App", "label": "A"}, "b": {"app_ids": "b.App", "label": "B"}}
        stopped = []

        def run(args, **_kw):
            if args[0].endswith("haltia-stop"):
                stopped.append(args[1])
                if args[1] == "a":
                    raise subprocess.TimeoutExpired(args, 60)
            return subprocess.CompletedProcess(args, 0)
        with mock.patch.object(hr, "sections", return_value=known), \
                mock.patch.object(hr, "ids_of", return_value={"a", "b"}), \
                mock.patch.object(hr, "windows", return_value=set()), \
                mock.patch.object(hr.stop, "program", return_value={1}), \
                mock.patch.object(hr.subprocess, "run", run):
            self.assertEqual(hr.restart(["pkg"], asking=False), 0)
        self.assertEqual(stopped, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
