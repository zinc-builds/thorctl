# Runs Cocoon's own "Rescan Games" for chosen platforms. Sourced after common.sh.
#
# Cocoon has no headless scan entry point. Its notification action opens the
# (non-exported) SettingsActivity with settings_discovery_rescan_platform_ids,
# which shows the Rescan Games picker with those platforms ticked. Root can
# start that activity; the start and OK buttons are then found in the
# accessibility tree (uiautomator only sees display 0) and tapped. Cocoon
# ignores injected gamepad keys, so taps are the only input that works.

UI_DUMP=$SYNC_HOME/ui.xml

ui_dump() {
    uiautomator dump "$UI_DUMP" > /dev/null 2>&1 || return 1
    tr '>' '\n' < "$UI_DUMP"
}

# Centre "x y" of the first node whose attribute matches, e.g. ui_center 'content-desc="Y"'.
ui_center() {
    printf '%s\n' "$2" | grep -F "$1" | head -n 1 \
        | sed -nE 's/.*bounds="\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]".*/\1 \2 \3 \4/p' \
        | awk '{ printf "%d %d\n", ($1 + $3) / 2, ($2 + $4) / 2 }'
}

# Waits up to $2 seconds for a node matching $1; prints the dump.
ui_wait_for() {
    deadline=$(( $(date +%s) + $2 ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        tree=$(ui_dump) && printf '%s\n' "$tree" | grep -qF "$1" && { printf '%s\n' "$tree"; return 0; }
        sleep 1
    done
    return 1
}

# True when the screen is on, only Cocoon is in front (no emulator running) and
# no other window, such as the "Use USB for" dialog, has focus on display 0.
cocoon_idle() {
    dumpsys power 2> /dev/null | grep -q "mWakefulness=Awake" || return 1
    fronts=$(dumpsys activity activities 2> /dev/null | grep 'topResumedActivity=' | grep -c .)
    ours=$(dumpsys activity activities 2> /dev/null | grep 'topResumedActivity=' | grep -c "$COCOON_PKG/")
    [ "$fronts" -gt 0 ] && [ "$fronts" = "$ours" ] || return 1
    focus0=$(dumpsys window displays 2> /dev/null \
        | awk '/Display: mDisplayId=/ { d = ($2 == "mDisplayId=0") } d && /mCurrentFocus=/ { print; exit }')
    case "$focus0" in
        *mCurrentFocus=null*|*"$COCOON_PKG"*) return 0 ;;
        *) return 1 ;;
    esac
}

# rescan_platforms <platformId>... ; returns 2 when Cocoon is busy (try later).
rescan_platforms() {
    cocoon_idle || return 2
    ids=$(echo "$*" | tr ' ' ',')
    am start --display 0 -n "$COCOON_PKG/.ui.activity.SettingsActivity" \
        --ei settings_initial_tab_index 1 --ez settings_focus_content_on_launch true \
        --esal settings_discovery_rescan_platform_ids "$ids" > /dev/null \
        || die "could not open Cocoon's rescan screen"
    # Allow for a cold start of Cocoon, e.g. right after boot.
    tree=$(ui_wait_for 'text="Rescan Games"' 45) \
        || die "Rescan Games screen did not appear; screen shows: $(ui_dump | sed -nE 's/.*text="([^"]+)".*/\1/p' | head -n 5 | tr '\n' '|')"
    printf '%s\n' "$tree" | grep -qF "text=\"$# platform(s) selected\"" \
        || die "rescan screen does not show $# selected platform(s) for: $ids"
    set -- $(ui_center 'content-desc="Y"' "$tree")
    [ -n "$1" ] || die "start button not found on rescan screen"
    input -d 0 tap "$1" "$2"
    tree=$(ui_wait_for 'text="Scan complete"' 600) || die "scan for $ids did not finish"
    summary=$(printf '%s\n' "$tree" | sed -nE 's/.*text="([^"]*)".*/\1/p' | tr '\n' ' ')
    log "rescanned $ids: $summary"
    set -- $(ui_center 'text="OK"' "$tree")
    [ -n "$1" ] || die "OK button not found after scan"
    input -d 0 tap "$1" "$2"
    am start -a android.intent.action.MAIN -c android.intent.category.HOME > /dev/null 2>&1
}
