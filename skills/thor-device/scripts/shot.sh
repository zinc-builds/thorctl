#!/bin/zsh
# shot.sh OUT_DIR [name]: screenshot both Thor screens to OUT_DIR/<name>-top.png and -bottom.png.
# Physical display ids come from SurfaceFlinger: the first listed (HWC 0) is the top screen.
set -e
out=${1:?usage: shot.sh OUT_DIR [name]}; name=${2:-shot}
mkdir -p "$out"
ids=($(adb shell dumpsys SurfaceFlinger --display-id | awk '{print $2}'))
[ ${#ids} -ge 2 ] || { echo "expected 2 displays, got: ${ids[*]}" >&2; exit 1; }
adb exec-out screencap -p -d "${ids[1]}" > "$out/$name-top.png"
adb exec-out screencap -p -d "${ids[2]}" > "$out/$name-bottom.png"
echo "$out/$name-top.png $out/$name-bottom.png"
