#!/bin/sh
# SPDX-License-Identifier: GPL-2.0
# Install the b8k tablet shell into a root file system: sh install.sh [ROOT]
# (ROOT empty or / for this system). The device repository's image build
# (lenovo-b8000h-linux, build-rootfs.sh) runs build.sh and then this.
#
# The shell runs programs on a tablet without a desktop: the panel
# (waybar), the home screen, the close button, the start-up curtain, the
# panel tab, the shell's own questions (fuzzel), the touch filter with its
# buzz, the on-screen keyboard (wvkbd), notifications (mako) and the GTK
# theme b8k. It knows programs through their .desktop files (ADR 0001 in
# lenovo-b8000h-linux). Its paths are /usr/local/{bin,sbin,share/b8k}: the
# scripts name them.
#
# The C parts come prebuilt from build.sh: TOOLS (/opt/b8000h/tools) and
# WVKBD (/opt/b8000h/out/wvkbd-b8k); a part not built is left out with a
# warning. The compositor and how the session starts are the device's.
set -eu
root=${1:-}
root=${root%/}
here=$(cd "$(dirname "$0")" && pwd)
TOOLS=${TOOLS:-/opt/b8000h/tools}
WVKBD=${WVKBD:-/opt/b8000h/out/wvkbd-b8k}
bin=$root/usr/local/bin
sbin=$root/usr/local/sbin
share=$root/usr/local/share/b8k
install -d -m 755 "$bin" "$sbin" "$share" "$root/etc/b8k" "$root/etc/local.d"

for f in "$here"/bin/*; do
	install -m 755 "$f" "$bin/${f##*/}"
done
for f in "$here"/sbin/*; do
	install -m 755 "$f" "$sbin/${f##*/}"
done
for f in apps.conf panel fuzzel-ask.ini foot.ini phoc.ini mako.conf; do
	install -m 644 "$here/share/$f" "$share/$f"
done
install -m 644 "$here"/share/icons/* "$share/"
# Gone with ADR 0001 step 5: b8k_ui (programs use b8k-compat), apps.d
# (programs bring .desktop files), the web-app windows' icon.
rm -rf "$share/python" "$share/site.svg"
rmdir "$share/apps.d" 2>/dev/null || true
install -d -m 755 "$root/etc/xdg/waybar"
install -m 644 "$here/waybar/config" "$root/etc/xdg/waybar/config"
install -m 644 "$here/waybar/style.css" "$root/etc/xdg/waybar/style.css"
for t in "$here"/themes/*; do
	install -D -m 644 "$t/gtk-3.0/gtk.css" "$root/usr/share/themes/${t##*/}/gtk-3.0/gtk.css"
done
install -D -m 644 "$here/share/galculator.conf" "$root/etc/skel/.config/galculator/galculator.conf"
if [ -d "$root/home/user" ] && [ ! -e "$root/home/user/.config/galculator/galculator.conf" ]; then
	install -d -m 755 -o 1000 -g 1000 "$root/home/user/.config/galculator"
	install -m 644 -o 1000 -g 1000 "$here/share/galculator.conf" \
		"$root/home/user/.config/galculator/galculator.conf"
fi

# The C parts.
part() { # name destination
	if [ -x "$TOOLS/$1" ]; then
		install -m 755 "$TOOLS/$1" "$2/$1"
	else
		echo "b8k-shell: $1 not built (build.sh), left out" >&2
	fi
}
for t in b8k-press b8k-splash b8k-close b8k-home b8k-tab b8k-session; do
	part "$t" "$bin"
done
if [ -x "$WVKBD" ]; then
	install -m 755 "$WVKBD" "$bin/wvkbd-b8k"
else
	echo "b8k-shell: wvkbd-b8k not built (build.sh), left out" >&2
fi
# The PAM service b8k-session opens (pam_elogind: a logind session).
install -d -m 755 "$root/etc/pam.d"
printf 'auth     sufficient pam_permit.so\naccount  sufficient pam_permit.so\nsession  include    base-session\n' \
	>"$root/etc/pam.d/b8k-session"

# The touch filter, on from the first boot; settings in /etc/b8k/touchguard.conf.
if [ -x "$TOOLS/b8k-touchguard" ]; then
	install -m 755 "$TOOLS/b8k-touchguard" "$sbin/b8k-touchguard"
	install -D -m 755 "$here/etc/b8k-touchguard.initd" "$root/etc/init.d/b8k-touchguard"
	[ -e "$root/etc/b8k/touchguard.conf" ] ||
		install -m 644 "$here/etc/touchguard.conf" "$root/etc/b8k/touchguard.conf"
	install -d -m 755 "$root/etc/runlevels/default"
	ln -sf /etc/init.d/b8k-touchguard "$root/etc/runlevels/default/b8k-touchguard"
else
	echo "b8k-shell: b8k-touchguard not built (build.sh), left out" >&2
fi

# The power key: the screen off and on, the power menu, sleep after 30 s
# with the screen off (b8k-sleep.py runs the device's b8k-suspend).
# elogind's default would power the tablet off.
cat >"$root/etc/local.d/b8k-sleep.start" <<'EOF'
#!/bin/sh
start-stop-daemon --start --background \
	--exec /usr/local/sbin/b8k-sleep-loop \
	--pidfile /run/b8k-sleep.pid --make-pidfile \
	--stdout /var/log/b8k-sleep.log --stderr /var/log/b8k-sleep.log
EOF
chmod +x "$root/etc/local.d/b8k-sleep.start"
install -d -m 755 "$root/etc/elogind/logind.conf.d"
printf '[Login]\nHandlePowerKey=ignore\nHandlePowerKeyLongPress=ignore\n' \
	>"$root/etc/elogind/logind.conf.d/b8k-power-key.conf"

# The panel's Wi-Fi follows NetworkManager at once.
install -d -m 755 "$root/etc/NetworkManager/dispatcher.d"
install -m 755 "$here/etc/nm-dispatcher-b8k-panel" "$root/etc/NetworkManager/dispatcher.d/90-b8k-panel"

# The session user's commands without a password: the power menu and the
# root terminal (z- sorts after wheel.conf; doas uses the last matching rule).
install -d -m 755 "$root/etc/doas.d"
cat >"$root/etc/doas.d/z-b8k-shell.conf" <<'EOF'
permit nopass user cmd /usr/local/sbin/b8k-poweroff args off
permit nopass user cmd /usr/local/sbin/b8k-poweroff args reboot
permit nopass user cmd /usr/local/sbin/b8k-rootsh
EOF
