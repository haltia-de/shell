# SPDX-License-Identifier: GPL-2.0
"""Small fixes from the second audit (#31): a program label is made safe
for waybar's JSON and Pango markup (SH2-43); Настройки' serial background
queue runs each job once with one worker (SH2-48).

    python3 -m unittest discover -s tests
"""
import json
import os
import re
import subprocess
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path)) as fh:
        return fh.read()


class Label(unittest.TestCase):
    def json_text(self, text):
        src = read("bin/haltia-launch")
        func = re.search(r"^json_text\(\) \{.*?^\}", src, re.S | re.M).group(0)
        res = subprocess.run(["sh", "-c", func + '\nprintf "%s" "$1" | json_text', "sh", text],
                             capture_output=True, text=True, check=True)
        return res.stdout

    def test_label_is_safe_json_and_markup(self):
        for label in ('Tom & "Jerry"', "a\\b", "<b>x</b>", "Блокнот"):
            out = self.json_text(label)
            parsed = json.loads('{"text":"%s"}' % out)["text"]
            self.assertNotIn("<", parsed)
            self.assertEqual(parsed.replace("&amp;", "&").replace("&lt;", "<")
                             .replace("&gt;", ">"), label)

    def test_control_characters_go(self):
        out = self.json_text("Мой\tблокнот\x01")
        self.assertEqual(json.loads('{"text":"%s"}' % out)["text"], "Мойблокнот")

    def test_the_id_fallback_is_escaped_too(self):
        src = read("bin/haltia-launch")
        self.assertEqual(src.count('label=$(printf \'%s\' "$id" | json_text)'), 2)
        self.assertNotIn('label="$id"', src)


class Queue(unittest.TestCase):
    def test_a_job_queued_as_the_last_is_taken_runs_once(self):
        """The window the race needed, made wide: the queue's pop sleeps, and
        a job is queued meanwhile. Before the fix a second worker started
        then, and the new job ran twice."""
        src = read("bin/haltia-settings")
        start = src.rfind("\n", 0, src.index("_queue = []")) + 1
        end = src.index("def spawn(")
        ns = {"threading": threading, "sys": __import__("sys"),
              "GLib": type("G", (), {"idle_add": staticmethod(lambda f, *a: f(*a))})}
        exec(src[start:end], ns)

        class SlowList(list):
            def pop(self, i=-1):
                item = super().pop(i)
                time.sleep(0.1)
                return item
        ns["_queue"] = SlowList()
        runs = []
        lock = threading.Lock()

        def job(name, takes=0.0):
            def fetch():
                with lock:
                    runs.append(name)
                time.sleep(takes)  # still running when the first worker looks again
            return fetch
        ns["background"](job("a"), serial=True)
        time.sleep(0.05)  # inside a's pop
        ns["background"](job("b", takes=0.2), serial=True)
        time.sleep(0.8)
        self.assertEqual(sorted(runs), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
