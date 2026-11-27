#!/bin/zsh
# armsx2-perflog.sh "ROM file name" [samples]: boot a PS2 game in ARMSX2 the way Cocoon does,
# wait for N PerfLog lines (one per 30 s; fps and EE/GS/VU/GPU load), print them with the GPU
# driver banner, then close ARMSX2. ARMSX2 writes an autosave state on exit, so save states are
# backed up first and restored afterwards. The ROM is read from Roms/PS2 on the SD card
# ($THOR_SDCARD, or the card thor-device/scripts/sdcard.sh finds).
set -e
rom=${1:?usage: armsx2-perflog.sh "Game (USA).chd" [samples]}; samples=${2:-6}
SD=$("${0:A:h}/../../thor-device/scripts/sdcard.sh")
B=/mnt/media_rw/$SD/Android/data/com.armsx2/files; L=$B/logs/emulog.txt
BK=/data/local/tmp/armsx2-perflog-sstates
enc=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "Roms/PS2/$rom")
U="content://com.android.externalstorage.documents/tree/$SD%3ARoms%2FPS2/document/$SD%3A$enc"
count() { adb shell "su -c 'grep -c PerfLog: $L 2>/dev/null'" | tr -d '\r'; }
adb shell am force-stop com.armsx2
adb shell "su -c 'rm -f $BK/* 2>/dev/null; mkdir -p $BK && cp -a $B/sstates/. $BK/'"
adb shell input keyevent KEYCODE_WAKEUP
adb shell "am start --display 0 -n com.armsx2/com.armsx2.MainActivity -a android.intent.action.VIEW -d '$U' --activity-clear-task --activity-clear-top" >/dev/null
sleep 8
until [ "$(count)" -ge "$samples" ]; do sleep 5; done
adb shell "su -c 'grep -E \"VK: GPU .|PerfLog\" $L'" | cut -c1-160
adb shell am force-stop com.armsx2
adb shell "su -c 'cp -a $BK/. $B/sstates/'"
echo "save states restored"
