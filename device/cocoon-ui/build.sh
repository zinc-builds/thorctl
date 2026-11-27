#!/bin/bash
# Build cocoon-ui.jar (a dex for app_process). Needs a JDK and the Android SDK.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
sdk=${ANDROID_HOME:-$HOME/Library/Android/sdk}
platform=$sdk/platforms/android-34/android.jar
d8=$(ls -d "$sdk"/build-tools/*/ | sort -V | tail -1)d8
out=$(mktemp -d "${TMPDIR:-/tmp}/cocoon-ui-build.XXXXXX")
javac -nowarn -source 8 -target 8 -cp "$platform" -d "$out/classes" $(find "$here/src" -name '*.java') 2>&1 | grep -v "^warning: \[options\]" || true
[ -f "$out/classes/cocoonui/Server.class" ] || { echo "javac failed" >&2; exit 1; }
"$d8" --min-api 33 --lib "$platform" --output "$out" $(find "$out/classes" -name '*.class')
(cd "$out" && zip -q -X "$here/cocoon-ui.jar" classes.dex)
echo "built $here/cocoon-ui.jar"
