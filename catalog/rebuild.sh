#!/bin/bash
# Rebuild the settings catalog for the Cocoon version installed on the device.
# Pulls the APK, decompiles it with jadx (brew install jadx), writes
# catalog/cocoon-<version>.json. Takes about 3 minutes.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
pkg=rip.moth.cocoonshell
version=$(adb shell dumpsys package $pkg | sed -n 's/.*versionName=\([^ ]*\).*/\1/p' | head -1)
[ -n "$version" ] || { echo "Cocoon is not installed on the device" >&2; exit 1; }
work=$(mktemp -d "${TMPDIR:-/tmp}/cocoon-catalog.XXXXXX")
echo "Cocoon $version -> $work"
adb pull "$(adb shell pm path $pkg | sed -n 's/^package://p' | head -1)" "$work/base.apk" >/dev/null
jadx -q --no-res --show-bad-code -j 8 -d "$work/jadx" "$work/base.apk" || true  # jadx exits 1 on any unparsed method
[ -d "$work/jadx/sources/rip/moth/cocoonshell" ] || { echo "jadx produced no sources" >&2; exit 1; }
python3 "$here/build_catalog.py" "$work/jadx/sources" "$version" > "$here/cocoon-$version.json"
python3 - "$here/cocoon-$version.json" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1]))
idx = c["search_index"]["entries"]
print(f"{len(c['keys'])} keys, {sum(1 for k in c['keys'].values() if k['files'])} with a known file, "
      f"{len(c['families'])} key families, {len(idx)} Settings pages, "
      f"{len(c['contract']['enums'])} enum and {len(c['contract']['float_ranges'])} range rules")
assert len(c["keys"]) > 200 and len(idx) > 30, "catalog looks incomplete; check build_catalog.py patterns"
EOF
echo "wrote $here/cocoon-$version.json; decompile kept in $work"
