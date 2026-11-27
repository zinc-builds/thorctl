# XenDroid (xendroid.compose)

Adapter: `apps/xendroid.json` (40 keys). Checked 2026-11-27 against versionName `0b11201` (versionCode 1) on an AYN Thor and the decompiled APK.

XenDroid is an Xbox 360 emulator: an Android port of Xenia (started from aX360e / Xenia Canary, later rebased on Xenia Edge) with a Kotlin/Compose front end. The core is `lib/arm64-v8a/libe.so`; it uses Xenia's cvar system and TOML config.

## Files

| Path | Role |
|---|---|
| `/sdcard/Android/data/xendroid.compose/files/compose/xenia-canary.config.toml` | Global config. Written on first run. |
| `.../files/compose/default_config.toml` | Commented template of every option with defaults (50744 bytes). Re-copied from the APK on every start when it differs. Never edit. |
| `.../files/compose/config/<TITLEID>.config.toml` | Per-game overrides. The folder is created with the first one. |
| `.../files/compose/content/<XUID>/` | Profile content, one folder per profile XUID. |
| `.../files/compose/cache*/`, `logs/` | Caches, logs. |
| `/data/data/xendroid.compose/files/datastore/xendroid_prefs.preferences_pb` | DataStore: only `game_dir_path` (the chosen ROM folder). |

## Format

TOML, `[Section]` tables, `key = value`. Xenia writes strings single-quoted (`gpu = 'vulkan'`); the template uses double quotes. Both parse. Adapter key = `Section/key` (e.g. `GPU/draw_resolution_scale_x`). Raw values are exactly as Xenia stores them: strings in single quotes (`'vulkan'`), numbers and `true`/`false` bare. cocoonlib's `toml` format (the ini reader/writer) reads and writes these lines as they are; it does not handle multi-line TOML values, and this file has none.

## When It Reads and Writes

- The native core opens the global file at boot (`Emulator.Config.open_config_file`). The settings screen loads it through the same native handle, changes entries and saves the whole file.
- The core also saves the global config itself (log string `SaveConfig skipped: a per-game config overlay is active`).
- `stop_before_write: true`. Edit with the app stopped; the next launch reads it.
- Keys missing from the file use core defaults. A file written by an older build lacks newer keys such as `Kernel/guest_scheduler`, `APU/apu_aaudio_buffer_bursts`, `Kernel/network_enabled` and `HID/show_touch_overlay`.

## Per-Game Settings

- Path: `compose/config/<TITLEID>.config.toml` (`D3.b.f`: `Application.b().getParentFile()/config/<id>.config.toml`).
- Id: 8-digit uppercase hex title ID (e.g. `415607D2`), shown on the game's Per-game settings screen.
- Content: sparse TOML, same sections and keys, only overridden keys. The app deletes the file when no overrides remain.
- The core loads it at that title's boot (`Loading game config: {}`, `Applied {} game config override(s)`) over the global file.
- Creating the folder and file by hand matches what the app does. Only keys in the app's settings list are offered per game; `Vulkan/vulkan_lib_path` and `HID/vibration` are global only.

## Gotchas

- Frame rate limit: core default `0` (unlimited) in the TOML; the settings screen shows 60 when the key is absent. Write the key explicitly.
- Resolution scale must be set on both `draw_resolution_scale_x` and `_y`. 2x/3x is very heavy.
- `Console/internal_display_resolution` is the mode reported to the game (default 8 = 1280x720), not the render scale.
- `Vulkan/turnip_debug = 'sysmem'` is the app default to avoid Adreno device-loss hangs.
- `[Profiles] logged_profile_slot_0_xuid` holds the profile XUID; leave it and do not print it.

## Verified On Device vs From Source

- On the test device: file paths, every key marked `verified_on_device: true`, template content, DataStore layout, no process running.
- From source: settings list, labels, enum values and ranges (`D3/u.java`), per-game path and save logic (`D3/b.java`, `D3/c.java`), native load/save messages (strings in `libe.so`). Not verified: that the core resolves the per-game path to the same `compose/config/` folder (the app writes it there; Xenia loads `<config folder>/config/`). No write tested.

## Sources

- APK `xendroid.compose` 0b11201, decompiled with jadx; `lib/arm64-v8a/libe.so` strings.
- https://www.androidauthority.com/xendroid-xbox-360-emulator-android-3699252/ , https://www.generationamiga.com/2026/08/19/xbox-360-emulation-gets-faster-on-android-with-xendroid/ (project background).
- Xenia config/cvar behaviour: https://github.com/xenia-canary/xenia-canary (src/xenia/config.cc).
