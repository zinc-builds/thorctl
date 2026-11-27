# hakuX (com.rfandango.haku_x)

Adapter: `apps/hakux.json` (17 keys). Checked 2026-11-27 against versionName `1.3.0`, versionCode 9, installed on the AYN Thor, and the decompiled APK.

hakuX is an original Xbox emulator for arm64 Android by rfandango, a fork of X1 BOX (an Android xemu port). Its core is `libhakuxcore.so` (FEX for x86 code, Vulkan). The APK bundles 60/120 fps mods for some titles (`assets/mods/<TITLEID>.<ver>/`).

## Before First Run

Until the app is opened, `/data/data/com.rfandango.haku_x` holds only `cache/` and `code_cache/`, there is no external files folder, and no settings file exists. Everything below is from source. Open it once (setup picks the games folder and HDD) before any adapter write.

## Files

| Path | Role |
|---|---|
| `/data/data/com.rfandango.haku_x/shared_prefs/x1box_prefs.xml` | Global settings (SharedPreferences, name kept from X1 BOX). |
| `/data/data/com.rfandango.haku_x/shared_prefs/per_game_settings.xml` | Per-game overrides, all `<string>`. |
| `/data/data/com.rfandango.haku_x/files/native/hdd/` | Emulated hard disk. |
| `/data/data/com.rfandango.haku_x/files/gpu_driver/` | The one installed custom Vulkan driver (`meta.json` + `.so`), installed from `/sdcard/Android/data/com.rfandango.haku_x/files/gpu_drivers/` in the UI. |

## When It Reads Settings

`NativeCoreActivity` reads the prefs at each game launch and passes them to the core as arguments: `scale=N`, `aspect=`, `fxaa=0|1`, `upscale=`, `video=<hex bitmask>` (widescreen 0x10000, letterbox 0x100000, 720p 0x20000, 1080i 0x40000, 480p 0x80000, PAL60 0x400000), `avpack=`, `lang=<1-9>`, `asyncpipe=`, `prebuild=`, `uncap`, `net=`. `show_fps` is read when the game screen resumes. Prefs are cached in the process, so `stop_before_write: true`.

## Per-Game Settings

- File: `per_game_settings.xml`. Key: `<game>/<setting>`.
- Game id: `%08X.%d`, title ID from the disc's XBE certificate plus XBE version, e.g. `4D530004.9`. Discs without a readable id use `path:<relative path>`.
- Settings: `uncapped`, `render_scale`, `async_shaders`, `prebuild_shaders`, `console_timing`, `aspect`, `fxaa`, `upscale`, `language`, `screen_format`, `480p`, `720p`, `1080i`, `pal60`, `av_pack`.
- Values are strings: `"true"`/`"false"`, `"2"`, or the same words as the global keys. A missing key uses the global value. Older `<TITLEID>/<setting>` keys are migrated by the app.
- The setting names differ from the global pref names (`render_scale` matches; `uncapped` ↔ `uncap_fps`, `aspect` ↔ `aspect_ratio`, `upscale` ↔ `upscale_filter`, `screen_format` ↔ `video_screen_format`, `480p` ↔ `video_480p`, `av_pack` ↔ `video_av_pack`, `language` ↔ `console_language`), so there is no single `key_map`.

## Gotchas

- `render_scale` is an `<int>` globally but a `<string>` per game.
- `console_language` `auto` uses the phone language if it is one of en/ja/de/fr/es/it/ko/zh/pt, else English.
- Network: `console_network` `insignia` uses `network_insignia_dns` (default 46.101.64.175); `kai` uses `network_kai_engine`; `lan` uses `network_lan_peers`.

## Verified On Device vs From Source

- On the test device: package and version, and that no data or settings exist before first run.
- From source: all keys, defaults, values and labels (`NativeCoreActivity`, `o4/a`, `o4/k`, `o4/m`, `b5/l0`, `res/values/strings.xml`). Nothing is `verified_on_device`.

## Sources

- APK `com.rfandango.haku_x` 1.3.0, decompiled with jadx.
- https://github.com/rfandango/hakuX (releases), https://www.androidauthority.com/hakux-original-xbox-emulator-android-3727845/
