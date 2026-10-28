"""install.sh puts Настройки' code in as a module of /usr/lib/haltia-shell,
which the package build compiles, and /usr/bin/haltia-settings runs it
through runpy with sys.argv kept (Python never caches the script it is
started by)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SettingsStub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        # A copy of the tree without the __pycache__ that other tests leave
        # in bin/ (install.sh installs bin/* as files).
        src = os.path.join(tempfile.mkdtemp(), "shell")
        shutil.copytree(ROOT, src, ignore=shutil.ignore_patterns("__pycache__", ".git"))
        env = dict(os.environ, TOOLS=tempfile.mkdtemp(), WVKBD="/nonexistent")
        env.pop("HALTIA_PACKAGE", None)
        subprocess.run(["sh", os.path.join(src, "install.sh"), cls.root], env=env,
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_the_code_is_the_module(self):
        with open(os.path.join(ROOT, "bin/haltia-settings"), "rb") as fh:
            script = fh.read()
        with open(os.path.join(self.root, "usr/lib/haltia-shell/haltia_settings_main.py"),
                  "rb") as fh:
            self.assertEqual(fh.read(), script)

    def test_the_stub_runs_it_as_main_with_argv_kept(self):
        stub = os.path.join(self.root, "usr/bin/haltia-settings")
        self.assertTrue(os.access(stub, os.X_OK))
        with open(stub) as fh:
            text = fh.read()
        self.assertTrue(text.startswith("#!/usr/bin/python3\n"))
        self.assertIn('sys.path.insert(0, "/usr/lib/haltia-shell")\n', text)
        # The stub, pointed at a stand-in module in a folder of its own.
        lib = tempfile.mkdtemp()
        with open(os.path.join(lib, "haltia_settings_main.py"), "w") as fh:
            fh.write("import sys\nprint(__name__, sys.argv)\n")
        copy = os.path.join(lib, "haltia-settings")
        with open(copy, "w") as fh:
            fh.write(text.replace('"/usr/lib/haltia-shell"', repr(lib)))
        run = subprocess.run([sys.executable, copy, "--page", "network"],
                             capture_output=True, text=True, check=True)
        self.assertEqual(run.stdout, "__main__ %r\n" % [copy, "--page", "network"])

    def test_no_other_script_moves(self):
        self.assertEqual(os.listdir(os.path.join(self.root, "usr/lib/haltia-shell")),
                         ["haltia_settings_main.py"])
        with open(os.path.join(ROOT, "libexec/haltia-sleep"), "rb") as fh:
            sleep = fh.read()
        with open(os.path.join(self.root, "usr/libexec/haltia/haltia-sleep"), "rb") as fh:
            self.assertEqual(fh.read(), sleep)


if __name__ == "__main__":
    unittest.main()
