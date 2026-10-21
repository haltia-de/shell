# SPDX-License-Identifier: GPL-2.0
"""haltia-badges' microphone(): a program recording from a real source
counts; a monitor, a corked stream and a filter's own stream (the
echo canceller the B8000-H keeps loaded) do not. pactl is a fake on PATH.

    python3 -m unittest discover -s tests
"""
import json
import os
import shutil
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCES = "0\talsa_output.speaker.monitor\n1\talsa_input.mic\n2\techo-cancel-source\n"


def functions():
    src = open(os.path.join(ROOT, "libexec/haltia-badges")).read()
    start = src.index("def short(*args):")
    end = src.index("def cameras():")
    ns = {}
    exec("import json, os, subprocess\n" + src[start:end], ns)
    return ns


class Microphone(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-rec-test.")
        self.addCleanup(shutil.rmtree, self.dir)
        self.path = os.environ.get("PATH", "")
        self.addCleanup(os.environ.__setitem__, "PATH", self.path)
        os.environ["PATH"] = self.dir + os.pathsep + self.path
        with open(os.path.join(self.dir, "sources"), "w") as fh:
            fh.write(SOURCES)
        self.ns = functions()

    def streams(self, *streams):
        with open(os.path.join(self.dir, "outputs.json"), "w") as fh:
            json.dump(list(streams), fh)
        fake = os.path.join(self.dir, "pactl")
        with open(fake, "w") as fh:
            fh.write(textwrap.dedent("""\
                #!/bin/sh
                case "$*" in
                "-f json list source-outputs") cat "%s/outputs.json" ;;
                "list short sources") cat "%s/sources" ;;
                esac
                """ % (self.dir, self.dir)))
        os.chmod(fake, 0o755)
        return self.ns["microphone"]()

    def test_a_program_recording_counts(self):
        self.assertTrue(self.streams({"source": 1, "corked": False, "properties": {}}))
        self.assertTrue(self.streams({"source": 2, "corked": False,
                                      "properties": {"media.role": "phone"}}))

    def test_the_echo_canceller_does_not(self):
        self.assertFalse(self.streams({"source": 1, "corked": True, "properties": {
            "media.name": "Echo-Cancel Source Stream", "media.role": "filter"}}))
        self.assertFalse(self.streams({"source": 1, "corked": False,
                                       "properties": {"media.role": "filter"}}))

    def test_corked_or_monitor_does_not(self):
        self.assertFalse(self.streams({"source": 1, "corked": True, "properties": {}}))
        self.assertFalse(self.streams({"source": 0, "corked": False, "properties": {}}))
        self.assertFalse(self.streams())

    def test_the_canceller_beside_a_call(self):
        self.assertTrue(self.streams(
            {"source": 1, "corked": False, "properties": {"media.role": "filter"}},
            {"source": 2, "corked": False, "properties": {"media.role": "phone"}}))


if __name__ == "__main__":
    unittest.main()
