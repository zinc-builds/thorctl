# ARMSX3 (com.armsx3)

Adapter: `apps/armsx3.json` (61 keys). Checked 2026-11-27 on an AYN Thor against versionName `1.6.7`, versionCode 114, and the decompiled APK (jadx).

ARMSX3 is an RPCS3 (PS3) port built on the ARMSX2 Android app. It keeps ARMSX2's settings model, so its settings live in a prefs file named `ARMSX2.xml`, not in RPCS3's YAML. The YAML files are outputs.

## Files

| Path | Role |
|---|---|
| `/data/data/com.armsx3/shared_prefs/ARMSX2.xml` | Source of truth. `config.global` (JSON), `config.game.<SERIAL>` (sparse JSON), `config.coreOverrides` and `config.coreOverrides.game.<SERIAL>` (raw RPCS3 overrides), `configDb.ignore.<SERIAL>`, library cache, touch layout, play time. Root only. |
| `/sdcard/Android/data/com.armsx3/files/config/config.yml` | RPCS3 global config. Written by the native core from what ARMSX3 pushes; do not edit. |
| `.../config/config_db/<SERIAL>.yml` | Community per-game configs (2288 files when checked) downloaded from `https://api.rpcs3.net/config/?api=v1`, plus ~60 built-in ARMSX3 fixes. Replaced wholesale on refresh. |
| `.../config/config_db_user/<SERIAL>.keys` | Written at boot: config_db keys the user overrode for that game, so the DB does not apply them. |
| `.../config/input_configs/global/Default.yml`, `.../config/patches/armsx3_patch.yml` | Pad mappings, patches. |
| `/data/data/com.armsx3/files/drivers/<id>/` | Installed GPU drivers, one directory per driver. Ids look like `purpleturnip-vturnip_mrpurple_t30-toasted.adpkg-turnip_mrpurple_t30-toasted.adpkg` (Mr. Purple T30) or `local-<number>` for a driver imported from a file. |

There is no `custom_configs/config_<SERIAL>.yml` as in desktop RPCS3.

## How Settings Reach The Core (k07.c, ym6, xm6.Q, pa1.h)

At each game boot (and after settings changes) ARMSX3:

1. Merges `config.global` with `config.game.<SERIAL>` key by key.
2. Pushes each value to the native core with `settingsSet("Section@@Key", yamlScalar)`. Enum keys are indexes that ARMSX3 converts to RPCS3 strings (lists in the JSON). The native core then writes `config.yml`.
3. Forces `Video@@Vblank Rate = 60` and `Core@@SPU GETLLAR Busy Waiting Percentage = 100`.
4. Applies hard-coded game fixes (class `xt2`).
5. Replays `config.coreOverrides` then `config.coreOverrides.game.<SERIAL>` (game wins).
6. Writes `config_db_user/<SERIAL>.keys`.

The community `config_db/<SERIAL>.yml` also applies to the game unless the user turned keys off (`configDb.ignore.<SERIAL>`) or overrides them; its order relative to step 2 was not traced.

Device check: `config.global` values matched `config.yml` exactly on the test device. Mappings seen: Resolution index 2 = `1280x720`, `upscaleFloat` 1 = `Resolution Scale: 100`, `ps3ShaderMode` 1 = `Async Recompiler (multi-threaded)`, `ps3SpuXFloat` 1 = `Approximate`, `ps3AudioRenderer` 4 = `Oboe`, `fpsLimit` 0 = `Frame limit: Auto`, `aspectRatio` 1 = 16:9 with Stretch false).

## Write Rules

- Keys use the `#`-JSON-path convention: `config.global#ps3ShaderMode`. Raw values are JSON scalars (`1`, `true`, `"vulkan"`, `1.5`).
- `config.global` also carries PS2-era keys inherited from ARMSX2 (eeCycleRate, mtvu, GS hacks...). The PS3 core ignores them, except `renderer`, `customDriverId`, `upscaleFloat`, `fpsLimit`, `frameLimitEnable`, `aspectRatio`, `audioVolume`, `audioMuted`, `affinityMode`, which ARMSX3 maps to RPCS3.
- `ps3ResolutionScale` is saved but not applied. Internal resolution is `upscaleFloat` (1.5 = 150%).
- `config.coreOverrides*` maps any RPCS3 YAML path (sections joined with `@@`, e.g. `Video@@Vulkan@@VRAM allocation limit (MB)`) to a YAML scalar string. String values keep their YAML quotes inside the JSON string: `{"Video@@Shader Precision":"\"Low\""}`. Booleans and numbers are bare: `"false"`, `"60"`. This is the way to set an RPCS3 key ARMSX3 has no field for.
- `stop_before_write: true`. The app holds prefs in memory and rewrites the file on every change.

## Per-Game Settings

- Id: PS3 serial (four letters and five digits), as listed in `gamesCache`.
- `config.game.<SERIAL>`: sparse JSON with the same key names as `config.global` (`key_map` `config.global#` → `config.game.{game}#`). Example: `config.game.<SERIAL> = {"renderer":"vulkan","customDriverId":"purpleturnip-...T30..."}`.
- `config.coreOverrides.game.<SERIAL>`: raw RPCS3 overrides for one game.
- Create a missing entry as a `<string>` holding `{}`. Delete a key to fall back to global.
- Do not edit `config_db/*.yml`: refreshes delete the folder. To stop a DB key for one game, add it to `configDb.ignore.<SERIAL>` (JSON array of `Section@@Key`) or override it per game.

## Gotchas

- `renderer` values other than OpenGL/Null all become Vulkan (`auto`, `software` included).
- `fpsLimit`: -1 = PS3 Native, 0 = Auto, 30/50/60/120 = those caps; any other number sets `Frame limit: Off` plus `Second Frame Limit: N`. `frameLimitEnable: false` forces Off.
- Some per-game community configs set `Frame limit` for a game (for example `PS3 Native`). ARMSX3 strips `Frame limit: Off/Infinite` from DB entries.
- `Vblank Rate` is always forced to 60.
- Frame generation is GitHub-build only per the app's own string.

## Verified On Device vs From Source

- On a device: prefs content, every `config.global` key and value listed with `verified_on_device: true`, `config.yml` output matching them, a `config.game.<SERIAL>` entry, `config_db` contents for installed games, installed drivers, no ARMSX3 process running.
- From source: key-to-YAML mapping and enum lists (`k07.c`, `xm6.Q`, `ym6`), boot order, coreOverrides semantics (`pa1`), config_db handling (`d41`), labels (`rd3` English strings). No write was tested.

## Sources

- APK `com.armsx3` 1.6.7 (versionCode 114), decompiled with jadx: `defpackage/k07.java` (settings model, apply), `xm6.java` (YAML mapping), `ym6.java` (enum lists, frame limit, renderer), `pa1.java` (coreOverrides), `d41.java` (config_db), `rd3.java` (labels).
- RPCS3 config key names: https://github.com/RPCS3/rpcs3/blob/master/rpcs3/Emu/system_config.h
- Community config DB: https://api.rpcs3.net/config/?api=v1
