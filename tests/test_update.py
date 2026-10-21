# SPDX-License-Identifier: GPL-2.0
"""libexec/haltia-update against a fake apk (tests/fake-apk): rollbacks
leave world as it was, never lose a snapshot on failure, and health and
the lock end in bounded time.

    python3 -m unittest discover -s tests
"""
import fcntl
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load():
    path = os.path.join(ROOT, "libexec", "haltia-update")
    loader = importlib.machinery.SourceFileLoader("haltia_update", path)
    spec = importlib.util.spec_from_loader("haltia_update", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


hu = load()

REPO = {"haltia-shell": ["2.8.0-r0", "2.9.0-r0"],
        "py3-haltia-kit": ["1.0-r0", "1.1-r0"],
        "musl": ["1.2-r0", "1.3-r0"],
        "haltia-newdep": ["1.0-r0"],
        "busybox": ["1.0-r0"]}
DEPS = {"haltia-shell-2.8.0-r0": ["musl"],
        "haltia-shell-2.9.0-r0": ["musl", "haltia-newdep"]}
BEFORE = {"haltia-shell": "2.8.0-r0", "py3-haltia-kit": "1.0-r0", "musl": "1.2-r0",
          "busybox": "1.0-r0"}
WORLD = ["busybox", "haltia-shell", "py3-haltia-kit"]


class Update(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="haltia-update-test.")
        self.addCleanup(shutil.rmtree, self.tmp)
        t = lambda *p: os.path.join(self.tmp, *p)
        os.makedirs(t("bin"))
        os.symlink(os.path.join(HERE, "fake-apk"), t("bin", "apk"))
        with open(t("bin", "elogind-inhibit"), "w") as fh:
            fh.write('#!/bin/sh\nwhile [ "${1#--}" != "$1" ]; do shift; done\nexec "$@"\n')
        os.chmod(t("bin", "elogind-inhibit"), 0o755)
        os.makedirs(t("cache"))
        for name in ("haltia-shell", "py3-haltia-kit", "musl"):
            open(t("cache", "%s-%s.1234abcd.apk" % (name, BEFORE[name])), "w").close()
        self.env = {"FAKE_DB": t("installed"), "FAKE_WORLD": t("world"),
                    "FAKE_REPO": json.dumps(REPO), "FAKE_DEPS": json.dumps(DEPS),
                    "FAKE_CALLS": t("calls"), "FAKE_FAIL": "",
                    "PATH": t("bin") + os.pathsep + os.environ["PATH"]}
        self.write_db(BEFORE)
        self.write_world(WORLD)
        patches = [mock.patch.dict(os.environ, self.env),
                   mock.patch.multiple(hu, STATE=t("state"), WORLD=t("world"),
                                       INSTALLED=t("installed"), LOCK=t("lock"),
                                       CACHE=t("cache"), HEALTH=t("health"), CONF=t("conf")),
                   mock.patch.object(hu.time, "sleep", lambda _s: None),
                   mock.patch.object(hu, "enable_cache", lambda: None),
                   mock.patch.object(hu, "log", lambda _msg: None)]
        popen = subprocess.Popen

        def no_health_later(args, **kw):
            if args[:1] == ["sh"]:
                return None  # the health check a minute on
            return popen(args, **kw)
        patches.append(mock.patch.object(hu.subprocess, "Popen", no_health_later))
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def write_db(self, db):
        with open(self.env["FAKE_DB"], "w") as fh:
            for name, ver in sorted(db.items()):
                fh.write("P:%s\nV:%s\n\n" % (name, ver))

    def write_world(self, entries):
        with open(self.env["FAKE_WORLD"], "w") as fh:
            fh.write("\n".join(entries) + "\n")

    def world(self):
        with open(self.env["FAKE_WORLD"]) as fh:
            return fh.read().split()

    def calls(self):
        try:
            with open(self.env["FAKE_CALLS"]) as fh:
                return [json.loads(l) for l in fh]
        except OSError:
            return []

    def fail(self, words):
        os.environ["FAKE_FAIL"] = words

    def pending(self):
        return os.path.exists(os.path.join(hu.STATE, "pending.json"))

    def test_good_upgrade_then_rollback(self):
        self.assertEqual(hu.upgrade(), 0)
        self.assertEqual(hu.installed()["haltia-shell"], "2.9.0-r0")
        self.assertIn("haltia-newdep", hu.installed())
        self.assertTrue(self.pending())
        self.assertEqual(hu.rollback(), 0)
        self.assertEqual(hu.installed(), BEFORE)  # haltia-newdep is gone
        # The snapshot's world, Haltia's packages pinned, no checksum holds,
        # and no pin on a system package.
        self.assertEqual(self.world(), ["busybox", "haltia-shell=2.8.0-r0",
                                        "py3-haltia-kit=1.0-r0"])
        self.assertEqual(hu.held(), {"haltia-shell": "2.9.0-r0", "py3-haltia-kit": "1.1-r0"})
        self.assertFalse(self.pending())

    def test_nothing_installed_leaves_world_and_apk_alone(self):
        self.fail("upgrade")
        self.assertEqual(hu.upgrade(), 1)
        self.assertEqual(self.world(), WORLD)
        self.assertEqual(hu.installed(), BEFORE)
        self.assertFalse([c for c in self.calls() if c[:1] == ["add"]])
        self.assertEqual(hu.snapshots(), [])  # nothing of it stayed
        self.assertEqual(hu.held(), {})

    def test_half_installed_comes_back_with_world_exact(self):
        self.fail("upgrade-half")
        self.assertEqual(hu.upgrade(), 1)
        self.assertEqual(hu.installed(), BEFORE)
        self.assertEqual(self.world(), WORLD)  # no pins: only the install failed
        self.assertEqual(hu.held(), {})
        self.assertEqual(hu.snapshots(), [])

    def test_failed_upgrade_keeps_the_oldest_snapshots(self):
        for sid in ("20260101000000", "20260102000000", "20260103000000",
                    "20260104000000", "20260105000000"):
            os.makedirs(os.path.join(hu.STATE, sid))
        self.fail("upgrade")
        self.assertEqual(hu.upgrade(), 1)
        self.assertEqual(len(hu.snapshots()), 5)
        self.assertIn("20260101000000", hu.snapshots())
        self.fail("")
        self.assertEqual(hu.upgrade(), 0)
        self.assertEqual(len(hu.snapshots()), 5)
        self.assertNotIn("20260101000000", hu.snapshots())

    def test_failed_rollback_keeps_snapshot_and_pending(self):
        self.assertEqual(hu.upgrade(), 0)
        world = self.world()
        sid = hu.snapshots()[0]
        self.fail("add-files")
        self.assertEqual(hu.rollback(), 1)
        self.assertTrue(self.pending())
        self.assertEqual(hu.snapshots(), [sid])
        self.assertEqual(self.world(), world)
        self.assertEqual(hu.held(), {})
        snap = hu.read_json(os.path.join(hu.STATE, sid, "snapshot.json"), {})
        self.assertNotIn("rolled_back", snap)

    def test_files_in_then_repository_fails_leaves_no_holds(self):
        # musl's old version is neither kept nor in the repository any more.
        os.unlink(os.path.join(hu.CACHE, "musl-1.2-r0.1234abcd.apk"))
        repo = dict(REPO, musl=["1.3-r0"])
        os.environ["FAKE_REPO"] = json.dumps(repo)
        self.assertEqual(hu.upgrade(), 0)
        world = self.world()
        self.assertEqual(hu.rollback(), 1)
        self.assertFalse([e for e in self.world() if "><" in e])
        self.assertEqual(self.world(), world)
        self.assertTrue(self.pending())
        self.assertEqual(hu.held(), {})

    def test_what_the_person_added_since_stays(self):
        self.assertEqual(hu.upgrade(), 0)
        os.environ["FAKE_REPO"] = json.dumps(dict(REPO, nano=["1.0-r0"]))
        self.assertEqual(hu.apk("add", "nano").returncode, 0)
        self.assertEqual(hu.rollback(), 0)
        self.assertIn("nano", self.world())
        self.assertEqual(hu.installed().get("nano"), "1.0-r0")
        self.assertEqual(hu.installed()["haltia-shell"], "2.8.0-r0")

    def test_partial_rollback_keeps_the_rest(self):
        self.assertEqual(hu.upgrade(), 0)
        self.assertEqual(hu.rollback(names=["haltia-shell"]), 0)
        have = hu.installed()
        self.assertEqual(have["haltia-shell"], "2.8.0-r0")
        self.assertEqual(have["py3-haltia-kit"], "1.1-r0")
        self.assertEqual(self.world(), ["busybox", "haltia-shell=2.8.0-r0", "py3-haltia-kit"])
        self.assertTrue(self.pending())  # the rest of the update still waits

    def test_shell_update_waits_for_a_new_session(self):
        # SH2-1: the checks in the session that ran before the update see
        # the old code in memory pass; only a session started after it
        # (session_start() marks it, no clocks involved) counts.
        self.assertEqual(hu.upgrade(), 0)
        pending = hu.read_json(os.path.join(hu.STATE, "pending.json"), {})
        self.assertTrue(pending["session"])
        self.assertEqual(hu.health(), 0)
        self.assertTrue(self.pending())
        self.assertEqual(hu.session_start(), 0)
        self.assertEqual(hu.health(), 0)
        self.assertFalse(self.pending())

    def test_new_session_without_its_panel_rolls_back(self):
        self.assertEqual(hu.upgrade(), 0)
        os.makedirs(os.path.join(hu.HEALTH, "required.d"))
        check = os.path.join(hu.HEALTH, "required.d", "10-session")
        with open(check, "w") as fh:
            fh.write("#!/bin/sh\necho 'waybar is not running' >&2\nexit 1\n")
        os.chmod(check, 0o755)
        self.assertEqual(hu.health(), 0)  # the old session: not judged
        self.assertTrue(self.pending())
        hu.session_start()
        self.assertEqual(hu.health(), 0)  # judged, failed: rolled back
        self.assertFalse(self.pending())
        self.assertEqual(hu.installed(), BEFORE)

    def test_program_update_is_good_in_the_running_session(self):
        self.assertEqual(hu.upgrade(names=["py3-haltia-kit"]), 0)
        pending = hu.read_json(os.path.join(hu.STATE, "pending.json"), {})
        self.assertFalse(pending["session"])
        self.assertEqual(hu.health(), 0)
        self.assertFalse(self.pending())

    def test_only_packages_with_a_desktop_file_are_programs(self):
        with open(hu.INSTALLED, "w") as fh:
            fh.write("P:haltia-shell\nV:1-r0\nF:usr/share/applications\n"
                     "R:io.github.haltia_de.Settings.desktop\n\n"
                     "P:haltia-text\nV:1-r0\nF:usr/bin\nR:haltia-text\n"
                     "F:usr/share/applications\nR:io.github.haltia_de.Text.desktop\n\n"
                     "P:haltia-gst-webrtc\nV:1-r0\nF:usr/lib/gstreamer-1.0\nR:libgstwebrtc.so\n\n"
                     "P:haltia-desktop\nV:1-r0\n\n"
                     "P:pavucontrol\nV:1-r0\nF:usr/share/applications\n"
                     "R:org.pulseaudio.pavucontrol.desktop\n\n")
        self.assertEqual(hu.programs(), {"haltia-shell", "haltia-text"})
        self.assertFalse(hu.needs_session([("haltia-text", "1", "2"),
                                           ("haltia-text-pyc", "1", "2"),
                                           ("py3-haltia-kit", "1", "2")]))
        for name in ("haltia-gst-webrtc", "haltia-desktop", "haltia-shell", "libnice",
                     "pavucontrol"):
            self.assertTrue(hu.needs_session([(name, "1", "2")]), name)

    def test_log_outlives_a_closed_window(self):
        # SH2-2: Настройки closed during «Обновить всё»: the next line must
        # not end haltia-update inside apk's transaction.
        fresh = load()
        rfd, wfd = os.pipe()
        os.close(rfd)
        out = os.fdopen(wfd, "w")
        self.addCleanup(out.close)
        with mock.patch.object(fresh.sys, "stdout", out):
            fresh.log("progress 10")
            fresh.log("progress 20")

    def test_lots_of_trigger_output_does_not_hang_the_update(self):
        # SH2-19: stdout used to be read only after the progress pipe closed.
        self.fail("noisy")
        start = time.monotonic()
        self.assertEqual(hu.upgrade(), 0)
        self.assertLess(time.monotonic() - start, 30)
        self.assertEqual(hu.installed()["haltia-shell"], "2.9.0-r0")

    def test_a_catalog_cut_short_is_not_kept(self):
        # SH2-20: kept under its ETag, a broken one would be answered 304.
        import gzip
        import io
        whole = gzip.compress(b"<components/>" * 100)

        class Answer(io.BytesIO):
            headers = {"ETag": "\"abc\""}

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False
        repo = "https://example.org/alpine/v3.24"
        with mock.patch.object(hu, "repositories", lambda: [repo]), \
                mock.patch.object(hu, "STATE", hu.STATE), \
                mock.patch("urllib.request.urlopen", lambda *_a, **_k: Answer(whole[:40])):
            hu.update_catalogs()
            self.assertFalse(os.path.exists(hu.catalog_path(repo)))
        with mock.patch.object(hu, "repositories", lambda: [repo]), \
                mock.patch("urllib.request.urlopen", lambda *_a, **_k: Answer(whole)):
            hu.update_catalogs()
            self.assertTrue(os.path.exists(hu.catalog_path(repo)))
        # A small download that unpacks past the reader's bound is refused.
        os.unlink(hu.catalog_path(repo))
        bomb = gzip.compress(b"\0" * (hu.CATALOG_MAX * 8 + 1))
        self.assertLess(len(bomb), hu.CATALOG_MAX)
        with mock.patch.object(hu, "repositories", lambda: [repo]), \
                mock.patch("urllib.request.urlopen", lambda *_a, **_k: Answer(bomb)):
            hu.update_catalogs()
            self.assertFalse(os.path.exists(hu.catalog_path(repo)))

    def test_hanging_check_counts_as_failed(self):
        os.makedirs(os.path.join(hu.HEALTH, "required.d"))
        check = os.path.join(hu.HEALTH, "required.d", "hangs")
        with open(check, "w") as fh:
            fh.write("#!/bin/sh\nexec sleep 30\n")
        os.chmod(check, 0o755)
        with mock.patch.object(hu, "CHECK_TIMEOUT", 1):
            self.assertFalse(hu.run_checks("required.d"))

    def test_lock_waits_a_bounded_time(self):
        os.makedirs(os.path.dirname(hu.LOCK), exist_ok=True)
        holder = open(hu.LOCK, "a")
        self.addCleanup(holder.close)
        fcntl.flock(holder, fcntl.LOCK_EX)
        with mock.patch.object(hu.time, "sleep", time.sleep):
            start = time.monotonic()
            with open(hu.LOCK, "a") as fh:
                self.assertFalse(hu.take_lock(fh, 1))
            self.assertLess(time.monotonic() - start, 3)
        self.assertTrue(hu.busy())
        fcntl.flock(holder, fcntl.LOCK_UN)
        with open(hu.LOCK, "a") as fh:
            self.assertTrue(hu.take_lock(fh, 1))

    def test_a_look_does_not_block_another_look(self):
        os.makedirs(os.path.dirname(hu.LOCK), exist_ok=True)
        looker = open(hu.LOCK, "a")
        self.addCleanup(looker.close)
        fcntl.flock(looker, fcntl.LOCK_SH)
        self.assertFalse(hu.busy())


if __name__ == "__main__":
    unittest.main()
