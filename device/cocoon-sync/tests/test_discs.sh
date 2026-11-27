#!/system/bin/sh
# Normalizer tests. Run on the device as root:
#   SYNC_HOME=<staged copy> sh tests/test_discs.sh <scratch dir on the SD card>
# The scratch dir should be dot-named so Cocoon never scans it.
set -u
. "$SYNC_HOME/lib/common.sh"
. "$SYNC_HOME/lib/discs.sh"
LOG=$SYNC_HOME/test.log
ROOT=$1
fails=0

check() {  # check <description> <test expression...>
    desc=$1; shift
    if "$@"; then echo "PASS $desc"; else echo "FAIL $desc"; fails=$((fails + 1)); fi
}

fresh() {
    rm -rf "$ROOT/$1" && mkdir -p "$ROOT/$1" && cd "$ROOT/$1" || exit 1
    shift
    for f in "$@"; do mkdir -p "$(dirname "$f")"; echo x > "$f"; done
}

# disc_key parsing
check "bracket disc key" [ "$(disc_key 'Example Quest (USA) (Disc 1).chd')" = "Example Quest (USA)||chd${TAB}1" ]
check "square bracket + suffix" [ "$(disc_key 'Game [Disk 2] (Rev 1).iso')" = "Game| (Rev 1)|iso${TAB}2" ]
check "bare CD-N" [ "$(disc_key 'Example Saga CD-2.cdi')" = "Example Saga||cdi${TAB}2" ]
not_disc() { ! disc_key "$1" > /dev/null; }
check "not a disc" not_disc 'Example Racer 2.cdi'
check "bin track ignored" not_disc 'Game (Disc 1).bin'

# m3u mode: loose discs, a broken existing m3u, a cue set, a single-disc game
fresh m3u \
    'A (USA) (Disc 1).chd' 'A (USA) (Disc 2).chd' \
    'B CD-1.cdi' 'B CD-2.cdi' \
    'C (Disc 1).cue' 'C (Disc 1).bin' 'C (Disc 2).cue' 'C (Disc 2).bin' \
    'Single (USA).chd'
printf '.hidden/A (USA) (Disc 1).chd\n.hidden/A (USA) (Disc 2).chd\n' > 'A (USA).m3u'
printf 'FILE "C (Disc 1).bin" BINARY\n' > 'C (Disc 1).cue'
printf 'FILE "C (Disc 2).bin" BINARY\n' > 'C (Disc 2).cue'
normalize_folder "$ROOT/m3u" m3u
check "m3u: discs moved to .hidden" [ -f '.hidden/A (USA) (Disc 2).chd' ] && [ ! -e 'A (USA) (Disc 1).chd' ]
check "m3u: matching m3u kept as is" [ "$(cat 'A (USA).m3u')" = "$(printf '.hidden/A (USA) (Disc 1).chd\n.hidden/A (USA) (Disc 2).chd')" ]
check "m3u: CD-N set gets B.m3u" [ "$(cat 'B.m3u')" = "$(printf '.hidden/B CD-1.cdi\n.hidden/B CD-2.cdi')" ]
check "m3u: cue tracks follow their sheet" [ -f '.hidden/C (Disc 2).bin' ] && [ ! -e 'C (Disc 1).bin' ]
check "m3u: single disc untouched" [ -f 'Single (USA).chd' ]
before=$(find . | sort)
normalize_folder "$ROOT/m3u" m3u
check "m3u: second run changes nothing" [ "$(find . | sort)" = "$before" ]
echo y > '.hidden/A (USA) (Disc 3).chd'
normalize_folder "$ROOT/m3u" m3u
check "m3u: added disc rewrites m3u" [ "$(wc -l < 'A (USA).m3u')" -eq 3 ]
check "m3u: old m3u kept in .hidden" [ -n "$(find .hidden -name 'A (USA).m3u.replaced-*')" ]

# group mode: m3u pointing into .hidden, m3u pointing at root, CD-N names
fresh group \
    '.hidden/P (Disc 1).chd' '.hidden/P (Disc 2).chd' \
    'Q (Disc 1).chd' 'Q (Disc 2).chd' \
    'R CD-1.chd' 'R CD-2.chd' 'Other.chd'
printf '.hidden/P (Disc 1).chd\n.hidden/P (Disc 2).chd\n' > 'P.m3u'
printf 'Q (Disc 1).chd\r\nQ (Disc 2).chd\r\n' > 'Q.m3u'
printf 'Missing (Disc 1).chd\nMissing (Disc 2).chd\n' > 'Broken.m3u'
normalize_folder "$ROOT/group" group
check "group: hidden discs back in root" [ -f 'P (Disc 2).chd' ] && [ ! -e '.hidden/P (Disc 2).chd' ]
check "group: m3u parked" [ -f '.hidden/P.m3u' ] && [ -f '.hidden/Q.m3u' ] && [ ! -e 'Q.m3u' ]
check "group: m3u with missing discs left alone" [ -f 'Broken.m3u' ]
check "group: CD-N renamed to (Disc N)" [ -f 'R (Disc 1).chd' ] && [ -f 'R (Disc 2).chd' ]
check "group: unrelated file untouched" [ -f 'Other.chd' ]
before=$(find . | sort)
normalize_folder "$ROOT/group" group
check "group: second run changes nothing" [ "$(find . | sort)" = "$before" ]

# dry run touches nothing
fresh dry 'D (Disc 1).chd' 'D (Disc 2).chd'
DRY_RUN=1 normalize_folder "$ROOT/dry" m3u > /dev/null
check "dry run: no changes" [ -f 'D (Disc 1).chd' ] && [ ! -e 'D.m3u' ]

cd / && rm -rf "$ROOT"
echo "$fails failure(s)"
[ "$fails" -eq 0 ]
