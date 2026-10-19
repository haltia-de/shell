#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
# A test of haltia-touchguard on the tablet, as root: a made-up screen
# (uinput, "b8k-test screen") feeds a second instance of the filter
# (HALTIA_TOUCHGUARD_SCREEN), whose output reaches the session like the real
# one's, so its touches land on whatever is in front; what it hands out is
# recorded and printed frame by frame, with the filter's decisions.
#
#   [CONF=FILE] touchguard-test.py FILTER SCENARIO...   (CONF: /etc/haltia/touchguard.conf)
#
# Scenarios: tap, pinch (apart), zoom (together), slowpinch, join (the
# second finger 15 ms after the first), scroll (two fingers up), palm,
# three (three small fingers), drag (one finger up), link, wait, and
# at=X,Y (a tap there, in screen units: 2230 × 1250 for 1280 × 800 px).
import fcntl
import glob
import os
import struct
import subprocess
import sys
import threading
import time

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
BTN_TOUCH = 0x14a
ABS = dict(X=0, Y=1, PRESSURE=0x18, SLOT=0x2f, MAJOR=0x30, MX=0x35, MY=0x36,
           TOOL=0x37, TID=0x39, MPRESSURE=0x3a)
NAMES = {v: k for k, v in ABS.items()}
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_ABSBIT = 0x40045564, 0x40045565, 0x40045567
UI_SET_PROPBIT, UI_DEV_SETUP, UI_ABS_SETUP = 0x4004556E, 0x405C5503, 0x401C5504
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502

fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
fcntl.ioctl(fd, UI_SET_KEYBIT, BTN_TOUCH)
fcntl.ioctl(fd, UI_SET_EVBIT, EV_ABS)
fcntl.ioctl(fd, UI_SET_PROPBIT, 1)  # INPUT_PROP_DIRECT
for code, lo, hi in ((ABS["X"], 0, 2230), (ABS["Y"], 0, 1250), (ABS["PRESSURE"], 0, 255),
                     (ABS["SLOT"], 0, 9), (ABS["MAJOR"], 0, 15), (ABS["MX"], 0, 2230),
                     (ABS["MY"], 0, 1250), (ABS["TID"], 0, 65535), (ABS["MPRESSURE"], 0, 255)):
    fcntl.ioctl(fd, UI_SET_ABSBIT, code)
    fcntl.ioctl(fd, UI_ABS_SETUP, struct.pack("HH6i", code, 0, 0, lo, hi, 0, 0, 0))
fcntl.ioctl(fd, UI_DEV_SETUP, struct.pack("4H80sI", 0x18, 0x1, 0x1, 1, b"b8k-test screen", 0))
fcntl.ioctl(fd, UI_DEV_CREATE)
time.sleep(0.5)


def node_named(name, exclude=()):
    for path in sorted(glob.glob("/sys/class/input/event*"), key=lambda p: int(p[22:])):
        with open(path + "/device/name") as fh:
            if fh.read().strip() == name and "/dev/input/" + path[17:] not in exclude:
                yield "/dev/input/" + path[17:]


src = list(node_named("b8k-test screen"))[-1]
old_out = set(node_named("haltia-touchguard touchscreen"))
filt = subprocess.Popen([sys.argv[1], os.environ.get("CONF", "/etc/haltia/touchguard.conf")], stderr=subprocess.PIPE,
                        text=True,
                        env={"HALTIA_TOUCHGUARD_SCREEN": src, "HALTIA_TOUCHGUARD_DEBUG": "1"})
time.sleep(3)  # the session picks the new device up
out = [n for n in node_named("haltia-touchguard touchscreen") if n not in old_out][0]
rec = []
stop = False


def reader():
    ofd = os.open(out, os.O_RDONLY | os.O_NONBLOCK)
    while not stop:
        try:
            data = os.read(ofd, 16 * 64)
        except BlockingIOError:
            time.sleep(0.005)
            continue
        for i in range(0, len(data), 16):
            _s, _u, typ, code, val = struct.unpack_from("llHHi", data, i)
            rec.append((typ, code, val))


threading.Thread(target=reader, daemon=True).start()
tid = [100]


def ev(typ, code, val):
    os.write(fd, struct.pack("llHHi", 0, 0, typ, code, val))


def syn():
    ev(EV_SYN, 0, 0)


def down(slot, x, y, major=5, pressure=48):
    tid[0] += 1
    ev(EV_ABS, ABS["SLOT"], slot)
    ev(EV_ABS, ABS["TID"], tid[0])
    move(slot, x, y, major, pressure, sync=False)


def move(slot, x, y, major=5, pressure=48, sync=False):
    ev(EV_ABS, ABS["SLOT"], slot)
    ev(EV_ABS, ABS["MX"], x)
    ev(EV_ABS, ABS["MY"], y)
    ev(EV_ABS, ABS["MAJOR"], major)
    ev(EV_ABS, ABS["MPRESSURE"], pressure)
    if sync:
        syn()


def up(slot):
    ev(EV_ABS, ABS["SLOT"], slot)
    ev(EV_ABS, ABS["TID"], -1)


def ms(n):
    time.sleep(n / 1000)


CX, CY = 1220, 700  # the middle of the content, right of the panel


def pinch(spread_from, spread_to, gap_ms=80, steps=15):
    down(0, CX - spread_from, CY)
    syn()
    ms(gap_ms)
    down(1, CX + spread_from, CY)
    syn()
    for k in range(1, steps + 1):
        d = spread_from + (spread_to - spread_from) * k // steps
        move(0, CX - d, CY)
        move(1, CX + d, CY)
        syn()
        ms(25)
    up(1)
    syn()
    ms(20)
    up(0)
    syn()


def scenario(name):
    if name.startswith("at="):  # a tap at screen units: at=X,Y
        x, y = (int(v) for v in name[3:].split(","))
        down(0, x, y)
        syn()
        ms(100)
        up(0)
        syn()
    elif name == "drag":  # one finger up the settings list
        down(0, 819, 1000)
        syn()
        for k in range(1, 26):
            move(0, 819, 1000 - k * 24)
            syn()
            ms(20)
        ms(300)
        up(0)
        syn()
    elif name == "wait":
        ms(8000)
    elif name == "link":  # "Know your rights" on about:license
        down(0, 636, 550)
        syn()
        ms(100)
        up(0)
        syn()
    elif name == "tap":
        down(0, CX, CY)
        syn()
        ms(100)
        up(0)
        syn()
    elif name == "pinch":  # fingers apart: zoom in
        pinch(80, 400)
    elif name == "slowpinch":
        pinch(100, 500, gap_ms=30, steps=40)
    elif name == "zoom":   # fingers together: zoom out
        pinch(400, 80)
    elif name == "join":   # the second finger 15 ms after the first
        pinch(80, 300, gap_ms=15)
    elif name == "scroll":  # two fingers up together
        down(0, CX - 100, CY + 200)
        syn()
        ms(60)
        down(1, CX + 100, CY + 200)
        syn()
        for k in range(1, 16):
            move(0, CX - 100, CY + 200 - k * 25)
            move(1, CX + 100, CY + 200 - k * 25)
            syn()
            ms(25)
        up(0)
        up(1)
        syn()
    elif name == "palm":   # a finger, then a palm-sized contact
        down(0, CX, CY)
        syn()
        ms(80)
        down(1, CX + 300, CY + 100, major=13, pressure=130)
        syn()
        ms(80)
        up(1)
        up(0)
        syn()
    elif name == "three":  # three small fingers at once
        down(0, CX - 200, CY)
        syn()
        ms(80)
        down(1, CX, CY)
        syn()
        ms(30)
        down(2, CX + 200, CY)
        syn()
        ms(80)
        up(0)
        up(1)
        up(2)
        syn()
    ms(700)  # past palm grace and repeat


def summary(events):
    lines, frame, slot = [], [], 0
    for typ, code, val in events:
        if typ == EV_SYN:
            if frame:
                lines.append(" ".join(frame))
            frame = []
        elif typ == EV_KEY:
            frame.append("TOUCH=%d" % val)
        elif typ == EV_ABS and code == ABS["SLOT"]:
            slot = val
        elif typ == EV_ABS and code == ABS["TID"]:
            frame.append("s%d:%s" % (slot, "up" if val < 0 else "down"))
        elif typ == EV_ABS and code == ABS["TOOL"]:
            frame.append("s%d:%s" % (slot, "PALM" if val == 2 else "finger"))
        elif typ == EV_ABS and code == ABS["MX"]:
            frame.append("s%d:x%d" % (slot, val))
    return lines


try:
    for name in sys.argv[2:]:
        start = len(rec)
        scenario(name)
        lines = summary(rec[start:])
        print("== %s: %d frames" % (name, len(lines)))
        for line in lines[:6] + (["..."] + lines[-3:] if len(lines) > 9 else lines[6:]):
            print("   " + line)
finally:
    stop = True
    filt.terminate()
    _out, err = filt.communicate()
    fcntl.ioctl(fd, UI_DEV_DESTROY)
    print("== filter log")
    print(err)
