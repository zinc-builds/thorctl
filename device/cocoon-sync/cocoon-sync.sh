#!/system/bin/sh
# cocoon-sync: imports new ROMs into Cocoon without its review step and keeps
# multi-disc folders in a layout that survives every Cocoon rescan.
#
#   cocoon-sync.sh watch                 run forever (started at boot by Magisk)
#   cocoon-sync.sh stop                  stop a running watcher
#   cocoon-sync.sh sync                  import whatever Cocoon has detected now
#   cocoon-sync.sh normalize <platform> [--dry-run]
#   cocoon-sync.sh rescan <platform>...  normalize, then run Cocoon's rescan
#
# The watcher reacts to file changes in the ROM folders and to Cocoon's own
# discovery results (lib/watch.sh); it blocks without waking the device while
# nothing changes.

SYNC_HOME=${SYNC_HOME:-$(cd "$(dirname "$0")" && pwd)}
. "$SYNC_HOME/lib/common.sh"
. "$SYNC_HOME/lib/discs.sh"
. "$SYNC_HOME/lib/rescan.sh"
. "$SYNC_HOME/lib/watch.sh"

# Platform ids with new games in Cocoon's pending discovery snapshot.
pending_platforms() {
    sed -n 's/.*name="pending_snapshot">\(.*\)<\/string>.*/\1/p' "$DISCOVERY_PREFS" \
        | sed 's/&quot;/"/g' \
        | sed -n 's/.*"games":\[\(.*\)\].*/\1/p' \
        | grep -o '"platformId":"[^"]*"' | cut -d'"' -f4 | sort -u
}

normalize_platform() {
    mode=$(platform_mode "$1")
    [ -n "$mode" ] || return 0
    dir=$(platform_folder "$1") || die "no enabled ROM folder for platform $1"
    normalize_folder "$dir" "$mode"
}

rescan() {
    cocoon_idle || return 2
    mkdir "$SYNC_HOME/lock" 2> /dev/null || { log "another sync is running"; return 2; }
    trap 'rmdir "$SYNC_HOME/lock"' EXIT
    for p in "$@"; do normalize_platform "$p"; done
    rescan_platforms "$@"
}

sync_pending() {
    platforms=$(pending_platforms)
    [ -n "$platforms" ] || return 0
    rescan $platforms
    case $? in
        0) ;;
        2) log "new games on: $(echo $platforms) - Cocoon busy, run sync again later" ;;
        *) die "rescan failed for: $(echo $platforms)" ;;
    esac
}

PIDFILE=$SYNC_HOME/watch.pid

stop_watch() {
    [ -f "$PIDFILE" ] || return 0
    pid=$(cat "$PIDFILE")
    rm -f "$PIDFILE"
    # After a reboot the old pid may belong to an unrelated process.
    tr '\0' ' ' < "/proc/$pid/cmdline" 2> /dev/null | grep -q 'cocoon-sync.sh watch' || return 0
    pkill -P "$pid" 2> /dev/null
    kill "$pid" 2> /dev/null
    log "watch stopped (pid $pid)"
}

watch() {
    stop_watch
    echo $$ > "$PIDFILE"
    log "watch started (pid $$)"
    watch_loop
}

case "$1" in
    watch) watch ;;
    stop) stop_watch ;;
    sync) sync_pending ;;
    normalize)
        [ -n "$2" ] || die "usage: normalize <platform> [--dry-run]"
        [ "$3" = --dry-run ] && DRY_RUN=1
        normalize_platform "$2" ;;
    rescan)
        shift
        [ $# -gt 0 ] || die "usage: rescan <platform>..."
        rescan "$@" ;;
    *) sed -n '2,13p' "$0"; exit 64 ;;
esac
