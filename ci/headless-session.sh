#!/bin/sh
# SPDX-License-Identifier: GPL-2.0
# The shell's session under headless phoc (wlroots' headless backend,
# pixman rendering) on whatever Alpine this runs in, x86_64 in CI: builds
# the C parts natively, installs everything, starts phoc with b8k-launcher
# as the session user, waits for the panel and the home screen, and takes
# a screenshot. Anything tied to the B8000-H (its backlight, touchscreen,
# power key, paths of its own) shows up here as a failure or in the
# picture, not on the next tablet (ADR 0004, lenovo-b8000h-linux).
#
#   sh ci/headless-session.sh OUT        (as root, in a throwaway container)
#
# OUT gets session.png, session.log and the session's own logs.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$1"
out=$(cd "$1" && pwd)
wvkbd_pin=$(sed -n 's/^PIN=//p' "$here/wvkbd/build.sh")

apk add --no-cache build-base pkgconf git linux-headers wayland-dev wayland-protocols \
	pango-dev cairo-dev libxkbcommon-dev linux-pam-dev \
	python3 py3-gobject3 gtk+3.0 gtk-layer-shell waybar fuzzel foot mako \
	elogind doas networkmanager pulseaudio-utils grim phoc dbus dbus-x11 \
	font-dejavu adwaita-icon-theme >/dev/null

# The keyboard's source at the pinned commit, then the C parts.
git clone -q https://github.com/jjsullivan5196/wvkbd /tmp/wvkbd
git -C /tmp/wvkbd checkout -q "$wvkbd_pin"
sh "$here/tools/native-build.sh" /tmp/wvkbd /tmp/b8k-out >/dev/null
TOOLS=/tmp/b8k-out WVKBD=/tmp/b8k-out/wvkbd-b8k sh "$here/install.sh"

id user >/dev/null 2>&1 || adduser -D user
echo user >/etc/b8k/session-user
run=/tmp/xdg-user
install -d -m 700 -o user -g user "$run"
# One headless output the size of the B8000-H's screen.
cat >/tmp/phoc-ci.ini <<'INI'
[output:HEADLESS-1]
mode = 1280x800
INI

su user -s /bin/sh -c "
	export XDG_RUNTIME_DIR=$run HOME=/home/user LANG=ru_RU.UTF-8
	export WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1
	exec dbus-run-session -- phoc -C /tmp/phoc-ci.ini -E /usr/bin/b8k-launcher
" >"$out/session.log" 2>&1 &
session=$!

# The panel and the home screen, then a little time to draw. (busybox's
# pgrep -x does not match these by name; pidof does.)
ok=
for _ in $(seq 60); do
	if pidof waybar >/dev/null && pidof b8k-home >/dev/null; then
		ok=yes
		break
	fi
	kill -0 "$session" 2>/dev/null || break
	sleep 1
done
sleep 5
display=$(cd "$run" && ls wayland-[0-9] 2>/dev/null | head -1)
status=0
if [ -n "$display" ]; then
	su user -s /bin/sh -c "XDG_RUNTIME_DIR=$run WAYLAND_DISPLAY=$display grim $run/session.png" &&
		cp "$run/session.png" "$out/" || status=1
else
	echo "no Wayland display" >&2
	status=1
fi
for p in waybar b8k-home b8k-close mako; do
	if pidof "$p" >/dev/null; then
		echo "running: $p"
	else
		echo "NOT running: $p" >&2
		status=1
	fi
done
[ -n "$ok" ] || status=1
cp "$run"/*.log "$out/" 2>/dev/null || true
kill "$session" 2>/dev/null || true
exit "$status"
