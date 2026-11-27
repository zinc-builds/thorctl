# Shared paths and helpers for cocoon-sync. Sourced, not executed.

COCOON_PKG=rip.moth.cocoonshell
COCOON_DB=/data/data/$COCOON_PKG/databases/cocoon_db
COCOON_PREFS=/data/data/$COCOON_PKG/shared_prefs
DISCOVERY_PREFS=$COCOON_PREFS/rom_library_discovery.xml

SYNC_HOME=${SYNC_HOME:-/data/adb/cocoon-sync}
SQLITE=$SYNC_HOME/bin/sqlite3
MODES_CONF=$SYNC_HOME/modes.conf
LOG=$SYNC_HOME/sync.log
LOG_MAX_BYTES=262144

log() {
    if [ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt "$LOG_MAX_BYTES" ]; then
        mv "$LOG" "$LOG.1"
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"
}

die() {
    log "ERROR $*"
    echo "cocoon-sync: $*" >&2
    exit 1
}

sql() {
    "$SQLITE" -readonly -bail "$COCOON_DB" ".timeout 5000" "$1"
}

# content://…/tree/1234-ABCD%3ARoms/document/1234-ABCD%3ARoms%2FPSX -> /storage/1234-ABCD/Roms/PSX
saf_uri_to_path() {
    doc=${1##*/document/}
    [ "$doc" = "$1" ] && doc=${1##*/tree/}
    doc=$(printf '%b' "$(printf '%s' "$doc" | sed 's/%\([0-9A-Fa-f][0-9A-Fa-f]\)/\\x\1/g')")
    volume=${doc%%:*}
    rel=${doc#*:}
    if [ "$volume" = primary ]; then
        echo "/storage/emulated/0/$rel"
    else
        echo "/storage/$volume/$rel"
    fi
}

# Folder for a platform, from Cocoon's own rom_folders table.
platform_folder() {
    uri=$(sql "SELECT uri FROM rom_folders WHERE platformId = '$1' AND isEnabled = 1 LIMIT 1;")
    [ -n "$uri" ] || return 1
    saf_uri_to_path "$uri"
}

# group (Cocoon groups "(Disc N)" files) or m3u (.m3u in root, discs in .hidden/).
platform_mode() {
    [ -f "$MODES_CONF" ] || return 1
    sed -n "s/^$1[[:space:]]\{1,\}\([a-z0-9]*\).*/\1/p" "$MODES_CONF" | head -n 1
}
