#!/bin/sh
# Cross-build haltia-touchguard (armv7 musl, no libraries) in the
# b8000h-build:3.24 container, with the keyboard build's sysroot
# (wvkbd/build.sh, run by build.sh first). Output:
# $WORK/tools/haltia-touchguard, which build-rootfs.sh installs.
set -eu
# The build's work folder: sysroots, sources, the output in tools/ and out/.
WORK=${WORK:-/opt/b8000h}
S=$WORK/sysroot-wvkbd
[ -e "$S/usr/include/linux/uinput.h" ] || { echo "no $S: build the keyboard first" >&2; exit 1; }
command -v ld.lld >/dev/null || apk add --no-cache lld
G=$(dirname "$(find "$S/usr/lib/gcc" -name crtbeginS.o | head -1)")
mkdir -p $WORK/tools
clang --target=armv7-alpine-linux-musleabihf --sysroot="$S" -B"$G" -L"$G" \
	-fuse-ld=lld -O2 -Wall -Wextra -o $WORK/tools/haltia-touchguard \
	"$(dirname "$0")/haltia-touchguard.c"
llvm-strip $WORK/tools/haltia-touchguard
ls -l $WORK/tools/haltia-touchguard
