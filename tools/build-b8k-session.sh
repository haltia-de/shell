#!/bin/sh
# Cross-build b8k-session (armv7 musl + libpam) in the b8000h-build:3.24 container.
# Output: $WORK/tools/b8k-session (used by build-rootfs.sh).
set -eu
# The build's work folder: sysroots, sources, the output in tools/ and out/.
WORK=${WORK:-/opt/b8000h}
S=$WORK/sysroot-armv7
if [ ! -e $S/usr/include/security/pam_appl.h ]; then
	mkdir -p $S/etc/apk/keys
	cp $WORK/rootfs/etc/apk/repositories $S/etc/apk/
	cp /usr/share/apk/keys/armv7/* $S/etc/apk/keys/
	apk --root $S --arch armv7 --initdb --update-cache --no-scripts \
		add musl-dev linux-pam-dev gcc libgcc >/dev/null
fi
G=$(dirname "$(find $S/usr/lib/gcc -name crtbeginS.o | head -1)")
mkdir -p $WORK/tools
clang --target=armv7-alpine-linux-musleabihf --sysroot=$S -B"$G" -L"$G" \
	-fuse-ld=lld -O2 -Wall -o $WORK/tools/b8k-session \
	"$(dirname "$0")/b8k-session.c" -lpam
llvm-strip $WORK/tools/b8k-session
ls -l $WORK/tools/b8k-session
