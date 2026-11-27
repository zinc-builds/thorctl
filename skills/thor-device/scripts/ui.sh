#!/bin/zsh
# ui.sh: read and tap labelled UI elements on an AYN Thor display via uiautomator.
#   ui.sh dump                      list text/content-desc elements with bounds
#   ui.sh tap "Label" [display]     tap the first element whose text or content-desc equals Label
# uiautomator only sees display 0 (top screen); for the bottom screen use screenshots + input -d 4.
set -e
display=${3:-0}
dump() {
    adb shell "uiautomator dump /data/local/tmp/ui.xml >/dev/null 2>&1; cat /data/local/tmp/ui.xml" | tr '>' '\n'
}
case $1 in
    dump)
        dump | grep -o -E '(text|content-desc)="[^"]+"[^/]*bounds="[^"]+"' \
            | sed -E 's/ (resource-id|class|package|checkable|checked|clickable|enabled|focusable|focused|scrollable|long-clickable|password|selected)="[^"]*"//g; s/ content-desc=""//' ;;
    tap)
        b=$(dump | grep -E "(text|content-desc)=\"$2\"" | head -1 \
            | sed -nE 's/.*bounds="\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]".*/\1 \2 \3 \4/p')
        [ -n "$b" ] || { echo "not found: $2" >&2; exit 1; }
        set -- $(echo $b | awk '{print int(($1+$3)/2), int(($2+$4)/2)}')
        adb shell input -d "$display" tap $1 $2
        echo "tapped $1,$2" ;;
    *) echo "usage: ui.sh dump|tap \"Label\" [display]" >&2; exit 2 ;;
esac
