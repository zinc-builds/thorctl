#!/bin/zsh
# sdcard.sh: print the Thor's SD-card volume id (the 1234-ABCD in /storage/1234-ABCD).
# Uses $THOR_SDCARD when set. Otherwise asks the device for the first /storage/XXXX-XXXX entry
# (emulated and self are skipped). Exits 1 with a message when there is none.
set -e
if [ -n "$THOR_SDCARD" ]; then
    echo "$THOR_SDCARD"
    exit 0
fi
listing=$(adb shell ls /storage | tr -d '\r')
vol=$(echo "$listing" | grep -vxE 'emulated|self' | grep -m1 -xE '[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}' || true)
[ -n "$vol" ] || { echo "sdcard.sh: no SD card in /storage (found: ${listing//$'\n'/ }); insert one or set THOR_SDCARD" >&2; exit 1; }
echo "$vol"
