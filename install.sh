#!/bin/sh
# SPDX-License-Identifier: GPL-2.0
# Install Haltia's shell into a root file system: sh install.sh [ROOT]
# (ROOT empty or / for this system). The device repository's image build
# (haltia-de/device-lenovo-b8000h, build-rootfs.sh) runs build.sh and then
# this; the Alpine package haltia-shell runs it into its pkgdir with
# HALTIA_PACKAGE=1.
#
# The shell runs programs on a tablet without a desktop: the panel
# (waybar), the home screen, the close button, the start-up curtain, the
# panel tab, the shell's own questions (fuzzel), the touch filter with its
# buzz, the on-screen keyboard (wvkbd), notifications (mako) and the GTK
# theme Haltia. It knows programs through their .desktop files (ADR 0001
# in the device repository). Its paths:
#   /usr/bin/haltia-*            what a person, a program or the device runs
#   /usr/libexec/haltia/haltia-* the shell's own parts and root helpers
#   /usr/lib/haltia-shell        Настройки' code as a module (bin/haltia-settings runs it)
#   /usr/share/haltia            configuration, icons, the panel
#   /etc/haltia                  touchguard.conf (and the device's files)
# Until 3.0 the old names stay as symlinks: /usr/bin/b8k-* and
# /usr/sbin/b8k-* (programs, the device's scripts and doas rules call
# them), the few /usr/local paths older images name (their session loop,
# doas rules and scripts), /usr/share/b8k/* file by file, /etc/b8k -> /etc/haltia (made by
# haltia-upgrade), and the GTK themes b8k, b8k-cards and b8k-galculator.
#
# The C parts come prebuilt from build.sh: TOOLS ($WORK/tools) and WVKBD
# ($WORK/out/wvkbd-b8k), WORK being the build's work folder (/opt/b8000h
# by default); a part not built is left out with a warning. The compositor
# and how the session starts are the device's.
#
# HALTIA_DOAS (B8K_DOAS until 3.0) chooses the doas rules written to
# /etc/doas.d/z-haltia-shell.conf: all (the default: the power menu, the
# touch settings and a root terminal without a password), shell (the same
# without the root terminal, which then asks for the password) or none (no
# file: the device's package decides; the power menu then goes through
# logind).
set -eu
root=${1:-}
root=${root%/}
here=$(cd "$(dirname "$0")" && pwd)
WORK=${WORK:-/opt/b8000h}
TOOLS=${TOOLS:-$WORK/tools}
WVKBD=${WVKBD:-$WORK/out/wvkbd-b8k}
HALTIA_DOAS=${HALTIA_DOAS:-${B8K_DOAS:-all}}
HALTIA_PACKAGE=${HALTIA_PACKAGE:-}
case $HALTIA_DOAS in
all | shell | none) ;;
*) echo "haltia-shell: HALTIA_DOAS must be all, shell or none" >&2; exit 2 ;;
esac
bin=$root/usr/bin
lib=$root/usr/libexec/haltia
share=$root/usr/share/haltia
install -d -m 755 "$bin" "$lib" "$share" "$root/etc/haltia" "$root/etc/local.d"

for f in "$here"/bin/*; do
	install -m 755 "$f" "$bin/${f##*/}"
done
# Python never caches the script it is started by, and Настройки' code is a
# big one: it goes in as a module of the package's own folder,
# /usr/lib/haltia-shell (compiled there with the rest by the package build),
# and /usr/bin/haltia-settings is a stub that runs it with the same sys.argv
# (haltia-stop and others match `python3 /usr/bin/haltia-settings`). Only
# Настройки: haltia-sleep restarts itself by its own path and others load
# their peers by path as modules.
rm -rf "$root/usr/lib/haltia-shell"
install -D -m 644 "$here/bin/haltia-settings" "$root/usr/lib/haltia-shell/haltia_settings_main.py"
cat >"$bin/haltia-settings" <<'EOF'
#!/usr/bin/env python3
# The code is /usr/lib/haltia-shell/haltia_settings_main.py, run as a module so Python loads it compiled.
import runpy
import sys
sys.path.insert(0, "/usr/lib/haltia-shell")
runpy.run_module("haltia_settings_main", run_name="__main__", alter_sys=False)
EOF
chmod 755 "$bin/haltia-settings"
for f in "$here"/libexec/*; do
	install -m 755 "$f" "$lib/${f##*/}"
done
for f in apps.conf panel fuzzel-ask.ini foot.ini phoc.ini mako.conf gtk-4.0.css; do
	install -m 644 "$here/share/$f" "$share/$f"
done
install -m 644 "$here"/share/icons/* "$share/"
# Which xdg-desktop-portal backends Haltia's desktop uses.
install -D -m 644 "$here/share/haltia-portals.conf" "$root/usr/share/xdg-desktop-portal/haltia-portals.conf"
# What the shell is and what changed in each release (AppStream; haltia-update
# shows a coming release's notes from the new package's copy).
install -D -m 644 "$here/data/io.github.haltia_de.Shell.metainfo.xml" \
	"$root/usr/share/metainfo/io.github.haltia_de.Shell.metainfo.xml"
# The session for display managers (tinydm, greetd): haltia-wayland-session.
install -D -m 644 "$here/share/haltia.desktop" "$root/usr/share/wayland-sessions/haltia.desktop"
install -D -m 644 "$here/share/io.github.haltia_de.Settings.desktop" \
	"$root/usr/share/applications/io.github.haltia_de.Settings.desktop"
# Настройки set the date, time and zone (timedated) without a password.
install -D -m 644 "$here/share/polkit/50-haltia.rules" "$root/usr/share/polkit-1/rules.d/50-haltia.rules"
install -D -m 644 "$here/share/io.github.haltia_de.TouchSettings.desktop" \
	"$root/usr/share/applications/io.github.haltia_de.TouchSettings.desktop"
# The panel's configuration in the shell's folder (/etc/xdg/waybar is the
# waybar package's own).
install -D -m 644 "$here/waybar/config" "$share/waybar/config"
install -D -m 644 "$here/waybar/style.css" "$share/waybar/style.css"
for t in "$here"/themes/*; do
	install -D -m 644 "$t/gtk-3.0/gtk.css" "$root/usr/share/themes/${t##*/}/gtk-3.0/gtk.css"
done
# The old theme names (GTK_THEME, a program's env= or gsettings may name
# them) import the new themes until 3.0.
for t in b8k:Haltia b8k-cards:Haltia-Cards b8k-galculator:Haltia-Galculator; do
	install -d -m 755 "$root/usr/share/themes/${t%%:*}/gtk-3.0"
	printf '/* The old name of the theme %s (Haltia shell 2.x). */\n@import url("/usr/share/themes/%s/gtk-3.0/gtk.css");\n' \
		"${t#*:}" "${t#*:}" >"$root/usr/share/themes/${t%%:*}/gtk-3.0/gtk.css"
done
# GTK's file chooser as the shell wants it (folders first, no size or
# type column, the folder the program names).
install -D -m 644 "$here/share/haltia-shell.gschema.override" \
	"$root/usr/share/glib-2.0/schemas/91-haltia-shell.gschema.override"
rm -f "$root/usr/share/glib-2.0/schemas/91-b8k-shell.gschema.override"
if command -v glib-compile-schemas >/dev/null && [ -z "$root" ]; then
	glib-compile-schemas /usr/share/glib-2.0/schemas
fi
install -D -m 644 "$here/share/galculator.conf" "$root/etc/skel/.config/galculator/galculator.conf"
# Not through a link of the person's (run as root on a live system, install
# -o would follow it to a root file).
cfg=$root/home/user/.config
if [ -d "$root/home/user" ] && [ ! -L "$root/home/user" ] && [ ! -L "$cfg" ] &&
	[ ! -L "$cfg/galculator" ] && [ ! -e "$cfg/galculator/galculator.conf" ] &&
	[ ! -L "$cfg/galculator/galculator.conf" ]; then
	install -d -m 755 -o 1000 -g 1000 "$root/home/user/.config/galculator"
	install -m 644 -o 1000 -g 1000 "$here/share/galculator.conf" \
		"$root/home/user/.config/galculator/galculator.conf"
fi

# The C parts.
part() { # name destination
	if [ -x "$TOOLS/$1" ]; then
		install -m 755 "$TOOLS/$1" "$2/$1"
	else
		echo "haltia-shell: $1 not built (build.sh), left out" >&2
	fi
}
part haltia-session "$bin"
for t in haltia-press haltia-splash haltia-close haltia-home haltia-tab; do
	part "$t" "$lib"
done
if [ -x "$WVKBD" ]; then
	install -m 755 "$WVKBD" "$lib/haltia-wvkbd"
else
	echo "haltia-shell: wvkbd-b8k not built (build.sh), left out" >&2
fi
# The PAM service haltia-session opens (pam_elogind: a logind session).
install -d -m 755 "$root/etc/pam.d"
printf 'auth     sufficient pam_permit.so\naccount  sufficient pam_permit.so\nsession  include    base-session\n' \
	>"$root/etc/pam.d/haltia-session"

# The touch filter, on from the first boot; settings in
# /etc/haltia/touchguard.conf. A package leaves the runlevel to its
# post-install and post-upgrade (haltia-upgrade), so that one who turned the
# filter off keeps it off. Without a package the runlevel link is made only
# by the first install (no service yet) and never where the device says
# touchguard=no in /etc/haltia/device.conf (a screen that brings its own
# answers, such as the Tab P11's): installing again must not turn on a
# filter that someone or the device left off.
if [ -x "$TOOLS/haltia-touchguard" ]; then
	first_filter=
	[ -e "$root/etc/init.d/haltia-touchguard" ] || first_filter=yes
	install -m 755 "$TOOLS/haltia-touchguard" "$lib/haltia-touchguard"
	install -D -m 755 "$here/etc/haltia-touchguard.initd" "$root/etc/init.d/haltia-touchguard"
	[ -e "$root/etc/haltia/touchguard.conf" ] || [ -e "$root/etc/b8k/touchguard.conf" ] ||
		install -m 644 "$here/etc/touchguard.conf" "$root/etc/haltia/touchguard.conf"
	# The values as shipped, for haltia-touch-settings's «Как при установке».
	install -m 644 "$here/etc/touchguard.conf" "$share/touchguard.conf"
	if [ -z "$HALTIA_PACKAGE" ] && [ -n "$first_filter" ] &&
		[ "$(sed -n 's/^[[:space:]]*touchguard[[:space:]]*=[[:space:]]*//p' \
			"$root/etc/haltia/device.conf" 2>/dev/null | tail -n 1)" != no ]; then
		install -d -m 755 "$root/etc/runlevels/default"
		ln -sf /etc/init.d/haltia-touchguard "$root/etc/runlevels/default/haltia-touchguard"
	fi
else
	echo "haltia-shell: haltia-touchguard not built (build.sh), left out" >&2
fi

# The power key: the screen off and on, the power menu, sleep after 30 s
# with the screen off (haltia-sleep runs the device's suspend hook, if
# any). elogind's default would power the tablet off.
cat >"$root/etc/local.d/haltia-sleep.start" <<'EOF'
#!/bin/sh
mkdir -p /run/haltia
start-stop-daemon --start --background \
	--exec /usr/libexec/haltia/haltia-sleep-loop \
	--pidfile /run/haltia/sleep.pid --make-pidfile \
	--stdout /var/log/haltia-sleep.log --stderr /var/log/haltia-sleep.log
EOF
chmod +x "$root/etc/local.d/haltia-sleep.start"
# Updates: boots that never reach a good mark roll back (haltia-update).
printf '#!/bin/sh\n/usr/libexec/haltia/haltia-update boot >>/var/log/haltia-update.log 2>&1\n' \
	>"$root/etc/local.d/haltia-update.start"
chmod +x "$root/etc/local.d/haltia-update.start"
install -D -m 755 "$here/etc/health-session" "$root/etc/haltia/health/required.d/10-session"
install -d -m 755 "$root/etc/elogind/logind.conf.d"
printf '[Login]\nHandlePowerKey=ignore\nHandlePowerKeyLongPress=ignore\n' \
	>"$root/etc/elogind/logind.conf.d/haltia-power-key.conf"

# A segfault leaves its registers in dmesg for the reports (the package's
# post-install and post-upgrade apply it at once, the sysctl service at boot).
install -D -m 644 "$here/etc/sysctl-haltia.conf" "$root/etc/sysctl.d/90-haltia.conf"

# The panel's Wi-Fi follows NetworkManager at once.
install -d -m 755 "$root/etc/NetworkManager/dispatcher.d"
install -m 755 "$here/etc/nm-dispatcher-haltia-panel" "$root/etc/NetworkManager/dispatcher.d/90-haltia-panel"
# And its battery the charger.
install -D -m 644 "$here/etc/udev-haltia-panel.rules" "$root/usr/lib/udev/rules.d/90-haltia-panel.rules"

# The session user's commands without a password (HALTIA_DOAS): the power
# menu, the touch settings (haltia-touchguard-conf checks every value
# itself) and, with all, the root terminal (z- sorts after wheel.conf; doas
# uses the last matching rule). doas matches the path as written, so the
# old /usr/sbin/b8k-* and /usr/local/sbin/b8k-* names are allowed as well
# until 3.0.
install -d -m 755 "$root/etc/doas.d"
if [ "$HALTIA_DOAS" = none ]; then
	rm -f "$root/etc/doas.d/z-haltia-shell.conf"
else
	for p in /usr/libexec/haltia/haltia- /usr/sbin/b8k- /usr/local/sbin/b8k-; do
		echo "permit nopass user cmd ${p}poweroff args off"
		echo "permit nopass user cmd ${p}poweroff args reboot"
		echo "permit nopass user cmd ${p}touchguard-conf"
		if [ "$p" = /usr/libexec/haltia/haltia- ]; then
			echo "permit nopass user cmd ${p}update"
			# Reading what only root may (dmesg, /var/log, pstore) for
			# haltia-report: these two words only.
			# nolog: the watcher would put a syslog line into
			# every report.
			echo "permit nopass nolog user cmd ${p}report-root args scan"
			echo "permit nopass nolog user cmd ${p}report-root args sections"
		fi
		if [ "$HALTIA_DOAS" = all ]; then
			echo "permit nopass user cmd ${p}rootsh"
		fi
	done >"$root/etc/doas.d/z-haltia-shell.conf"
fi

# The old names (shell 1.x) as symlinks to the new ones, until 3.0.
old() { # old-path new-path
	[ -e "$root$2" ] || return 0
	install -d -m 755 "$root${1%/*}"
	rm -rf "$root$1"
	ln -s "$2" "$root$1"
}
for n in apps ask brightness focus launch launcher panel-signal rotate session term; do
	old "/usr/bin/b8k-$n" "/usr/bin/haltia-$n"
done
old /usr/bin/b8k-touchguard-setup /usr/bin/haltia-touch-settings
for n in badges clock close home keyboard meter press splash tab volume; do
	old "/usr/bin/b8k-$n" "/usr/libexec/haltia/haltia-$n"
done
old /usr/bin/wvkbd-b8k /usr/libexec/haltia/haltia-wvkbd
old /usr/sbin/b8k-panel-signal /usr/bin/haltia-panel-signal
for n in poweroff rootsh sleep-loop touchguard touchguard-conf; do
	old "/usr/sbin/b8k-$n" "/usr/libexec/haltia/haltia-$n"
done
old /usr/sbin/b8k-sleep.py /usr/libexec/haltia/haltia-sleep
# What the B8000-H images up to v1.1.0 name in /usr/local: their desktop.start
# (a session loop read at boot keeps the old text), z-b8k-power.conf and
# the device's scripts.
old /usr/local/bin/b8k-session /usr/bin/haltia-session
old /usr/local/bin/b8k-launcher /usr/bin/haltia-launcher
old /usr/local/share/b8k/phoc.ini /usr/share/haltia/phoc.ini
for n in rootsh poweroff touchguard-conf; do
	old "/usr/local/sbin/b8k-$n" "/usr/libexec/haltia/haltia-$n"
done
old /usr/local/sbin/b8k-panel-signal /usr/bin/haltia-panel-signal
# /usr/share/b8k file by file: the device's desktop.start names phoc.ini.
for f in "$share"/* "$share"/waybar/*; do
	[ -f "$f" ] || continue
	old "/usr/share/b8k${f#"$share"}" "/usr/share/haltia${f#"$share"}"
done

# On a running system (not a package or an image): move /etc/b8k, the
# runlevel and the running services over at once.
if [ -z "$root" ] && [ -z "$HALTIA_PACKAGE" ]; then
	/usr/libexec/haltia/haltia-upgrade
fi
