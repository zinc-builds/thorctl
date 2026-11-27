#!/bin/zsh
# fix-pref-owner.sh PACKAGE FILE: after editing a file in /data/data/PACKAGE as root, restore the
# app's uid ownership and MLS SELinux label. sed -i / printf as root leaves root:root and a bare
# "s0" label, and the app then cannot read its own prefs.
set -e
pkg=${1:?usage: fix-pref-owner.sh PACKAGE FILE}; file=${2:?usage: fix-pref-owner.sh PACKAGE FILE}
uid=$(adb shell "dumpsys package $pkg" | grep -m1 -o 'userId=[0-9]*' | cut -d= -f2)
[ -n "$uid" ] || { echo "no uid for $pkg" >&2; exit 1; }
adb shell "su -c 'ctx=\$(ls -Zd /data/data/$pkg | cut -d\" \" -f1); chown $uid:$uid \"$file\" && chcon \$ctx \"$file\" && ls -lnZ \"$file\"'"
