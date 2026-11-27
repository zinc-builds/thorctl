# Skies of Arcadia Legends Recomp (com.skiesofarcadia.recomp)

Adapter: [skies.json](skies.json) (27 keys). Checked 2026-11-27 against **0.83.0-beta** (versionCode 424821) on an AYN Thor. Source: <https://github.com/ogdanimal/SkiesOfArcadiaLegends-Recomp> (GPL-3.0).

## Files

| id | Path | What |
|---|---|---|
| dolphin | `/sdcard/Android/data/com.skiesofarcadia.recomp/files/Config/Dolphin.ini` | Dolphin main config plus the port's `[Skies]` section (Widescreen, Hud, FrameMode, gameplay multipliers, AutoSave, Language, Dreamcast options) |
| gfx | `.../Config/GFX.ini` | Resolution, MSAA, filtering, scaling, VSync, ShowFPS, HiresTextures |
| gcpad | `.../Config/GCPadNew.ini` | `[GCPad1]` = `Android/1/Odin Controller`; `[SkiesHotkeys]` Menu = Select, Invincible = L3 \| R3 |
| game_settings | `.../GameSettings/GEA?8P.ini` | Shipped engine hints (`StaticRecompIdlePC`, `CPUThread`). Do not edit |

`Dolphin.ini` also holds `[Analytics] ID`: do not print or copy it.

## Where the Keys Come From

The settings panel (`org.dolphinemu.dolphinemu.skies.SkiesSettingsPanel`) builds each row with `configRow(label, choices, file, section, key, default)` and writes through `NativeConfig.setInt(layer 1, …)` then `NativeConfig.save(1)`. `show()` would not decompile; it was dumped as raw code with `jadx --comments-level debug`, and every row's file, section, key, choice list and default was read from it. Choice lists (value → label) are static fields in the same class.

## Write Rules

- Stop the app first (`stop_before_write: true`): it is Dolphin-based and rewrites the inis from memory.
- `MSAA` is written as hex (`0x00000002`), bools as `True`/`False`, the rest as decimal.
- `GFX.ini` `AspectRatio = 5` and `CustomAspectRatio*` belong to the Picture setting. Leave them.

## Update to 0.94

**v0.94.0-beta** switches to a new engine on the Aurora renderer. Per its release notes: settings, saves and the data folder carry over; save states made by the new engine do not load in 0.83; the new Renderer setting replaces Dolphin's video backend settings. Recheck this adapter after updating (`version_checked` will no longer match), and back up saves first (Settings > Saves > Back up saves).

## Not Verified

`ShowFPS` and `HiresTextures` sections come from Dolphin's GFX layout; the panel passes them through a register the raw dump did not resolve. No key was changed on the test device.
