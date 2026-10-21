# SPDX-License-Identifier: GPL-2.0
"""share/mako.conf: an incoming call's notification goes by itself a little
after the longest ring (MAX rings up to about 90 s) if the program forgets
to close it, whatever timeout the program sent; and haltia-mako config,
which sets the person's timeout, leaves that section alone.

    python3 -m unittest discover -s tests
"""
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sections(text):
    """mako's sections: the top part as "", then each [criteria] one."""
    found, name = {"": {}}, ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            name = line
            found[name] = {}
        elif "=" in line:
            key, val = line.split("=", 1)
            found[name][key] = val
    return found


class MakoConf(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "share/mako.conf")) as fh:
            self.text = fh.read()

    def test_a_forgotten_call_goes_by_itself(self):
        call = sections(self.text)["[category=call.incoming urgency=critical]"]
        self.assertEqual(call["on-notify"], "exec /usr/libexec/haltia/haltia-call")
        timeout = int(call["default-timeout"])
        self.assertGreater(timeout, 90000)  # longer than a ring
        self.assertLessEqual(timeout, 180000)  # yet not for good
        self.assertEqual(call["ignore-timeout"], "1")  # the program's 0 does not win

    def test_the_persons_timeout_leaves_the_call_alone(self):
        home = tempfile.mkdtemp(prefix="haltia-mako-test.")
        self.addCleanup(shutil.rmtree, home)
        os.makedirs(os.path.join(home, ".config/haltia"))
        with open(os.path.join(home, ".config/haltia/notifications"), "w") as fh:
            fh.write("timeout=0\n")
        script = os.path.join(ROOT, "libexec/haltia-mako")
        with open(script) as fh:
            src = fh.read().replace("/usr/share/haltia/mako.conf",
                                    os.path.join(ROOT, "share/mako.conf"))
        copy = os.path.join(home, "haltia-mako")
        with open(copy, "w") as fh:
            fh.write(src)
        env = dict(os.environ, HOME=home, XDG_RUNTIME_DIR=home)
        subprocess.run(["sh", copy, "config"], env=env, check=True)
        with open(os.path.join(home, "haltia/mako.conf")) as fh:
            made = sections(fh.read())
        self.assertEqual(made[""]["default-timeout"], "0")
        self.assertEqual(made["[category=call.incoming urgency=critical]"]["default-timeout"],
                         "100000")


if __name__ == "__main__":
    unittest.main()
