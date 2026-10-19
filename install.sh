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
# lenovo-b8000h-linux). Its paths are /usr/{bin,sbin,share/b8k}: the
# scripts name them. /usr/local is the person's; until shell 2.0 it holds
# a symlink at each old path (/usr/local/{bin,sbin,share/b8k}), so that an
# older session start, doas rule or program still finds the shell.
#
# The C parts come prebuilt from build.sh: TOOLS ($WORK/tools) and WVKBD
# ($WORK/out/wvkbd-b8k), WORK being the build's work folder (/opt/b8000h
# by default); a part not built is left out with a warning. The compositor
# and how the session starts are the device's.
#
# B8K_DOAS chooses the doas rules written to /etc/doas.d/z-b8k-shell.conf:
# all (the default: the power menu, the touch settings and a root terminal
# without a password), shell (the same without the root terminal, which
# then asks for the password) or none (no file: the device's package
# decides; the power menu then goes through logind).
set -eu
root=${1:-}
root=${root%/}
here=$(cd "$(dirname "$0")" && pwd)
WORK=${WORK:-/opt/b8000h}
TOOLS=${TOOLS:-$WORK/tools}
WVKBD=${WVKBD:-$WORK/out/wvkbd-b8k}
B8K_DOAS=${B8K_DOAS:-all}
case $B8K_DOAS in
all | shell | none) ;;
*) echo "b8k-shell: B8K_DOAS must be all, shell or none" >&2; exit 2 ;;
esac
bin=$root/usr/bin
sbin=$root/usr/sbin
share=$root/usr/share/b8k
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
rm -rf "$root/usr/local/share/b8k/python" "$root/usr/local/share/b8k/site.svg"
# Gone with the panel's drawer (1.5.0): its handle and the sun.
for f in drawer-open.svg drawer-closed.svg brightness.svg; do
	rm -f "$share/$f" "$root/usr/local/share/b8k/$f"
done
rmdir "$root/usr/local/share/b8k/apps.d" 2>/dev/null || true
# The panel's configuration in the shell's folder (/etc/xdg/waybar is the
# waybar package's own).
install -D -m 644 "$here/waybar/config" "$share/waybar/config"
install -D -m 644 "$here/waybar/style.css" "$share/waybar/style.css"
for t in "$here"/themes/*; do
	install -D -m 644 "$t/gtk-3.0/gtk.css" "$root/usr/share/themes/${t##*/}/gtk-3.0/gtk.css"
done
# GTK's file chooser as the shell wants it (folders first, no size or
# type column, the folder the program names).
install -D -m 644 "$here/share/b8k-shell.gschema.override" \
	"$root/usr/share/glib-2.0/schemas/91-b8k-shell.gschema.override"
if command -v glib-compile-schemas >/dev/null && [ -z "$root" ]; then
	glib-compile-schemas /usr/share/glib-2.0/schemas
fi
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
	# The values as shipped, for b8k-touchguard-setup's «Как при установке».
	install -m 644 "$here/etc/touchguard.conf" "$share/touchguard.conf"
	install -d -m 755 "$root/etc/runlevels/default"
	ln -sf /etc/init.d/b8k-touchguard "$root/etc/runlevels/default/b8k-touchguard"
else
	echo "b8k-shell: b8k-touchguard not built (build.sh), left out" >&2
fi

# The power key: the screen off and on, the power menu, sleep after 30 s
# with the screen off (b8k-sleep.py runs the device's suspend hook, if
# any). elogind's default would power the tablet off.
cat >"$root/etc/local.d/b8k-sleep.start" <<'EOF'
#!/bin/sh
start-stop-daemon --start --background \
	--exec /usr/sbin/b8k-sleep-loop \
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

# The session user's commands without a password (B8K_DOAS): the power
# menu, the touch settings (b8k-touchguard-conf checks every value itself)
# and, with all, the root terminal (z- sorts after wheel.conf; doas uses
# the last matching rule). doas matches the path as written, so the old
# /usr/local/sbin paths are allowed as well until shell 2.0.
install -d -m 755 "$root/etc/doas.d"
if [ "$B8K_DOAS" = none ]; then
	rm -f "$root/etc/doas.d/z-b8k-shell.conf"
else
	for d in /usr/sbin /usr/local/sbin; do
		echo "permit nopass user cmd $d/b8k-poweroff args off"
		echo "permit nopass user cmd $d/b8k-poweroff args reboot"
		echo "permit nopass user cmd $d/b8k-touchguard-conf"
		if [ "$B8K_DOAS" = all ]; then
			echo "permit nopass user cmd $d/b8k-rootsh"
		fi
	done >"$root/etc/doas.d/z-b8k-shell.conf"
fi

# The old paths (shell 1.6 and older) as symlinks to the new ones, file by
# file, not the folders: programs' install.sh still remove their own old
# files from /usr/local/share/b8k. Removed in shell 2.0 (ADR 0004, step 4).
compat() { # new-folder old-folder
	install -d -m 755 "$root$2"
	for f in "$root$1"/*; do
		[ -f "$f" ] && [ ! -L "$f" ] || continue
		rm -rf "$root$2/${f##*/}"
		ln -s "$1/${f##*/}" "$root$2/${f##*/}"
	done
}
# Only the shell's own files in /usr/bin and /usr/sbin.
compat_names() { # new-folder old-folder name...
	new=$1 old=$2
	shift 2
	install -d -m 755 "$root$old"
	for n in "$@"; do
		[ -f "$root$new/$n" ] || continue
		rm -f "$root$old/$n"
		ln -s "$new/$n" "$root$old/$n"
	done
}
names() { for f in "$@"; do printf '%s\n' "${f##*/}"; done; }
# shellcheck disable=SC2046 # one name per word
compat_names /usr/bin /usr/local/bin $(names "$here"/bin/*) \
	b8k-press b8k-splash b8k-close b8k-home b8k-tab b8k-session wvkbd-b8k
# shellcheck disable=SC2046
compat_names /usr/sbin /usr/local/sbin $(names "$here"/sbin/*) b8k-touchguard
compat /usr/share/b8k /usr/local/share/b8k
compat /usr/share/b8k/waybar /usr/local/share/b8k/waybar
