#!/bin/sh
# Cross-build haltia-press (armv7 musl) in the
# b8000h-build:3.24 container. Output: $WORK/tools/haltia-press, which
# build-rootfs.sh installs when it is there.
set -eu
# The build's work folder: sysroots, sources, the output in tools/ and out/.
WORK=${WORK:-/opt/b8000h}
S=$WORK/sysroot-armv7
if [ ! -e $S/usr/include/linux/input.h ]; then
	mkdir -p $S/etc/apk/keys
	cp $WORK/rootfs/etc/apk/repositories $S/etc/apk/
	cp /usr/share/apk/keys/armv7/* $S/etc/apk/keys/
	apk --root $S --arch armv7 --initdb --update-cache --no-scripts \
		add musl-dev linux-headers gcc libgcc >/dev/null
fi
G=$(dirname "$(find $S/usr/lib/gcc -name crtbeginS.o | head -1)")
mkdir -p $WORK/tools
clang --target=armv7-alpine-linux-musleabihf --sysroot=$S -B"$G" -L"$G" \
	-fuse-ld=lld -O2 -Wall -Wextra -o $WORK/tools/haltia-press \
	"$(dirname "$0")/haltia-press.c"
llvm-strip $WORK/tools/haltia-press
ls -l $WORK/tools/haltia-press
