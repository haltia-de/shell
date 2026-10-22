# SPDX-License-Identifier: GPL-2.0
"""haltia-ask close-front: «Закрыть «…»?» is asked unless Настройки →
«Для помощника» switched it off (~/.config/haltia/close.conf, ask = no);
then «✕» closes at once. Run on a copy with fuzzel, haltia-focus and the
other helpers as stand-ins.

    python3 -m unittest discover -s tests
"""
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FOCUS = """#!/bin/sh
# Stand-in: one window until it is asked to close.
case $1 in
list) [ -e "%(dir)s/closed" ] || echo io.github.haltia_de.Text ;;
close) touch "%(dir)s/closed" ;;
esac
"""
FUZZEL = """#!/bin/sh
echo asked >>"%(dir)s/fuzzel"
cat >/dev/null
[ -e "%(dir)s/answer" ] && cat "%(dir)s/answer"
exit 0
"""


class CloseAsk(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-close-ask.")
        self.addCleanup(shutil.rmtree, self.dir)
        d = self.dir
        self.bin = os.path.join(d, "bin")
        os.makedirs(self.bin)
        os.makedirs(os.path.join(d, "run/haltia/launch"))
        os.makedirs(os.path.join(d, "home/.config/haltia"))
        with open(os.path.join(d, "run/haltia/launch/front"), "w") as fh:
            fh.write("io.github.haltia_de.Text\n")
        with open(os.path.join(d, "run/haltia/apps.conf"), "w") as fh:
            fh.write("[io.github.haltia_de.Text]\nlabel = Блокнот\n"
                     "app_ids = io.github.haltia_de.Text\n")
        for name, body in (("haltia-focus", FOCUS), ("fuzzel", FUZZEL),
                           ("haltia-press", "#!/bin/sh\nexit 0\n"),
                           ("haltia-stop", "#!/bin/sh\necho stop >>%(dir)s/stopped\n")):
            path = os.path.join(self.bin, name)
            with open(path, "w") as fh:
                fh.write(body % {"dir": d})
            os.chmod(path, 0o755)
        with open(os.path.join(ROOT, "bin/haltia-ask")) as fh:
            src = fh.read()
        src = src.replace("/usr/bin/haltia-focus", os.path.join(self.bin, "haltia-focus"))
        src = src.replace("/usr/libexec/haltia/", self.bin + "/")
        self.ask = os.path.join(d, "haltia-ask")
        with open(self.ask, "w") as fh:
            fh.write(src)

    def run_ask(self):
        env = dict(os.environ, HOME=os.path.join(self.dir, "home"),
                   XDG_RUNTIME_DIR=os.path.join(self.dir, "run"),
                   PATH=self.bin + os.pathsep + os.environ["PATH"])
        subprocess.run(["sh", self.ask, "close-front"], env=env, timeout=20, check=True)

    def asked(self):
        return os.path.exists(os.path.join(self.dir, "fuzzel"))

    def closed(self):
        return os.path.exists(os.path.join(self.dir, "closed"))

    def settings(self, text):
        with open(os.path.join(self.dir, "home/.config/haltia/close.conf"), "w") as fh:
            fh.write(text)

    def test_asks_by_default(self):
        with open(os.path.join(self.dir, "answer"), "w") as fh:
            fh.write("0\n")  # «Закрыть»
        self.run_ask()
        self.assertTrue(self.asked())
        self.assertTrue(self.closed())

    def test_cancel_closes_nothing(self):
        self.settings("[close]\nask = yes\n")
        self.run_ask()  # no answer: Отмена
        self.assertTrue(self.asked())
        self.assertFalse(self.closed())

    def test_switched_off_closes_at_once(self):
        self.settings("[close]\nask = no\n")
        self.run_ask()
        self.assertFalse(self.asked())
        self.assertTrue(self.closed())


if __name__ == "__main__":
    unittest.main()
