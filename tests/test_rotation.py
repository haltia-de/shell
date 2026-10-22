# SPDX-License-Identifier: GPL-2.0
"""haltia-rotate writes the output's transform to
$XDG_RUNTIME_DIR/haltia/rotation (#54): read from wlr-randr on start, one
word, replaced at once after every turn.

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RANDR = """#!/bin/sh
case "$*" in
"") cat <<'EOT'
HDMI-A-1 "monitor"
  Enabled: no
  Transform: 180
DSI-1 "(null) (null) (DSI-1)"
  Enabled: yes
  Transform: 90
  Scale: 1.000000
EOT
;;
*) exit 0 ;;
esac
"""


class Rotation(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-rotation.")
        self.addCleanup(shutil.rmtree, self.dir)
        bin_ = os.path.join(self.dir, "bin")
        os.makedirs(bin_)
        for name, body in (("wlr-randr", RANDR), ("haltia-gestures", "#!/bin/sh\nexit 0\n")):
            with open(os.path.join(bin_, name), "w") as fh:
                fh.write(body)
            os.chmod(os.path.join(bin_, name), 0o755)
        env = mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.dir,
                                           "PATH": bin_ + os.pathsep + os.environ["PATH"]})
        env.start()
        self.addCleanup(env.stop)
        path = os.path.join(ROOT, "bin/haltia-rotate")
        loader = importlib.machinery.SourceFileLoader("haltia_rotate", path)
        spec = importlib.util.spec_from_loader("haltia_rotate", loader)
        self.rot = importlib.util.module_from_spec(spec)
        loader.exec_module(self.rot)
        self.rot.log = lambda _m: None
        self.file = os.path.join(self.dir, "haltia", "rotation")
        self.assertEqual(self.rot.ROTATION, self.file)

    def read(self):
        with open(self.file) as fh:
            return fh.read()

    def test_the_output_transform_from_wlr_randr(self):
        self.assertEqual(self.rot.current_transform("DSI-1"), "90")
        self.assertEqual(self.rot.current_transform("HDMI-A-1"), "180")
        self.assertIsNone(self.rot.current_transform("eDP-1"))

    def test_written_as_one_word(self):
        self.rot.write_rotation("270")
        self.assertEqual(self.read(), "270\n")
        self.rot.write_rotation("sideways")  # not a transform: left as it was
        self.assertEqual(self.read(), "270\n")
        self.assertFalse(os.path.exists(self.file + ".new"))

    def test_a_turn_writes_it(self):
        gestures = os.path.join(self.dir, "bin", "haltia-gestures")
        with mock.patch.object(self.rot.subprocess, "call",
                               lambda args, **_k: 0 if args[0].endswith("haltia-gestures")
                               else 1):
            self.assertTrue(self.rot.turn("DSI-1", "right-up"))
        self.assertEqual(self.read(), "270\n")
        self.assertTrue(os.path.exists(gestures))


if __name__ == "__main__":
    unittest.main()
