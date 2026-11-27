#!/bin/zsh
# navbar.sh [--fix]: report whether the gesture bar (navigation handle) is showing on each Thor
# screen; with --fix, restart SystemUI (about 3 s) when it is, which re-applies hide_nav_bar.
set -e
tmp=$(mktemp -d)
shot=${0:A:h}/../../thor-device/scripts/shot.sh
check() {
    "$shot" "$tmp" nav >/dev/null
    python3 - "$tmp" <<'EOF'
import sys
from PIL import Image
out = []
for name in ("top", "bottom"):
    im = Image.open(f"{sys.argv[1]}/nav-{name}.png").convert("L")
    w, h = im.size
    # The handle is a bright pill centred ~30 px above the bottom edge.
    out.append(f"{name}:{'visible' if max(im.crop((w//2-200, h-40, w//2+200, h-20)).getdata()) > 200 else 'hidden'}")
print(" ".join(out))
EOF
}
state=$(check); echo "$state"
if [ "$1" = --fix ] && [[ $state == *visible* ]]; then
    adb shell "su -c 'pkill -f com.android.systemui'" || true
    sleep 6
    echo "after SystemUI restart: $(check)"
fi
