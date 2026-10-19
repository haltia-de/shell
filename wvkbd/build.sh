#!/bin/sh
# Cross-build the large B8000-H keyboard (armv7 musl) in b8000h-build:3.24.
# Upstream pin is wvkbd 0.21, commit bbecd996aae5a4dc4bc32bd643d37cefa9f63752.
set -eu
# The build's work folder: sysroots, sources, the output in tools/ and out/.
WORK=${WORK:-/opt/b8000h}
UPSTREAM=${UPSTREAM:-$WORK/src/wvkbd}
PIN=bbecd996aae5a4dc4bc32bd643d37cefa9f63752
BUILD=/tmp/wvkbd-b8k-build
S=$WORK/sysroot-wvkbd
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$WORK/out/wvkbd-b8k

if [ ! -e "$S/usr/include/pango-1.0/pango/pango.h" ]; then
	mkdir -p "$S/etc/apk/keys"
	if [ -d /usr/share/apk/keys/armv7 ]; then
		cp /usr/share/apk/keys/armv7/* "$S/etc/apk/keys/"
	else
		cp $WORK/sysroot-armv7/etc/apk/keys/* "$S/etc/apk/keys/"
	fi
	cp /etc/apk/repositories "$S/etc/apk/repositories"
	apk --root "$S" --arch armv7 --initdb --update-cache --no-scripts \
		add musl-dev linux-headers gcc libgcc \
		wayland-dev pango-dev cairo-dev libxkbcommon-dev pkgconf
fi
command -v wayland-scanner >/dev/null || apk add --no-cache wayland-dev
command -v ld.lld >/dev/null || apk add --no-cache lld

rm -rf "$BUILD"
cp -a "$UPSTREAM" "$BUILD"
cd "$BUILD"
git config --global --add safe.directory "$BUILD"
git checkout -q "$PIN"
patch -p1 < "$HERE/0001-hide-key.patch"
patch -p1 < "$HERE/0002-no-cover-popup.patch"
patch -p1 < "$HERE/0003-enter-shape.patch"
patch -p1 < "$HERE/0004-shift-lock.patch"
patch -p1 < "$HERE/0005-haptic.patch"
cp "$HERE/layout.b8k.h" \
	"$HERE/config.b8k.h" \
	"$HERE/keymap.b8k.h" .

export PKG_CONFIG_SYSROOT_DIR=$S
export PKG_CONFIG_LIBDIR=$S/usr/lib/pkgconfig
export PKG_CONFIG_PATH=
G=$(dirname "$(find "$S/usr/lib/gcc" -name crtbeginS.o | head -1)")
export CC="clang --target=armv7-alpine-linux-musleabihf --sysroot=$S -B$G -L$G -fuse-ld=lld"
make LAYOUT=b8k -j4 wvkbd-b8k
mkdir -p $WORK/out
cp -f wvkbd-b8k "$OUT"
ls -l "$OUT"
