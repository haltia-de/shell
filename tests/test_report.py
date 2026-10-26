# SPDX-License-Identifier: GPL-2.0
"""haltia-report (#56): what is personal is cleaned out of fake logs, what
went wrong is noticed once and merged, a report stays under its size and
the queue under its bounds, and a report goes to «Почта» or waits.

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import tarfile
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    path = os.path.join(ROOT, "libexec/haltia-report")
    loader = importlib.machinery.SourceFileLoader("haltia_report_t", path)
    spec = importlib.util.spec_from_loader("haltia_report_t", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


hr = load()

FAKE_LOG = """\
2026-10-22 10:02:58 voice call: active
2026-10-22 10:04:23 voice quality: [{"type": "outbound-rtp", "packets-sent": 724, "bytes-sent": 49386}]
2026-10-22 10:05:00 login with phone +7 (916) 123-45-67 ok, also 89161234567 and 79161234567
2026-10-22 10:05:01 token=abcdef0123456789abcdef0123456789abcdef password: hunter2 Authorization: Bearer xyz
2026-10-22 10:05:02 connected to SSID "Дача у Тани" bssid 12:34:56:78:9a:bc ip 10.0.0.23 gw fe80::1:2:3:4
2026-10-22 10:05:03 message: Мама, я приеду в субботу text="привет, как дела?" from ivan.petrov@mail.ru
2026-10-22 10:05:04 location 55.751244, 37.618423 lat=55.7512 lon=37.6184
2026-10-22 10:05:05 Traceback (most recent call last): File "/usr/bin/haltia-messenger", line 5120, in on_send
2026-10-22 10:05:05 ValueError: bad frame 3 of 10
Oct 22 11:54:59 b8000h daemon.info NetworkManager[874]: <info>  policy: auto-activating connection 'Квартира 5G' (uuid)
Oct 22 11:54:59 b8000h daemon.info NetworkManager[874]: <info>  Config: added 'ssid' value 'Квартира 5G'
"""


class Clean(unittest.TestCase):
    def setUp(self):
        self.out = hr.clean(FAKE_LOG)

    def test_personal_things_go(self):
        for gone in ("916", "89161234567", "79161234567", "abcdef0123456789", "hunter2",
                     "xyz", "Дача у Тани", "12:34:56:78:9a:bc", "10.0.0.23", "fe80::1",
                     "приеду", "привет", "ivan.petrov", "55.751244", "37.6184", "Квартира"):
            self.assertNotIn(gone, self.out, gone)

    def test_system_facts_and_errors_stay(self):
        for kept in ("2026-10-22 10:02:58", "voice call: active", "packets-sent\": 724",
                     "bytes-sent\": 49386", "Traceback (most recent call last)",
                     "line 5120, in on_send", "ValueError: bad frame 3 of 10",
                     "NetworkManager[874]: <info>  policy: auto-activating connection"):
            self.assertIn(kept, self.out, kept)


# Lines a hostile or careless program might write: none of their personal
# parts may reach a report.
HOSTILE = [
    ("GET https://api.example.org/v1/me?access_token=ya29AbCdEf12&refresh_token=1//0gRt5x",
     ["ya29AbCdEf12", "1//0gRt5x"]),
    ('{"access_token": "ya29AbCdEf12", "refresh_token": "1//0gRt5x", "expires_in": 3600}',
     ["ya29AbCdEf12", "1//0gRt5x"]),
    ('{"lat": 55.75, "lon": 37.61, "accuracy": 20}', ["55.75", "37.61"]),
    ("open tel:89161234567", ["89161234567"]),
    ("dial 8 (495) 123-45-67 and 84951234567 and +7 495 123 45 67", ["495"]),
    ("from Иван Петров: Приходи вечером, пирог готов", ["Иван", "Приходи", "пирог"]),
    ('notify("Мама", "Купи хлеба")', ["Мама", "Купи"]),
    ("msg='see you at 7 near the station'", ["near the station"]),
    ("Authorization: OAuth y0_AgAAAAB3xyz", ["y0_AgAAAAB3xyz"]),
    ("chat_id=123456789 from_id: 987654 peer_id=55", ["123456789", "987654"]),
    ("nm-dispatcher: (2) wlan0: up for 'Дача у Тани'", ["Дача"]),
    ("iwlwifi 0000:01:00.0: connected to HomeNet-5G", ["HomeNet"]),
    ("wlan0: associated with Rostelecom_42", ["Rostelecom_42"]),
]


class Hostile(unittest.TestCase):
    def test_hostile_lines_lose_their_personal_parts(self):
        for line, gone in HOSTILE:
            for program in (False, True):
                out = hr.clean(line, program=program)
                for word in gone:
                    self.assertNotIn(word, out, (line, program))

    def test_a_program_log_keeps_only_safe_lines(self):
        log = ("2026-10-22 10:00:01 INFO messenger: connected\n"
               "Петя пишет: завтра в 10 у подъезда\n"
               "random text without any shape at all\n"
               "Traceback (most recent call last):\n"
               '  File "/usr/bin/haltia-messenger", line 12, in on_message\n'
               "    show(text)\n"
               "KeyError: 'id'\n"
               "voice call: ended\n")
        out = hr.clean(log, program=True)
        for kept in ("INFO messenger: connected", "Traceback (most recent call last)",
                     "line 12, in on_message", "KeyError", "voice call: ended"):
            self.assertIn(kept, out, kept)
        for gone in ("Петя", "подъезда", "random text"):
            self.assertNotIn(gone, out, gone)
        self.assertIn("[строки скрыты]", out)

    def test_indented_text_outside_a_traceback_goes(self):
        log = ("Traceback (most recent call last):\n"
               '  File "/usr/bin/x", line 3, in f\n'
               "    f()\n"
               "    Петя: встретимся у метро\n"
               "    secret plan for saturday\n"
               "ValueError: x\n")
        out = hr.clean(log, program=True)
        self.assertIn("    f()", out)
        for gone in ("метро", "secret plan"):
            self.assertNotIn(gone, out)


class RootText(unittest.TestCase):
    def test_the_system_log_keeps_known_services(self):
        log = ("Oct 22 11:54:59 b8000h daemon.info NetworkManager[874]: <info> state up\n"
               "Oct 22 11:55:00 b8000h user.notice someapp[12]: Петя написал про хлеб\n"
               "Oct 22 11:55:01 b8000h user.info logger: my diary entry\n"
               "Oct 22 11:55:03 b8000h user.info NetworkManager: posing as a service\n"
               "Oct 22 11:55:02 b8000h kern.warn kernel: [ 1.2] usb 1-1: new device\n")
        out = hr.keep_syslog(log)
        self.assertIn("NetworkManager[874]", out)
        self.assertIn("usb 1-1", out)
        self.assertNotIn("хлеб", out)
        self.assertNotIn("diary", out)
        self.assertNotIn("posing", out)


class Report(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="haltia-report-test.")
        self.addCleanup(shutil.rmtree, self.dir)
        p = lambda *a: os.path.join(self.dir, *a)
        os.makedirs(p("run"))
        os.makedirs(p("crashes"))
        patches = [mock.patch.multiple(hr, QUEUE=p("queue"), STATE=p("queue", "watch.json"),
                                       CONF=p("report.conf"), CRASHES=p("crashes"), RUN=p("run"),
                                       PROGRAM_LOGS=()),
                   mock.patch.object(hr, "log", lambda _m: None),
                   mock.patch.object(hr, "root_sections",
                                     lambda: {"root/dmesg.txt": "kernel: ok\n"}),
                   mock.patch.object(hr, "state_section", lambda: "state\n")]
        for x in patches:
            x.start()
            self.addCleanup(x.stop)
        self.p = p

    def settings(self, text):
        with open(self.p("report.conf"), "w") as fh:
            fh.write(text)

    def test_a_crash_record_is_noticed_once(self):
        with mock.patch.object(hr, "run", lambda *a, **k: "{}"):
            state = {}
            hr.scan(state)
            with open(self.p("crashes", "io.github.haltia_de.Text-1.json"), "w") as fh:
                json.dump({"program": "Блокнот", "traceback": "ValueError: x"}, fh)
            events = hr.scan(state)
            self.assertEqual([(e["kind"], e["program"]) for e in events], [("crash", "Блокнот")])
            self.assertEqual(hr.scan(state), [])

    def test_hangs_exits_and_root_events(self):
        with open(self.p("run", "stop.log"), "w") as fh:
            fh.write("haltia-stop: io.github.haltia_de.Paint stopped (3 processes, 1 killed)\n")
        with open(self.p("run", "volume.log"), "w") as fh:
            fh.write("haltia-keep: /usr/libexec/haltia/haltia-volume ended (1), starting it again\n"
                     "haltia-keep: /usr/libexec/haltia/haltia-volume ended (143), starting it again\n")
        root = json.dumps({"oom": ["[ 12.3] Out of memory: Killed process 431 (firefox)"],
                           "pstore": ["dmesg-ramoops-0@1792600000"], "rollback": []})
        with mock.patch.object(hr, "run", lambda *a, **k: root):
            kinds = sorted((e["kind"], e["program"]) for e in hr.scan({}))
        self.assertEqual(kinds, [("exit", "haltia-volume"), ("hang", "io.github.haltia_de.Paint"),
                                 ("oom", "firefox"), ("pstore", None)])

    def test_a_supervised_daemon_killed_by_a_signal(self):
        line = ("Oct 26 11:48:03 b8000h daemon.err supervise-daemon[849]: "
                "/usr/libexec/iio-sensor-proxy, pid 850, terminated by signal 11")
        root = json.dumps({"daemon": [line]})
        with mock.patch.object(hr, "run", lambda *a, **k: root):
            state = {}
            events = hr.scan(state, root=True)
            self.assertEqual([(e["kind"], e["program"]) for e in events],
                             [("fault", "iio-sensor-proxy")])
            self.assertIn("terminated by signal 11", events[0]["detail"])
            self.assertEqual(time.localtime(events[0]["time"])[1:6], (10, 26, 11, 48, 3))
            self.assertEqual(hr.scan(state, root=True), [])
        self.assertIn("• сбой — iio-sensor-proxy (1)", hr.summary(events, None))

    def test_a_signal_exit_of_a_session_daemon_is_a_fault(self):
        with open(self.p("run", "rotate.log"), "w") as fh:
            fh.write("haltia-keep: /usr/libexec/haltia/haltia-rotate ended (139) at 1792999683,"
                     " starting it again\n"
                     "haltia-keep: /usr/libexec/haltia/haltia-volume ended (1), starting it again\n")
        with mock.patch.object(hr, "run", lambda *a, **k: "{}"):
            events = hr.scan({})
        self.assertEqual([(e["kind"], e["program"], e["time"]) for e in events][0],
                         ("fault", "haltia-rotate", 1792999683))
        self.assertEqual(events[1]["kind"], "exit")
        self.assertIn("• сбой — haltia-rotate (1)", hr.summary(events, None))
        out = hr.crash_section(events[:1])
        self.assertTrue(out.startswith("сбой — haltia-rotate"))
        self.assertIn("ended (139)", out)

    def test_a_session_crash_asks_root_at_once(self):
        calls = []
        with open(self.p("run", "rotate.log"), "w") as fh:
            fh.write("haltia-keep: /usr/libexec/haltia/haltia-rotate ended (132), starting it again\n")
        with mock.patch.object(hr, "root_due", lambda _s: False), \
                mock.patch.object(hr, "run", lambda *a, **k: calls.append(a) or "{}"):
            hr.scan({})
        self.assertEqual(len(calls), 1)

    def test_crashes_together_are_named_in_the_summary(self):
        events = [{"kind": "fault", "program": "haltia-rotate", "time": 1000},
                  {"kind": "fault", "program": "iio-sensor-proxy", "time": 1002},
                  {"kind": "fault", "program": "polkitd", "time": 1003},
                  {"kind": "exit", "program": "haltia-volume", "time": 2000},
                  {"kind": "hang", "program": "io.github.haltia_de.Paint", "time": 1001}]
        text = hr.summary(events, None)
        self.assertIn("Одновременно упали 3 программы (haltia-rotate, iio-sensor-proxy, "
                      "polkitd)", text)
        self.assertNotIn("Одновременно", hr.summary(events[:1] + events[3:], None))

    def test_the_same_merged_with_a_count(self):
        pending = {}
        ev = {"kind": "crash", "program": "Блокнот", "time": 1}
        hr.merge(pending, [dict(ev), dict(ev, time=2)])
        self.assertEqual(list(pending.values())[0]["count"], 2)
        self.assertIn("и ещё 1", hr.subject([ev, {"kind": "oom", "program": None, "time": 1}]))

    def test_only_the_shells_own_logs_skip_the_allowlist(self):
        built = {}
        sections = {"session/messenger.log": "Петя пишет: привет\nrandom chat words\n",
                    "session/portal.log": "opened /home/user/Документы/diagnosis.pdf\n",
                    "session/home.log": "home: raised\n"}
        with mock.patch.object(hr, "session_logs", lambda: sections), \
                mock.patch.object(hr, "root_sections", dict):
            path = hr.build([{"kind": "manual", "program": None, "time": 1}])
        with open(path) as fh:
            archive = json.load(fh)["archive"]
        with tarfile.open(archive) as tar:
            for m in tar.getmembers():
                built[m.name.split("/", 1)[1]] = tar.extractfile(m).read().decode()
        self.assertNotIn("random chat", built["session/messenger.log"])
        self.assertNotIn("diagnosis", built["session/portal.log"])
        self.assertIn("home: raised", built["session/home.log"])

    def test_a_session_loop(self):
        state = {}
        for key in ("1-1", "2-2"):
            self.assertEqual(hr.session_started(state, key), [])
        self.assertEqual(hr.session_started(state, "3-3")[0]["kind"], "loop")

    def test_a_crash_detail_keeps_only_safe_lines(self):
        ev = {"kind": "crash", "program": "x", "time": 1,
              "detail": "Traceback (most recent call last):\nlocals: chat with Petya about bread\n"
                        "ValueError: x"}
        out = hr.crash_section([ev])
        self.assertIn("ValueError: x", out)
        self.assertNotIn("Petya", out)

    def test_a_restarted_watcher_is_no_loop(self):
        # haltia-keep starting the watcher again in the same session.
        state = {}
        for _ in range(5):
            self.assertEqual(hr.session_started(state, "1-1"), [])

    def test_root_is_asked_only_on_a_sign(self):
        calls = []
        vmstat = self.p("vmstat")
        with open(vmstat, "w") as fh:
            fh.write("oom_kill 0\n")
        with mock.patch.object(hr, "VMSTAT", vmstat), \
                mock.patch.object(hr, "UPDATE_LOG", self.p("nolog")), \
                mock.patch.object(hr, "run", lambda *a, **k: calls.append(a) or "{}"):
            state = {}
            hr.scan(state, root=True)
            hr.scan(state)
            hr.scan(state)
            self.assertEqual(len(calls), 1)
            with open(vmstat, "w") as fh:
                fh.write("oom_kill 1\n")
            hr.scan(state)
            self.assertEqual(len(calls), 2)
            state["root_at"] -= hr.ROOT_EVERY
            hr.scan(state)
            self.assertEqual(len(calls), 3)

    def test_odd_root_answers_do_no_harm(self):
        for answer in ("[1, 2]", '{"oom": "text"}', '{"oom": [1, null]}', "null"):
            with mock.patch.object(hr, "run", lambda *a, **k: answer):
                self.assertEqual(hr.scan({}, root=True), [])

    def test_a_program_name_is_a_safe_member(self):
        self.assertEqual(hr.member("../../etc/passwd"), "_.._etc_passwd")
        self.assertEqual(hr.member(None), "unknown")
        self.assertEqual(hr.member("io.github.haltia_de.Text"), "io.github.haltia_de.Text")

    def test_a_report_is_cleaned_and_bounded(self):
        self.settings("name=Мама\n")
        with open(self.p("run", "session.log"), "w") as fh:
            fh.write(FAKE_LOG * 3)
        with mock.patch.object(hr, "LIMIT", 4000):
            path = hr.build([{"kind": "crash", "program": "Блокнот", "time": 1, "count": 2,
                              "records": ["phone 89161234567"]}], note="звонил 89161234567")
        with open(path) as fh:
            meta = json.load(fh)
        self.assertRegex(meta["subject"], r"^Haltia: сбой «Блокнот» — Мама \(.+-[0-9a-f]{4}\)$")
        self.assertNotIn("89161234567", meta["body"])
        with tarfile.open(meta["archive"]) as tar:
            names = tar.getnames()
            data = b"".join(tar.extractfile(m).read() for m in tar.getmembers())
        self.assertTrue(any(n.endswith("/summary.txt") for n in names))
        self.assertTrue(any(n.endswith("/session/session.log") for n in names))
        self.assertLessEqual(len(data), 4000)
        self.assertNotIn(b"89161234567", data)
        self.assertNotIn(b"10.0.0.23", data)

    def test_the_queue_keeps_its_bounds(self):
        with mock.patch.object(hr, "MAX_REPORTS", 3):
            for _ in range(5):
                hr.build([{"kind": "manual", "program": None, "time": 1}])
                time.sleep(0.01)
        self.assertEqual(len(hr.queued()), 3)
        path, meta = hr.queued()[0]
        meta["time"] = 1  # very old
        hr.write_json(path, meta)
        hr.prune()
        self.assertEqual(len(hr.queued()), 2)
        self.assertFalse(os.path.exists(meta["archive"]))

    def test_sent_through_mail_or_waiting(self):
        hr.build([{"kind": "manual", "program": None, "time": 1}])
        self.assertEqual(hr.send_queued(), "not-configured")  # no address yet
        self.settings("to=helper@example.org\nauto=yes\n")
        with mock.patch.object(hr, "mail_send", lambda *a: "no-mail"):
            self.assertEqual(hr.send_queued(), "no-mail")  # Почта not there: it waits
        self.assertEqual(hr.status()["waiting"], 1)
        sent = []
        with mock.patch.object(hr, "mail_send", lambda *a: sent.append(a) or "queued"):
            self.assertEqual(hr.send_queued(), "queued")
        self.assertEqual(sent[0][0], "helper@example.org")
        self.assertTrue(sent[0][3][0].endswith(".tar.gz"))
        st = hr.status()
        self.assertEqual((st["waiting"], st["auto"], st["last"]["status"]), (0, True, "handed"))

    def test_a_draft_goes_only_when_named(self):
        self.settings("to=helper@example.org\n")
        draft = hr.build([{"kind": "manual", "program": None, "time": 1}], draft=True)
        with open(draft) as fh:
            rid = json.load(fh)["id"]
        sent = []
        with mock.patch.object(hr, "mail_send", lambda *a: sent.append(a) or "queued"):
            self.assertIsNone(hr.send_queued())  # the draft stays
            self.assertEqual(hr.status()["waiting"], 0)
            self.assertEqual(hr.send_queued(rid), "queued")
        self.assertEqual(len(sent), 1)

    def test_only_the_newest_draft_stays_and_pushes_out_nothing(self):
        for i in range(hr.MAX_REPORTS):
            hr.build([{"kind": "crash", "program": "p%d" % i, "time": i}])
        for _ in range(3):
            hr.build([{"kind": "manual", "program": None, "time": 1}], draft=True)
        kinds = [m.get("status") for _p, m in hr.queued()]
        self.assertEqual(kinds.count("draft"), 1)
        self.assertEqual(kinds.count("queued"), hr.MAX_REPORTS)

    def test_the_tablet_id_is_made_once(self):
        first = hr.device_id()
        self.assertRegex(first, r"^[\w-]+-[0-9a-f]{4}$")
        self.assertEqual(hr.device_id(), first)


class RootHelper(unittest.TestCase):
    def test_root_sections_are_parsed(self):
        out = json.dumps({"root/dmesg.txt": "line one\n=== summary.txt ===\nforged\n",
                          "summary.txt": "over the session's", "root/../etc": "up",
                          "root/update.log": "upgrade done\n"})
        with mock.patch.object(hr, "run", lambda *a, **k: out):
            found = hr.root_sections()
        # A log line cannot make a section, nor a name leave root/.
        self.assertEqual(found, {"root/dmesg.txt": "line one\n=== summary.txt ===\nforged\n",
                                 "root/update.log": "upgrade done\n"})

    def test_a_broken_answer_is_kept_aside(self):
        with mock.patch.object(hr, "run", lambda *a, **k: "doas: Operation not permitted"):
            self.assertEqual(list(hr.root_sections()), ["root/недоступно"])


if __name__ == "__main__":
    unittest.main()
