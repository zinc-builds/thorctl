# Majora ReMasked (io.github.otpr26.dekuifork)

Adapter: [majoraremasked.json](majoraremasked.json) (24 keys). Checked 2026-11-27 against **0.4.4** (versionCode 34311419) on the AYN Thor. Source: <https://github.com/OTPR26/ReMasked> (GPL-2.0; formerly OTPR26/DekUI-Fork, a fork of tgacquin/mm3d-dekui).

Majora's Mask 3D runs in an embedded, adapted Azahar (3DS emulator); DekUI adds single-screen HUD, 60 FPS interpolation, camera and gameplay options. It is not a recompilation.

## Files

Both files are created on first start.

| id | Path | Format |
|---|---|---|
| config | `<root>/config/config.ini` | Azahar INI (ini4j), bools `true`/`false` |
| presentation | `<root>/config/mm3d-local/presentation.json` | JSON object, must keep `"version": 1` |

`<root>` (`DekuiStorage.root`) is `/sdcard/mm3dport` once `shared_prefs/dekui-storage.xml` has `shared-v1 = true` (needs All files access; the General page says "Game data: Internal storage/mm3dport"), else `/data/data/io.github.otpr26.dekuifork/files/dekui`. The adapter uses `/sdcard/mm3dport`; confirm after the first start.

## Sources

- `DekuiSettingsActivity`: pages, labels, keys, defaults and ranges (`bool(label, key, default)`, `number(label, key, default, min, max, step)`, `graphics()`).
- `DekuiPresentationStore`: the JSON path and version check.
- `SettingsFile`, `IntSetting`, `BooleanSetting`: the config.ini sections and defaults; key names from `libcitra-android.so` strings; value labels from `res/values/arrays.xml`.

## Frame Rate Mode

The Graphics page shows three buttons that write two JSON keys:

| Button | interpolation_60fps | interpolation_cpu_vertices |
|---|---|---|
| Original 30 FPS | false | (unchanged) |
| 60 FPS CPU interpolation (default) | true | true |
| 60 FPS GPU interpolation | true | false |

Picking a 60 FPS mode also sets `Renderer/use_vsync = true` and `Renderer/use_hw_shader = true` in config.ini.

## Write Rules

Stop the app first: the settings screen and the in-game menu share these files and save on every change.

## Needs a UI Test

First start (storage mode and real paths), and what Azahar shows on the Thor's bottom screen (`Layout/secondary_display_layout`, default 4).
