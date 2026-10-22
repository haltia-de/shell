# SPDX-License-Identifier: GPL-2.0
"""haltia-ask screenshot (the power menu's «Снимок экрана»): the screen goes
into the pictures folder's «Снимки экрана», then the question offers the
programs that take a PNG from others (X-Haltia-Share), and «Готово». Run on
a copy with grim, fuzzel and gio as stand-ins.

    python3 -m unittest discover -s tests
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHARE = """[Desktop Entry]
Type=Application
Name=Messages
Name[ru]=Сообщения
Exec=haltia-messenger %%U
MimeType=image/jpeg;image/png;
X-Haltia-Share=true
"""
NOT_PNG = """[Desktop Entry]
Type=Application
Name=Player
Exec=player %%U
MimeType=audio/ogg;
X-Haltia-Share=true
"""


class Screenshot(unittest.TestCase):
    def setUp(self):
        self.dir = d = tempfile.mkdtemp(prefix="haltia-shot.")
        self.addCleanup(shutil.rmtree, d)
        self.bin = os.path.join(d, "bin")
        self.home = os.path.join(d, "home")
        apps = os.path.join(d, "share/applications")
        for p in (self.bin, self.home, apps, os.path.join(d, "run/haltia")):
            os.makedirs(p)
        with open(os.path.join(apps, "io.github.haltia_de.Messenger.desktop"), "w") as fh:
            fh.write(SHARE % ())
        with open(os.path.join(apps, "player.desktop"), "w") as fh:
            fh.write(NOT_PNG % ())
        stubs = {
            "grim": '#!/bin/sh\nprintf png >"$1"\n',
            "fuzzel": '#!/bin/sh\necho "$@" >>%s/fuzzel.args\ncat >>%s/fuzzel.items\n'
                      '[ -e %s/answer ] && cat %s/answer\nexit 0\n' % (d, d, d, d),
            "gio": '#!/bin/sh\necho "$@" >%s/gio\n' % d,
            "haltia-press": "#!/bin/sh\nexit 0\n",
        }
        for name, body in stubs.items():
            path = os.path.join(self.bin, name)
            with open(path, "w") as fh:
                fh.write(body)
            os.chmod(path, 0o755)
        with open(os.path.join(ROOT, "bin/haltia-ask")) as fh:
            src = fh.read().replace("/usr/libexec/haltia/", self.bin + "/")
        self.ask = os.path.join(d, "haltia-ask")
        with open(self.ask, "w") as fh:
            fh.write(src)

    def run_ask(self, answer=None):
        if answer is not None:
            with open(os.path.join(self.dir, "answer"), "w") as fh:
                fh.write(answer + "\n")
        env = dict(os.environ, HOME=self.home, XDG_RUNTIME_DIR=os.path.join(self.dir, "run"),
                   XDG_DATA_HOME=os.path.join(self.dir, "nothing"),
                   XDG_DATA_DIRS=os.path.join(self.dir, "share"),
                   PATH=self.bin + os.pathsep + os.environ["PATH"])
        subprocess.run(["sh", self.ask, "screenshot"], env=env, timeout=20, check=True)
        time.sleep(0.2)  # gio runs in the background

    def shots(self, folder):
        path = os.path.join(self.home, folder, "Снимки экрана")
        return [os.path.join(path, n) for n in os.listdir(path)] if os.path.isdir(path) else []

    def items(self):
        with open(os.path.join(self.dir, "fuzzel.items")) as fh:
            return fh.read().splitlines()

    def test_saved_and_offered_to_messages(self):
        self.run_ask()  # no answer: Готово
        shots = self.shots("Изображения")
        self.assertEqual(len(shots), 1)
        self.assertRegex(os.path.basename(shots[0]),
                         r"^Снимок \d{4}-\d\d-\d\d \d\d-\d\d-\d\d\.png$")
        self.assertEqual(self.items(), ["Отправить: Сообщения", "Готово"])
        self.assertFalse(os.path.exists(os.path.join(self.dir, "gio")))

    def test_sending_launches_the_program_with_the_file(self):
        self.run_ask("0")
        with open(os.path.join(self.dir, "gio")) as fh:
            line = fh.read().strip()
        self.assertTrue(line.startswith("launch " + os.path.join(
            self.dir, "share/applications/io.github.haltia_de.Messenger.desktop")))
        self.assertIn(self.shots("Изображения")[0], line)

    def test_the_power_menu_offers_it_and_no_usb(self):
        with open(os.path.join(self.dir, "answer"), "w") as fh:
            fh.write("2\n")  # «Снимок экрана»
        env = dict(os.environ, HOME=self.home, XDG_RUNTIME_DIR=os.path.join(self.dir, "run"),
                   XDG_DATA_HOME=os.path.join(self.dir, "nothing"),
                   XDG_DATA_DIRS=os.path.join(self.dir, "share"),
                   PATH=self.bin + os.pathsep + os.environ["PATH"])
        subprocess.run(["sh", self.ask, "power"], env=env, timeout=20, check=True)
        first = self.items()[:4]
        self.assertEqual(first, ["Выключить", "Перезагрузить", "Снимок экрана", "Отмена"])
        self.assertFalse(any(i.startswith("USB") for i in self.items()))
        self.assertEqual(len(self.shots("Изображения")), 1)

    def test_the_pictures_folder_of_user_dirs(self):
        os.makedirs(os.path.join(self.home, ".config"))
        with open(os.path.join(self.home, ".config/user-dirs.dirs"), "w") as fh:
            fh.write('XDG_PICTURES_DIR="$HOME/Фото"\n')
        self.run_ask()
        self.assertEqual(len(self.shots("Фото")), 1)


if __name__ == "__main__":
    unittest.main()
