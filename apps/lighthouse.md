# Lighthouse (com.lighthouse.android)

Adapter: `apps/lighthouse.json` (13 keys). Checked 2026-11-27 against an install on the AYN Thor, `libmain.so` strings from the APK, and the source of `github.com/izzy2lost/Lighthouse` (Android fork of `HarbourMasters/Lighthouse`) at HEAD. The libultraship submodule was not cloned.

## Build Checked

- Checked against versionName `1.0.2`, versionCode 1, the only release of izzy2lost/Lighthouse (`1.0.2`, 2026-08-07). HarbourMasters' own releases (1.2.2) have no Android build.
- Before the first launch `/sdcard/Android/data/com.lighthouse.android` does not exist. The adapter comes from source; no setting has been checked against a written file.

## What It Is

The Banjo-Kazooie decompilation running on libultraship (the Ship of Harkinian engine). The APK carries `gamedata.zip` (Torch configs for USA rev0/rev1, PAL, JP) and `lighthouse.o2r`; your ROM is converted to `bk.o2r` on the device.

## Files

App folder: `/sdcard/Android/data/com.lighthouse.android/files/` (`GameAssets`: `getExternalFilesDir`, falls back to internal `files/`).

| File | What it holds |
|---|---|
| `lighthouse.cfg.json` | libultraship config: `CVars` (all settings and enhancements), `Window` (size, backend, audio backend). |
| `imgui.ini` | ImGui window layout. |
| `baserom.us.z64`, `bk.o2r`, `lighthouse.o2r` | ROM copy and asset archives. |
| `mods/` | `.o2r` mods and romhacks. |
| saves | Managed by `SaveStore` (names not checked). |

## Write Rules (`json`)

- CVar names are split on dots into nested objects under `CVars`: `gSettings.MSAAValue` is `CVars/gSettings/MSAAValue`.
- Checkbox CVars are integers 0/1. Sliders are int or float as listed.
- Missing keys take the default given where the CVar is read.

## When It Reads and Writes

libultraship loads the config at start-up and saves it when a setting changes and on exit. Force-stop before editing. Texture Filter and Renderer API need a reload.

## Graphics Keys

Internal Resolution 0.5-2.0, MSAA 1-8, Current FPS 30 up to the display refresh (interpolation), Match Refresh Rate, VSync, Texture Filter (0 Three-Point, 1 Linear, 2 None). Enhancements: Extended Draw Distance 1-6x, Disable LOD, cutscene aspect. Many more `gEnhancements.*` CVars (fixes, cheats, cutscene skips) are in `libmain.so`; only the common ones are in the adapter.

## UI Tests Still Needed

- First launch: import a `.z64` (also check whether the importer accepts a byte-swapped `.n64`) and confirm `lighthouse.cfg.json` is created in the app folder.
- Find how the ImGui menu opens on Android (touch or controller combo) and record it.
- Set InternalResolution 1.5 and InterpolationFPS 60 through the adapter and confirm the menu shows them.
