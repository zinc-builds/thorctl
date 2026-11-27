#!/system/bin/sh
# Magisk boot script (installed as /data/adb/service.d/cocoon-sync.sh).
SYNC_HOME=/data/adb/cocoon-sync
until [ "$(getprop sys.boot_completed)" = 1 ] && [ -d /data/data/rip.moth.cocoonshell/shared_prefs ]; do
    sleep 5
done
nohup /system/bin/sh "$SYNC_HOME/cocoon-sync.sh" watch > /dev/null 2>> "$SYNC_HOME/sync.log" &
