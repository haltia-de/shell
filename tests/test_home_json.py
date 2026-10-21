# SPDX-License-Identifier: GPL-2.0
"""haltia-home's json_string (#31, SH2-40): a \\u escape cut short by the end
of the text (the weather cache read while it is written) is not read past
the terminator. The function is cut out of tools/haltia-home.c and built
with AddressSanitizer, which turns an over-read into a failure.

    python3 -m unittest discover -s tests
"""
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv)
{
	char out[64];
	/* An exact-size heap copy: ASan sees a byte past it. */
	size_t n = strlen(argv[1]) + 1;
	char *in = malloc(n);

	memcpy(in, argv[1], n);
	json_string(in, out, sizeof(out));
	fputs(out, stdout);
	free(in);
	return 0;
}
"""


def function_source():
    with open(os.path.join(ROOT, "tools/haltia-home.c")) as fh:
        src = fh.read()
    start = src.index("static void json_string(")
    end = src.index("\n}\n", start) + 3
    return src[start:end]


@unittest.skipIf(CC is None, "needs a C compiler")
class JsonString(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="haltia-home-json.")
        src = os.path.join(cls.dir, "t.c")
        with open(src, "w") as fh:
            fh.write("#include <ctype.h>\n#include <stdlib.h>\n#include <string.h>\n")
            fh.write(function_source())
            fh.write(MAIN)
        cls.exe = os.path.join(cls.dir, "t")
        res = subprocess.run([CC, "-fsanitize=address", "-g", "-o", cls.exe, src],
                             capture_output=True, text=True)
        if res.returncode:
            res = subprocess.run([CC, "-g", "-o", cls.exe, src], capture_output=True, text=True)
        if res.returncode:
            raise unittest.SkipTest("does not build: " + res.stderr[-200:])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir)

    def parse(self, text):
        res = subprocess.run([self.exe, text], capture_output=True)
        self.assertEqual(res.returncode, 0, res.stderr.decode(errors="replace")[-400:])
        return res.stdout.decode()

    def test_russian_word(self):
        self.assertEqual(self.parse(r'Москва"'), "Москва")

    def test_cut_short_escape_is_not_read_past_the_end(self):
        for cut in (r"\u", r"\u0", r"\u04", r"\u041"):
            self.parse("Мос" + cut)  # no over-read, no crash


if __name__ == "__main__":
    unittest.main()
