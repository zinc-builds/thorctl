---
name: thor-device
description: Drive and inspect a rooted AYN Thor (dual-screen Android 13 handheld) over adb. Use for any task on the Thor - screenshots of both screens, tapping UI, reading or editing app data as root, installing or updating APKs, reverse-engineering an app's intents, or moving files to the SD card. Covers display ids, input quirks, SELinux/ownership fixes and storage paths.
---

# AYN Thor Device Control

The Thor: Snapdragon 8 Gen 2 / Adreno 740, Android 13, firmware `Thor_V1.0.0.377`, rooted with Magisk (`su` works from `adb shell`). Connected over adb from the Mac. The front-end is Cocoon; see the `cocoon-library` skill. Repo paths below are relative to the repo root (two levels above this skill, after resolving symlinks). If `local/skills/thor-device.md` exists there, read it too: it holds this device's own details.

## Displays

- **Top screen** = logical display 0 (1920x1080). **Bottom screen** = logical display 4 (1240x1080).
- Screenshots need *physical* ids: `scripts/shot.sh OUT_DIR name` captures both (top is the first id listed by `dumpsys SurfaceFlinger --display-id`).
- Taps: `adb shell input -d 0 tap x y` (top) / `input -d 4 tap x y` (bottom). Coordinates are in that display's own pixels.
- `uiautomator dump` only sees display 0. `scripts/ui.sh dump` and `scripts/ui.sh tap "Label"` wrap it. Compose apps often expose few labels; fall back to a screenshot and coordinates.
- Cocoon's bottom-screen grid: first tap focuses a tile, second tap opens it.

## Input Quirks

- Cocoon and SDL-based emulators (ARMSX2) **ignore injected gamepad keys** (`KEYCODE_BUTTON_A` etc.). Use taps, an app's own menus, or intents.
- Cocoon's on-screen keyboard drops taps faster than ~1 s apart and ignores `input text`. Prefer `thorctl rename`/`sql --write`.
- The screen sleeps during long jobs: `adb shell input keyevent KEYCODE_WAKEUP; adb shell wm dismiss-keyguard` before any UI step. A black screenshot usually means asleep.
- `KEYCODE_HOME`, `KEYCODE_BACK`, `KEYCODE_APP_SWITCH` (Recents) work.
- `am start --display 0 <emulator>` can leave Cocoon's bottom activity on the top screen; recover with `adb shell am force-stop rip.moth.cocoonshell` or `am start --display 0 -a android.intent.action.MAIN -c android.intent.category.HOME`.
- Check what is in front: `dumpsys activity activities | grep topResumedActivity` (one line per display) and `dumpsys window | grep mCurrentFocus`.

## Shell Gotchas

- In zsh never name a variable `path` (it clobbers `$PATH`).
- Harness blocks long foreground `sleep`; wait with `until <check>; do sleep 3; done` or chains of `adb shell true`, and push multi-minute waits to background jobs.
- Device shell is toybox/mksh: no `sort -h`, `ls --time-style`; `inotifyd` drops the first mask letter.
- `adb` inside `while read` swallows stdin; add `</dev/null`.

## Root Edits to App Data

1. `am force-stop <pkg>` first (apps rewrite prefs on exit).
2. Edit with `su -c` (sed / printf), keeping a backup in `/data/local/tmp`.
3. Run `scripts/fix-pref-owner.sh <pkg> <file>`: root edits leave `root:root` or the wrong uid and a bare `s0` SELinux label without the app's MLS categories (`s0:cNNN,c256,c512,c768`), so the app silently can't read the file. Always derive the uid from `dumpsys package <pkg> | grep userId`, never from file owners on shared storage (those show the MediaProvider uid 10109).

## Storage

- SD card: `/storage/<vol>` (FUSE) = `/mnt/media_rw/<vol>` (backing, use for root writes/inotify), where `<vol>` is the card's volume id such as `1234-ABCD`. `scripts/sdcard.sh` prints it: `$THOR_SDCARD` when set, otherwise the first `XXXX-XXXX` entry in `/storage`. ROMs in `Roms/<platform>`, BIOS in `Roms/BIOS`.
- Internal: `/storage/emulated/0` = `/data/media/0` backing. `Roms/Steam` lives here (DroidDeck can't write the SD card).
- `Android/data/<pkg>` on either volume is invisible to SAF pickers; apps' private data is `/data/data/<pkg>`.
- Apps targeting SDK <= 29 with WRITE_EXTERNAL_STORAGE (e.g. DroidDeck, target 28) can write anywhere on internal storage by path, but not the SD card.

## Installing and Updating APKs

- Verify downloads against GitHub's `digest` field (`curl -s api.github.com/repos/O/R/releases`), check the package with `~/Library/Android/sdk/build-tools/37.0.0/aapt2 dump badging x.apk` (no Java for apksigner).
- Update in place with `adb install -r`. `INSTALL_FAILED_UPDATE_INCOMPATIBLE` = different signing key; **never uninstall to work around it without asking** (loses app data). Check where saves live first.
- Before uninstalling apps with game data, back up Wine `drive_c/users` dirs or save folders to a backups folder on the Mac.

## Reverse-Engineering Launch Intents

1. `adb shell pm path <pkg>` → `adb pull` → `jadx -q -d out app.apk` (jadx is installed via brew).
2. `dumpsys package <pkg>` "Activity Resolver Table" lists schemes and actions.
3. grep sources for `getStringExtra`, `getQueryParameter`, `LAUNCH`, the scheme. Big single-line Kotlin metadata strings break grep context; use a small Python line filter.
4. Shell (uid 2000) cannot grant URI permission: drop `--grant-read-uri-permission` when testing; the target app needs its own SAF tree grant.

## Permissions Policy

Security toggles (All files access, accessibility services, default apps) are the user's to flip; ask them. SAF "Allow access to folder" dialogs inside a setup the user asked for are fine to accept.
