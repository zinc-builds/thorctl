# Event loop for `cocoon-sync.sh watch`. Sourced after common.sh, discs.sh, rescan.sh.
#
# Cocoon's own discovery only checks for new games on its first resume after a
# process start or every 6 h, and its folder watcher never fires for files
# copied in over USB/MTP. So this loop watches each enabled ROM folder itself,
# on the SD card's backing path (/mnt/media_rw/...), which sees every write
# however it arrives. It also watches Cocoon's discovery prefs, so anything
# Cocoon detects on its own is imported too.
#
# A platform becomes dirty when a file its emulators accept (or an .m3u) is
# written, moved or deleted in its folder. Once the folder has been quiet for
# QUIET_SECS and no file in it changed for SETTLE_SECS (a copy in progress
# keeps bumping mtime), the folder is normalized and Cocoon rescans it. While
# nothing is dirty the loop blocks in read and never wakes the device.

QUIET_SECS=10
SETTLE_SECS=20
BUSY_RETRY_SECS=60
FAIL_RETRY_SECS=300
MAX_FAILURES=3
FOLDERS_MAP=$SYNC_HOME/folders.map
FOLDERS_SIG=$SYNC_HOME/folders.sig
CARRY_DIRTY=$SYNC_HOME/dirty
RELOAD=3

# Enabled ROM folders as one string, to notice folders added in Cocoon.
folders_signature() {
    sql "SELECT group_concat(platformId || '=' || uri, ' ') FROM
         (SELECT platformId, uri FROM rom_folders WHERE isEnabled = 1 ORDER BY id);"
}

# /storage/<vol>/... -> /mnt/media_rw/<vol>/..., /storage/emulated/0 -> /data/media/0
backing_path() {
    case "$1" in
        /storage/emulated/0/*) echo "/data/media/0/${1#/storage/emulated/0/}" ;;
        /storage/*) echo "/mnt/media_rw/${1#/storage/}" ;;
        *) die "unexpected ROM folder path: $1" ;;
    esac
}

# Writes "backing dir<TAB>platformId" per enabled ROM folder.
build_folders_map() {
    : > "$FOLDERS_MAP"
    sql "SELECT platformId || char(9) || uri FROM rom_folders WHERE isEnabled = 1;" \
        | while IFS="$TAB" read -r pid uri; do
            dir=$(backing_path "$(saf_uri_to_path "$uri")")
            [ -d "$dir" ] || { log "skip watching $pid: $dir missing"; continue; }
            printf '%s\t%s\n' "$dir" "$pid" >> "$FOLDERS_MAP"
        done || die "could not build $FOLDERS_MAP"
    [ -s "$FOLDERS_MAP" ] || die "no ROM folders to watch"
    folders_signature > "$FOLDERS_SIG"
}

add_dirty() {
    case " $dirty " in *" $1 "*) ;; *) dirty="${dirty:+$dirty }$1" ;; esac
}

# Cocoon's per-platform filename regexes use PCRE lookarounds that grep -E
# lacks, and they accept nearly everything anyway. Skip what is never a game:
# dot-files and the save, state and metadata files emulators may write beside
# ROMs, so playing a game does not trigger a rescan.
NOT_A_GAME='^\.|\.(srm|sav|state[0-9]*|st[0-9]|auto|mcr|mcd|mc|dsv|sps|eep|fla|rtc|bak|tmp|part|log|txt|nfo|xml|cfg|ini|png|jpg|jpeg)$'

# handle_event <event line> [platform ids to ignore]
handle_event() {
    ev_dir=$(printf '%s\n' "$1" | cut -f2)
    ev_file=$(printf '%s\n' "$1" | cut -f3)
    if [ "$ev_dir" = "$COCOON_PREFS" ]; then
        if [ "$ev_file" = "${DISCOVERY_PREFS##*/}" ]; then
            for p in $(pending_platforms); do add_dirty "$p"; done
        fi
        # A folder added under a platform's settings only touches Cocoon's
        # settings prefs, not the discovery prefs, so check on any prefs write.
        [ "$(folders_signature)" = "$(cat "$FOLDERS_SIG")" ] || folders_changed=1
        return 0
    fi
    entry=$(awk -F'\t' -v d="$ev_dir" '$1 == d' "$FOLDERS_MAP")
    [ -n "$entry" ] || return 0
    ev_pid=$(printf '%s\n' "$entry" | cut -f2)
    case " $2 " in *" $ev_pid "*) return 0 ;; esac
    printf '%s\n' "$ev_file" | grep -qiE "$NOT_A_GAME" && return 0
    add_dirty "$ev_pid"
    last_event=$(date +%s)
}

# Newest mtime (epoch) of files in a platform folder and its .hidden.
newest_mtime() {
    find "$1" "$1/$HIDDEN" -maxdepth 1 -type f 2> /dev/null -exec stat -c %Y {} + | sort -n | tail -n 1
}

settled() {
    now=$(date +%s)
    [ $((now - last_event)) -ge "$QUIET_SECS" ] || return 1
    for p in $dirty; do
        dir=$(awk -F'\t' -v p="$p" '$2 == p { print $1 }' "$FOLDERS_MAP")
        [ -n "$dir" ] || continue
        newest=$(newest_mtime "$dir")
        [ -z "$newest" ] || [ $((now - newest)) -ge "$SETTLE_SECS" ] || return 1
    done
}

watch_loop() {
    while :; do
        build_folders_map
        log "watching $(cut -f2 "$FOLDERS_MAP" | tr '\n' ' ')"
        watch_events
        [ $? = "$RELOAD" ] || break
        pkill -P $$ -x inotifyd
        log "ROM folders changed; reloading"
    done
    die "inotifyd exited"
}

# Runs until inotifyd ends, or returns $RELOAD when Cocoon's folders changed
# (pending dirty platforms are carried over in $CARRY_DIRTY).
watch_events() {
    # toybox inotifyd: w = written, d = deleted, m/y = renamed (both names).
    # This build (0.8.6) drops the first letter of every mask, so each mask
    # starts with a sacrificial "x".
    # shellcheck disable=SC2046
    inotifyd - "$COCOON_PREFS:xwm" $(cut -f1 "$FOLDERS_MAP" | sed 's/$/:xwdmy/') | {
        dirty=""; last_event=0; tick=$QUIET_SECS; failures=0; folders_changed=0
        if [ -f "$CARRY_DIRTY" ]; then
            for p in $(cat "$CARRY_DIRTY"); do add_dirty "$p"; done
            rm -f "$CARRY_DIRTY"
            last_event=$(date +%s)
        fi
        while :; do
            if [ -n "$dirty" ]; then read -t "$tick" -r line; rc=$?; else read -r line; rc=$?; fi
            [ "$rc" = 1 ] && break
            if [ "$rc" = 0 ]; then
                handle_event "$line"
                if [ "$folders_changed" = 1 ]; then
                    echo "$dirty" > "$CARRY_DIRTY"
                    exit "$RELOAD"
                fi
                continue
            fi
            settled || { tick=$QUIET_SECS; continue; }
            done_now=$dirty
            ( rescan $dirty ); rc=$?
            case $rc in
                0) dirty=""; failures=0 ;;
                2) log "pending: $dirty (Cocoon busy)"; tick=$BUSY_RETRY_SECS; continue ;;
                *)
                    failures=$((failures + 1))
                    if [ "$failures" -lt "$MAX_FAILURES" ]; then
                        log "sync of '$dirty' failed ($failures/$MAX_FAILURES); retrying in ${FAIL_RETRY_SECS}s"
                        tick=$FAIL_RETRY_SECS
                        continue
                    fi
                    log "sync of '$dirty' failed $failures times; giving up until the next change"
                    dirty=""; failures=0 ;;
            esac
            # Discard the events our own moves and m3u writes just queued.
            while read -t 3 -r line; do handle_event "$line" "$done_now"; done
            tick=$QUIET_SECS
        done
    }
}
