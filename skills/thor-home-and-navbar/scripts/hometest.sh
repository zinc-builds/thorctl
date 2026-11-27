#!/bin/zsh
# hometest.sh [cycles] [rom]: open a DS game, then cycle Recents/Back/Recents/Home/reopen, printing the
# resumed activity on each screen and the gesture-bar state after every step. Healthy output:
# Cocoon MainActivity + ExternalDisplayActivity after Home/Back, bar hidden except inside Recents.
# rom is a path on the SD card such as "Roms/NDS/Game (USA).nds"; default $THOR_HOMETEST_ROM, else
# the first .nds file in Roms/NDS. The SD card is $THOR_SDCARD or the one sdcard.sh finds.
set -e
cycles=${1:-3}; here=${0:A:h}
SD=$("$here/../../thor-device/scripts/sdcard.sh")
rom=${2:-$THOR_HOMETEST_ROM}
if [ -z "$rom" ]; then
    first=$(adb shell "ls /storage/$SD/Roms/NDS" | tr -d '\r' | grep -m1 -iE '\.nds$' || true)
    [ -n "$first" ] || { echo "hometest.sh: no .nds file in /storage/$SD/Roms/NDS; pass a rom or set THOR_HOMETEST_ROM" >&2; exit 1; }
    rom="Roms/NDS/$first"
fi
enc() { python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }
U="content://com.android.externalstorage.documents/tree/$SD%3A$(enc "${rom:h}")/document/$SD%3A$(enc "$rom")"
top() { adb shell "dumpsys activity activities | grep topResumedActivity" | sed 's/.*u0 //;s/}.*//;s/rip.moth.cocoonshell/cocoon/' | tr '\n' ' '; }
step() { sleep 3; echo "$1 | $(top)| $("$here/navbar.sh")"; }
echo "rom: $rom"
adb shell input keyevent KEYCODE_WAKEUP
adb shell "am start -a me.magnum.melondualds.LAUNCH_ROM -n me.magnum.melondualds/me.magnum.melonds.ui.emulator.EmulatorActivity -e uri '$U'" >/dev/null
sleep 12; step game
for i in $(seq 1 $cycles); do
    adb shell input keyevent KEYCODE_APP_SWITCH; step "recents$i"
    adb shell input keyevent KEYCODE_BACK; step "back$i"
    adb shell input keyevent KEYCODE_APP_SWITCH; step "recents$i"
    adb shell input keyevent KEYCODE_HOME; step "home$i"
    adb shell monkey -p me.magnum.melondualds -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; step "reopen$i"
done
adb shell input keyevent KEYCODE_HOME; adb shell am force-stop me.magnum.melondualds; step closed
