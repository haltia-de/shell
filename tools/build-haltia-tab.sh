#!/bin/sh
# Cross-build haltia-tab (armv7 musl) in the b8000h-build:3.24 container, with
# the sysroot and the wlr-layer-shell protocol of the keyboard build
# (wvkbd/build.sh, run by build.sh first). Output: $WORK/tools/haltia-tab,
# which build-rootfs.sh installs when it is there.
set -eu
# The build's work folder: sysroots, sources, the output in tools/ and out/.
WORK=${WORK:-/opt/b8000h}
S=$WORK/sysroot-wvkbd
PROTO=${PROTO:-$WORK/src/wvkbd/proto}
BUILD=/tmp/haltia-tab-build
if [ ! -e "$S/usr/include/wayland-client.h" ]; then
	echo "no $S: build the keyboard first (wvkbd/build.sh)" >&2
	exit 1
fi
command -v wayland-scanner >/dev/null || apk add --no-cache wayland-dev
command -v ld.lld >/dev/null || apk add --no-cache lld
rm -rf "$BUILD"
mkdir -p "$BUILD"
for p in wlr-layer-shell-unstable-v1 xdg-shell; do
	wayland-scanner client-header "$PROTO/$p.xml" "$BUILD/$p-client-protocol.h"
	wayland-scanner private-code "$PROTO/$p.xml" "$BUILD/$p-protocol.c"
done
G=$(dirname "$(find "$S/usr/lib/gcc" -name crtbeginS.o | head -1)")
mkdir -p $WORK/tools
clang --target=armv7-alpine-linux-musleabihf --sysroot="$S" -B"$G" -L"$G" \
	-fuse-ld=lld -O2 -Wall -Wextra -I"$BUILD" -o $WORK/tools/haltia-tab \
	"$(dirname "$0")/haltia-tab.c" "$BUILD/wlr-layer-shell-unstable-v1-protocol.c" \
	"$BUILD/xdg-shell-protocol.c" -lwayland-client -lm
llvm-strip $WORK/tools/haltia-tab
ls -l $WORK/tools/haltia-tab
