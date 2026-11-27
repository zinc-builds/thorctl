#!/bin/bash
# Daily job (launchd: ~/Library/LaunchAgents/com.thorctl.autodiscover.plist).
# Finds the Thor on Wi-Fi adb, then drafts adapters for emulators/recomps that
# were installed since the last run. Free: no agent runs. A macOS notification
# says when there is something for an agent to finish (apps/<name>.md).
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/Library/Android/sdk/platform-tools:$HOME/.local/bin:/usr/bin:/bin"
echo "== $(date '+%Y-%m-%d %H:%M')"
serial=""
for d in $(adb devices | awk 'NR>1 && $2=="device" {print $1}'); do
  [ "$(adb -s "$d" shell getprop ro.product.model 2>/dev/null | tr -d '\r')" = "AYN Thor" ] && serial=$d
done
if [ -z "$serial" ]; then
  for addr in $(adb mdns services 2>/dev/null | awk '/_adb._tcp/ {print $3}'); do
    adb connect "$addr" >/dev/null 2>&1
    if [ "$(adb -s "$addr" shell getprop ro.product.model 2>/dev/null | tr -d '\r')" = "AYN Thor" ]; then
      serial=$addr
      break
    fi
  done
fi
if [ -z "$serial" ]; then
  echo "Thor not reachable over adb; skipped"
  exit 0
fi
export ANDROID_SERIAL=$serial
thorctl app autodiscover --notify
