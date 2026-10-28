"""The touch filter's output device carries only axes with a range (#88).

The TB-J606L's NT36523W lists ABS_X, ABS_Y and ABS_PRESSURE as 0..0; the
filter copied them, libinput refused the device (min == max) and the session
got no touch. Running the filter needs root and uinput, so this checks the
source: every copied axis is range-checked, and the single-touch ones fall
back to their multitouch twins."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Axes(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "tools/haltia-touchguard.c")) as fh:
            src = fh.read()
        start = src.index("static int create_output(void)")
        self.body = src[start:src.index("\n}\n", start)]

    def test_a_copied_axis_needs_a_range(self):
        self.assertRegex(self.body, r"ai\.maximum > ai\.minimum[^;]*;\s*\n\s*\n\s*if \(!ok && mt_of\[i\]")
        self.assertIn("if (!ok)\n\t\t\tcontinue;", self.body)

    def test_single_touch_axes_take_the_multitouch_range(self):
        m = re.search(r"mt_of\[\] = \{([^}]*)\}", self.body)
        self.assertIsNotNone(m)
        twins = [w.strip() for w in m.group(1).split(",") if w.strip()]
        self.assertEqual(twins[:3], ["ABS_MT_POSITION_X", "ABS_MT_POSITION_Y", "ABS_MT_PRESSURE"])
        copy = re.search(r"copy\[\] = \{([^}]*)\}", self.body).group(1)
        self.assertEqual(len([w for w in copy.split(",") if w.strip()]), len(twins))


if __name__ == "__main__":
    unittest.main()
