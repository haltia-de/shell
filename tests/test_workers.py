# SPDX-License-Identifier: GPL-2.0
"""The workers that keep slow commands off the GTK thread (#31, SH2-17,
SH2-47): haltia-brightness's Latest applies only the newest value, one
call at a time, and tells the panel once after the last; haltia-touch-
settings' Ordered runs the helper's calls in the order asked and hands
their answers back in that order. The classes are read from the scripts
alone, so neither GTK nor a layer shell is needed.

    python3 -m unittest discover -s tests
"""
import os
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(script, name):
    with open(os.path.join(ROOT, "bin", script)) as fh:
        src = fh.read()
    start = src.index("class %s:" % name)
    end = src.index("\n\n\n", start)
    ns = {"threading": threading, "sys": sys}
    exec(src[start:end], ns)
    return ns[name]


class Latest(unittest.TestCase):
    def setUp(self):
        self.Latest = load("haltia-brightness", "Latest")
        self.calls = []
        self.lock = threading.Lock()
        self.running = 0
        self.most = 0

    def work(self, value, gate=None):
        with self.lock:
            self.running += 1
            self.most = max(self.most, self.running)
        self.calls.append(value)
        if gate is not None:
            gate.wait(5)
        time.sleep(0.01)
        with self.lock:
            self.running -= 1

    def test_newest_only(self):
        gate, started = threading.Event(), threading.Event()

        def work(value):
            started.set()
            self.work(value, gate if value == 1 else None)

        after = []
        latest = self.Latest(work, after=lambda: after.append(list(self.calls)), settle=0.05)
        latest.put(1)
        self.assertTrue(started.wait(5))
        for v in (2, 3, 4):  # while 1 is still being applied
            latest.put(v)
        gate.set()
        latest.close()
        self.assertEqual(self.calls, [1, 4])
        self.assertEqual(self.most, 1)
        self.assertEqual(after, [[1, 4]])  # once, after the last value

    def test_after_waits_for_rest(self):
        after = []
        latest = self.Latest(self.work, after=lambda: after.append(time.monotonic()),
                             settle=0.3)
        latest.put(1)
        time.sleep(0.1)
        latest.put(2)  # within settle: the panel is not told in between
        time.sleep(0.6)
        self.assertEqual(len(after), 1)
        self.assertEqual(self.calls, [1, 2])
        latest.put(3)  # a new drag: a new worker, told again
        latest.close()
        self.assertEqual(len(after), 2)
        self.assertEqual(self.calls, [1, 2, 3])

    def test_no_after_and_errors(self):
        def work(value):
            self.calls.append(value)
            if value == 1:
                raise RuntimeError("logind refused")

        latest = self.Latest(work)
        latest.put(1)
        time.sleep(0.1)  # the worker ended after the error
        latest.put(2)
        latest.close()
        self.assertEqual(self.calls, [1, 2])


class Ordered(unittest.TestCase):
    def setUp(self):
        self.Ordered = load("haltia-touch-settings", "Ordered")

    def test_order(self):
        ran, answers = [], []
        posted = []
        worker = self.Ordered(post=posted.append)
        for i in range(8):
            # Later jobs are quicker: they must still wait their turn.
            def work(i=i):
                time.sleep(0.02 * (8 - i) / 8)
                ran.append(i)
                return "answer %d" % i
            worker.submit(work, answers.append if i % 2 == 0 else None)
        worker.submit(lambda: ran.append("drop"))
        self.assertTrue(worker.wait(5))
        self.assertEqual(ran, list(range(8)) + ["drop"])
        # The main loop runs what was posted, in any order and as often.
        for call in reversed(posted):
            call()
        self.assertEqual(answers, ["answer 0", "answer 2", "answer 4", "answer 6"])

    def test_one_at_a_time_and_errors(self):
        lock, running, most, answers = threading.Lock(), [0], [0], []

        def work():
            with lock:
                running[0] += 1
                most[0] = max(most[0], running[0])
            time.sleep(0.01)
            with lock:
                running[0] -= 1

        worker = self.Ordered(post=lambda f: f())
        for _ in range(5):
            worker.submit(work)
        worker.submit(lambda: 1 / 0, answers.append)
        self.assertTrue(worker.wait(5))
        self.assertEqual(most[0], 1)
        self.assertEqual(answers, ["division by zero"])
        worker.submit(lambda: "again", answers.append)  # a new worker
        self.assertTrue(worker.wait(5))
        self.assertEqual(answers, ["division by zero", "again"])


if __name__ == "__main__":
    unittest.main()
