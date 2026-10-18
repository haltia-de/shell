#!/bin/sh
# SPDX-License-Identifier: GPL-2.0
# Cross-build the shell's C parts (armv7 musl) in the b8000h-build:3.24
# container: the on-screen keyboard first (wvkbd/build.sh: its sysroot,
# /opt/b8000h/sysroot-wvkbd, has cairo, pango and the Wayland protocols
# the others build against), then each tool (tools/build-*.sh). Output:
# /opt/b8000h/out/wvkbd-b8k and /opt/b8000h/tools/<tool>, which install.sh
# installs. A part that does not build is reported and left out.
set -u
here=$(cd "$(dirname "$0")" && pwd)
failed=
sh "$here/wvkbd/build.sh" || failed="$failed wvkbd"
for b in "$here"/tools/build-*.sh; do
	sh "$b" || failed="$failed $(basename "$b" .sh)"
done
if [ -n "$failed" ]; then
	echo "b8k-shell: not built:$failed" >&2
	exit 1
fi
