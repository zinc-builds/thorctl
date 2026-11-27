# Paper Cut EU (dev.ttyd.port.us)

Adapter: [papercut.json](papercut.json) (22 keys). Checked 2026-11-27 against **0.5.1** (versionCode 5019). Source: <https://github.com/LLCOOLT/paper-cut> (MIT), running the LLCOOLT/ttyd decompilation on Aurora. Keys, ranges and defaults are from `port/src/aurora/settings_aurora.c` and `port/include/port/settings.h` at tag **v0.5.1**.

## File

`settings.txt` in Aurora's user folder, beside the memory cards: `key=value` per line, no spaces, no sections. Read once at start (`portSettingsLoad`), clamped to each key's range; the settings page writes the whole file. The adapter assumes `/data/data/dev.ttyd.port.us/files/settings.txt` (SDL's pref path on Android); **not verified** on a device.

## Disc Region

This is the European build and wants G8MP01. Upstream ships one APK per disc release: a USA disc (G8ME01) needs the US APK (`papercut-0.5.1-us-android-arm64.apk`).

## Write Rules

Stop the app first. `msaa`, `language` and `pal_50hz` apply from the next start.
