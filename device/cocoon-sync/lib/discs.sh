# Multi-disc layout normalizer. Sourced after common.sh.
#
# Cocoon (v3.07) scans only the top level of a ROM folder and skips dot-named
# entries. Within it:
#   - an .m3u whose entries resolve becomes one game and hides those discs;
#   - other files named "Name (Disc N).ext" (also [Disc N], Disk, CD) are
#     grouped into one game that launches the lowest disc.
# A folder is put into one of two layouts, chosen per platform in modes.conf:
#   group: discs stay in the root under "(Disc N)" names, no .m3u in the root.
#          For emulators that cannot open .m3u from a content:// URI
#          (DuckStation) or at all (ARMSX2).
#   m3u:   "Name.m3u" in the root, discs in .hidden/. For emulators that read
#          .m3u from a real path (RetroArch Beetle Saturn, Flycast).
# Nothing is ever deleted. Replaced or parked .m3u files go to .hidden/.

HIDDEN=.hidden
TAB=$(printf '\t')

# Disc image formats (a .cue sheet stands for its .bin tracks). sh has no
# local variables, so helpers avoid assigning names their callers use.
is_disc_ext() {
    case "$(echo "$1" | tr 'A-Z' 'a-z')" in
        chd|cdi|iso|cso|pbp|rvz|cue) return 0 ;;
        *) return 1 ;;
    esac
}

# Prints "base|suffix|ext<TAB>discnumber" for a disc file name, nothing otherwise.
#   "Example Quest (USA) (Disc 1).chd" -> "Example Quest (USA)||chd	1"
#   "Example Saga CD-1.cdi"      -> "Example Saga||cdi	1"
disc_key() {
    out=$(printf '%s\n' "$1" | sed -nE "s/^(.*[^ ])[ ]*[[(][ ]*([Dd][Ii][Ss][CcKk]|[Cc][Dd])[ ]*([0-9]+)[ ]*[])](.*)\.([^.]+)\$/\1|\4|\5$TAB\3/p")
    [ -n "$out" ] || out=$(printf '%s\n' "$1" | sed -nE "s/^(.*[^ _-])[ _-]+([Dd][Ii][Ss][CcKk]|[Cc][Dd])[ _-]*([0-9]+)\.([^.]+)\$/\1||\4$TAB\3/p")
    [ -n "$out" ] || return 1
    is_disc_ext "$(printf '%s\n' "$out" | cut -f1 | cut -d'|' -f3)" || return 1
    printf '%s\n' "$out"
}

is_bracket_disc_name() {
    printf '%s\n' "$1" | grep -qE '[[(][ ]*([Dd][Ii][Ss][CcKk]|[Cc][Dd])[ ]*[0-9]+[ ]*[])]'
}

act() {
    if [ "${DRY_RUN:-0}" = 1 ]; then
        echo "DRY-RUN: $*"
    else
        log "$*"
        "$@" || die "failed: $*"
    fi
}

# Files referenced by a .cue sheet (FILE "x" BINARY), one per line.
cue_tracks() {
    tr -d '\r' < "$1" | sed -nE 's/^[[:space:]]*FILE[[:space:]]+"([^"]+)".*/\1/p; s/^[[:space:]]*FILE[[:space:]]+([^" ]+)[[:space:]].*/\1/p'
}

# Moves a disc (and, for .cue, its tracks) from $1 into $2.
move_disc() {
    src_dir=$1; dst_dir=$2; name=$3
    act mv "$src_dir/$name" "$dst_dir/$name"
    case "$name" in
        *.[Cc][Uu][Ee])
            cue_tracks "$dst_dir/$name" | while IFS= read -r track; do
                [ -e "$src_dir/$track" ] && act mv "$src_dir/$track" "$dst_dir/$track"
            done || die "moving tracks of $name failed" ;;
    esac
}

# "key<TAB>num<TAB>location<TAB>name" for every disc file in root and .hidden.
list_discs() {
    dir=$1
    for loc in . "$HIDDEN"; do
        [ -d "$dir/$loc" ] || continue
        find "$dir/$loc" -maxdepth 1 -type f ! -name '.*' | while IFS= read -r path; do
            name=${path##*/}
            k=$(disc_key "$name") || continue
            printf '%s\t%s\t%s\n' "$k" "$loc" "$name"
        done
    done
}

normalize_m3u() {
    dir=$1
    list_discs "$dir" > "$TMPDIR/discs"
    cut -f1 "$TMPDIR/discs" | sort -u | while IFS= read -r key; do
        members=$(awk -F'\t' -v k="$key" '$1 == k' "$TMPDIR/discs")
        [ "$(printf '%s\n' "$members" | wc -l)" -ge 2 ] || continue
        base=$(printf '%s\n' "$key" | cut -d'|' -f1)
        suffix=$(printf '%s\n' "$key" | cut -d'|' -f2)
        m3u="$base$(printf '%s' "$suffix" | sed 's/^ *//; s/ *$//').m3u"
        [ -d "$dir/$HIDDEN" ] || act mkdir "$dir/$HIDDEN"
        printf '%s\n' "$members" | awk -F'\t' '$3 == "."' | cut -f4 | while IFS= read -r name; do
            move_disc "$dir" "$dir/$HIDDEN" "$name"
        done || exit 1
        want=$(printf '%s\n' "$members" | sort -t "$TAB" -k2,2n | awk -F'\t' -v h="$HIDDEN" '{print h "/" $4}')
        if [ -f "$dir/$m3u" ] && [ "$(tr -d '\r' < "$dir/$m3u")" = "$want" ]; then
            continue
        fi
        if [ -f "$dir/$m3u" ]; then
            act mv "$dir/$m3u" "$dir/$HIDDEN/$m3u.replaced-$(date +%Y%m%d%H%M%S)"
        fi
        if [ "${DRY_RUN:-0}" = 1 ]; then
            echo "DRY-RUN: write $dir/$m3u:"; printf '%s\n' "$want"
        else
            printf '%s\n' "$want" > "$dir/$m3u" || die "cannot write $dir/$m3u"
            log "wrote $dir/$m3u ($(printf '%s\n' "$want" | wc -l) discs)"
        fi
    done || die "m3u normalize failed in $dir"
}

normalize_group() {
    dir=$1
    # Park root .m3u files whose entries are all discs, bringing hidden discs back.
    find "$dir" -maxdepth 1 -type f -iname '*.m3u' ! -name '.*' | while IFS= read -r m3u; do
        entries=$(tr -d '\r' < "$m3u" | sed 's/^\.\///' | grep -v -e '^#' -e '^[[:space:]]*$')
        [ "$(printf '%s\n' "$entries" | wc -l)" -ge 2 ] || continue
        ok=1
        printf '%s\n' "$entries" > "$TMPDIR/entries"
        while IFS= read -r e; do
            name=${e##*/}
            disc_key "$name" > /dev/null || { ok=0; break; }
            [ -e "$dir/$e" ] || [ -e "$dir/$name" ] || { log "skip $m3u: missing $e"; ok=0; break; }
        done < "$TMPDIR/entries"
        [ "$ok" = 1 ] || continue
        while IFS= read -r e; do
            name=${e##*/}
            if [ ! -e "$dir/$name" ]; then
                move_disc "$dir/${e%/*}" "$dir" "$name"
            fi
        done < "$TMPDIR/entries"
        [ -d "$dir/$HIDDEN" ] || act mkdir "$dir/$HIDDEN"
        act mv "$m3u" "$dir/$HIDDEN/${m3u##*/}"
    done || die "m3u parking failed in $dir"
    # Rename "Name CD-1.ext" style discs so Cocoon's (Disc N) grouping sees them.
    list_discs "$dir" | awk -F'\t' '$3 == "."' > "$TMPDIR/discs"
    cut -f1 "$TMPDIR/discs" | sort | uniq -d | while IFS= read -r key; do
        awk -F'\t' -v k="$key" '$1 == k' "$TMPDIR/discs" | while IFS="$TAB" read -r k num loc name; do
            is_bracket_disc_name "$name" && continue
            case "$name" in *.[Cc][Uu][Ee]) log "skip rename of cue sheet $name"; continue ;; esac
            base=$(printf '%s\n' "$k" | cut -d'|' -f1)
            ext=$(printf '%s\n' "$k" | cut -d'|' -f3)
            new="$base (Disc $num).$ext"
            [ -e "$dir/$new" ] && { log "skip rename $name: $new exists"; continue; }
            act mv "$dir/$name" "$dir/$new"
        done || exit 1
    done || die "disc renaming failed in $dir"
}

# normalize_folder <dir> <group|m3u>
normalize_folder() {
    [ -d "$1" ] || die "no such folder: $1"
    TMPDIR=$(mktemp -d "$SYNC_HOME/tmp.XXXXXX") || die "mktemp failed"
    case "$2" in
        m3u) normalize_m3u "$1" ;;
        group) normalize_group "$1" ;;
        *) rm -rf "$TMPDIR"; die "unknown mode '$2' for $1" ;;
    esac
    rm -rf "$TMPDIR"
}
