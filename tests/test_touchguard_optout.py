"""install.sh makes the touch filter's runlevel link only on a first install
and never where device.conf says touchguard=no; the service and
haltia-upgrade honour the same key (#88)."""
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = "etc/runlevels/default/haltia-touchguard"


def install(root, device_conf=None, existing_service=False):
    tools = tempfile.mkdtemp()
    fake = os.path.join(tools, "haltia-touchguard")
    with open(fake, "w") as fh:
        fh.write("#!/bin/sh\n")
    os.chmod(fake, 0o755)
    if device_conf is not None:
        os.makedirs(os.path.join(root, "etc/haltia"), exist_ok=True)
        with open(os.path.join(root, "etc/haltia/device.conf"), "w") as fh:
            fh.write(device_conf)
    if existing_service:
        os.makedirs(os.path.join(root, "etc/init.d"), exist_ok=True)
        open(os.path.join(root, "etc/init.d/haltia-touchguard"), "w").close()
    # A copy of the tree without the __pycache__ that other tests leave in
    # bin/ (install.sh installs bin/* as files).
    src = os.path.join(tempfile.mkdtemp(), "shell")
    shutil.copytree(ROOT, src, ignore=shutil.ignore_patterns("__pycache__", ".git"))
    env = dict(os.environ, TOOLS=tools, WVKBD="/nonexistent")
    env.pop("HALTIA_PACKAGE", None)
    subprocess.run(["sh", os.path.join(src, "install.sh"), root], env=env,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return os.path.lexists(os.path.join(root, LINK))


class Install(unittest.TestCase):
    def test_a_first_install_turns_the_filter_on(self):
        self.assertTrue(install(tempfile.mkdtemp()))

    def test_a_device_without_the_filter_keeps_it_off(self):
        conf = "# Tab P11\ntransform_offset=270\n touchguard = no\n"
        self.assertFalse(install(tempfile.mkdtemp(), conf))

    def test_another_device_conf_value_leaves_it_on(self):
        self.assertTrue(install(tempfile.mkdtemp(), "touchguard=yes\n"))

    def test_installing_again_does_not_turn_it_back_on(self):
        self.assertFalse(install(tempfile.mkdtemp(), existing_service=True))


class Service(unittest.TestCase):
    def test_the_service_and_the_upgrade_read_the_key(self):
        for path in ("etc/haltia-touchguard.initd", "libexec/haltia-upgrade"):
            with open(os.path.join(ROOT, path)) as fh:
                src = fh.read()
            self.assertIn("touchguard[[:space:]]*=", src, path)
            self.assertIn("/etc/haltia/device.conf", src, path)


if __name__ == "__main__":
    unittest.main()
