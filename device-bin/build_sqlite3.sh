#!/bin/sh
# Builds a static arm64 sqlite3 CLI for the Thor from the official amalgamation.
# Usage: build_sqlite3.sh <unzipped sqlite-amalgamation dir>   (ANDROID_NDK_HOME picks the NDK)
set -eu
src=$1
out=$(cd "$(dirname "$0")" && pwd)/sqlite3
ndk=${ANDROID_NDK_HOME:-/opt/homebrew/share/android-ndk}
cc=$(ls "$ndk"/toolchains/llvm/prebuilt/*/bin/aarch64-linux-android30-clang | head -n 1)
[ -x "$cc" ] || { echo "no NDK clang under $ndk; set ANDROID_NDK_HOME" >&2; exit 1; }
"$cc" -O2 -static -o "$out" \
  -DSQLITE_THREADSAFE=0 -DSQLITE_OMIT_LOAD_EXTENSION -DHAVE_READLINE=0 \
  "$src/shell.c" "$src/sqlite3.c"
echo "$out"
