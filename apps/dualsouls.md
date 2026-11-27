# HK: Dual Souls (igawa6.dualsouls)

Adapter: `apps/dualsouls.json` (13 keys). Checked 2026-11-27 against an install on the AYN Thor, the decompiled APK (`com.radit.hkaux`), and `github.com/igawa6/dualsouls` at main (pushed 2026-11-26; the 1.0.3 release checked is from 2026-08-23, so field defaults may have changed since).

## Build Checked

- Checked against versionName `1.0.3`, versionCode 1, the latest release on 2026-11-27.
- `/sdcard/Android/data/igawa6.dualsouls` does not exist until the game data is built on first launch. Inputs: a Hollow Knight PC game folder (Steam layout) and the port's `.xdelta` patch. The adapter comes from source; no setting has been checked against a written file.

## What It Is

A same-version Unity rebuild of Hollow Knight 1.5.12620 for Android, patched on the device from your own PC copy of the game, with a bottom-screen companion for the Thor.

## Files

All in Unity's `persistentDataPath` = `/sdcard/Android/data/igawa6.dualsouls/files/`.

| File | What it holds |
|---|---|
| `hkds_options.json` | `{"dualScreen":1,"touch":"auto"}` from the two rows added to Hollow Knight's Options screens. |
| `hkds_layout.json` | Hand-edited dual-screen runtime config (about 150 flat fields). The app never writes it. |
| `tweaks.json` | Mod menu (QoL/cheats) state. |
| `main.1.igawa6.dualsouls.obb`, `hk_data_stamp.txt` | Built game data and its stamp. |
| save slots | Hollow Knight's four slots. |

Hollow Knight's own video/audio options are in Unity PlayerPrefs (`/data/data/igawa6.dualsouls/shared_prefs/`), not covered here. The port forces 120 fps with vSync off every few seconds.

## Write Rules (`json`, Unity JsonUtility)

- Flat, name-keyed fields. Do not nest. Unknown keys are ignored and logged once.
- Ints for switches (0/1), floats, strings in quotes.
- `hkds_layout.json`: include only the keys you change; everything else keeps its default. It hot-reloads on file mtime about three times a second, so changes apply live. An empty or half-written file keeps the previous config.
- `hkds_options.json` is read once per run, written by the app. Force-stop before editing. Once it exists, its `dualScreen` and `touch` win over the same settings in `hkds_layout.json`.

## UI Tests Still Needed

- First launch: grant Files permission, Import Game with the folder and patch, Build game data, Start.
- Then write `{"compStats":0}` to `hkds_layout.json` while playing and confirm the bottom FPS/battery readout disappears after the next scene change (build-time knob).
- Toggle Options > Game > Dual Screen and confirm `hkds_options.json` is written.
