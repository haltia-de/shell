# SPDX-License-Identifier: GPL-2.0
"""haltia-sleep's wake socket: the session user is heard, a stranger or a
silent client is not, and haltia-wake speaks its protocol.

    python3 -m unittest discover -s tests
"""
import os
import pwd
import shutil
import socket
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def functions():
    src = open(os.path.join(ROOT, "libexec/haltia-sleep")).read()
    start = src.index('WAKE_SOCKET = "/run/haltia/wake.sock"')
    end = src.index("def open_home_forward():")
    ns = {}
    exec("import os, pwd, socket, struct\n" + src[start:end], ns)
    return ns


class Wake(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-wake-test.")
        self.addCleanup(shutil.rmtree, self.dir)
        self.ns = functions()
        self.ns["WAKE_SOCKET"] = os.path.join(self.dir, "wake.sock")
        me = pwd.getpwuid(os.getuid()).pw_name
        self.ns["session_user"] = lambda: me
        self.sock = self.ns["open_wake_socket"]()
        self.addCleanup(self.sock.close)

    def ask(self, text):
        answer = []

        def client():
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as c:
                c.connect(self.ns["WAKE_SOCKET"])
                if text:
                    c.sendall(text)
                c.settimeout(2)
                answer.append(c.recv(16))
        t = threading.Thread(target=client)
        t.start()
        self.sock.setblocking(True)
        heard = self.ns["wake_request"](self.sock)
        t.join()
        return heard, answer[0] if answer else b""

    def test_the_session_user_is_heard(self):
        self.assertEqual(self.ask(b"wake\n"), (True, b"ok\n"))

    def test_another_word_is_not(self):
        self.assertEqual(self.ask(b"sleep\n"), (False, b"no\n"))

    def test_a_stranger_is_not(self):
        self.ns["session_user"] = lambda: "root" if os.getuid() else "nobody"
        if os.getuid() == 0:
            self.skipTest("root is always heard")
        self.assertEqual(self.ask(b"wake\n"), (False, b"no\n"))

    def test_a_silent_client_costs_little(self):
        heard, _answer = self.ask(b"")
        self.assertFalse(heard)

    def test_haltia_wake_speaks_it(self):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader(
            "haltia_wake", os.path.join(ROOT, "libexec/haltia-wake"))
        spec = importlib.util.spec_from_loader("haltia_wake", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        mod.SOCKET = self.ns["WAKE_SOCKET"]
        result = []
        t = threading.Thread(target=lambda: result.append(mod.wake()))
        t.start()
        self.sock.setblocking(True)
        self.assertTrue(self.ns["wake_request"](self.sock))
        t.join()
        self.assertEqual(result, [True])


if __name__ == "__main__":
    unittest.main()
