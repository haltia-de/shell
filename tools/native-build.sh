#!/bin/sh
# SPDX-License-Identifier: GPL-2.0
# Build the shell's C parts on the machine itself (the Alpine package's
# build(), in an Alpine armv7 or on the tablet): native-build.sh WVKBD OUT
# WVKBD is a wvkbd checkout at the commit wvkbd/build.sh pins (its proto/
# holds the Wayland protocols the tools build against too); OUT gets
# wvkbd-b8k and the tools. Needs cc, pkgconf, wayland-dev, pango-dev,
# cairo-dev, libxkbcommon-dev, linux-pam-dev, linux-headers.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
wvkbd=$(cd "$1" && pwd)
mkdir -p "$2"
out=$(cd "$2" && pwd)
CC=${CC:-cc}
CFLAGS=${CFLAGS:--O2}

# The keyboard: wvkbd with the b8k patches and layout.
cd "$wvkbd"
for p in "$here"/../wvkbd/*.patch; do
	patch -p1 -N <"$p" || true # applied already when run twice
done
cp "$here"/../wvkbd/layout.b8k.h "$here"/../wvkbd/config.b8k.h "$here"/../wvkbd/keymap.b8k.h .
make LAYOUT=b8k wvkbd-b8k
cp -f wvkbd-b8k "$out/wvkbd-b8k"

# The protocols the tools speak.
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
for p in wlr-layer-shell-unstable-v1 xdg-shell; do
	wayland-scanner client-header "$wvkbd/proto/$p.xml" "$work/$p-client-protocol.h"
	wayland-scanner private-code "$wvkbd/proto/$p.xml" "$work/$p-protocol.c"
done
proto="$work/wlr-layer-shell-unstable-v1-protocol.c $work/xdg-shell-protocol.c"
cd "$here"
# shellcheck disable=SC2046,SC2086 # pkg-config and the list print separate words
for t in haltia-home haltia-close haltia-splash; do
	$CC $CFLAGS -Wall -Wextra -I"$work" -o "$out/$t" "$t.c" $proto \
		$(pkg-config --cflags --libs pangocairo wayland-client) -ldl -lm
done
# shellcheck disable=SC2086
$CC $CFLAGS -Wall -Wextra -I"$work" -o "$out/haltia-tab" haltia-tab.c $proto -lwayland-client -lm
$CC $CFLAGS -Wall -Wextra -o "$out/haltia-touchguard" haltia-touchguard.c
$CC $CFLAGS -Wall -Wextra -o "$out/haltia-press" haltia-press.c
$CC $CFLAGS -Wall -o "$out/haltia-session" haltia-session.c -lpam
ls -l "$out"
