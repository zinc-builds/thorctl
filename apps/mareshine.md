# Mareshine (io.github.them3dium.mareshine)

Adapter: [mareshine.json](mareshine.json) (20 keys). Checked 2026-11-27 against **2.1.6** (versionCode 1020). Source: <https://github.com/TheM3dium/mareshine> (MIT; fork of jbcgames/sms-android). Native Super Mario Sunshine built from the decompilation; needs your own GMSE01 disc.

## File

`<data>/settings.txt`, where `<data>` is `/sdcard/Android/data/io.github.them3dium.mareshine/files` (getExternalFilesDir) unless `shared_prefs/sunshine.xml` has `data_dir`. The same folder holds `iso/` (the disc), `saves/` (memory card and shader cache), `textures/`, `languages/`, `logs/`.

Format (`Settings.java`): a header comment, then one `key = value` per line, no sections, `#` comments. The launcher rewrites the whole file from its map. The adapter marks it `other`; it reads like an INI with no section.

## Sources

`Settings.DEFAULTS` (defaults) and every `Choice`/`Toggle` in `SettingsActivity` (labels, values). `Toggle(key, label, desc, z, z2)` stores `"1"`/`"0"` with default `z xor z2`; the `disable_*` keys are shown inverted (switch On = value 0).

## Presets

The Video presets write these keys together (render_scale, frame_rate, widescreen, widescreen_hud, draw_distance, msaa, anisotropic, fxaa, disable_shadows, disable_reflections, disable_water_anim, disable_shimmer):

| Preset | Values |
|---|---|
| Recommended | 1.5, 30, 16:9, edges, 1.0, 0, 4, 0, 0, 0, 0, 0 |
| Low | 0.5, 30, 16:9, centre, 0.7, 0, 0, 0, 1, 1, 1, 1 |
| Medium | 1.0, 30, 16:9, edges, 1.0, 0, 2, 0, 0, 0, 0, 1 |
| High | 1.5, 30, 16:9, edges, 1.5, 2, 4, 1, 0, 0, 0, 0 |
| Ultra | 4.0, 60, 16:9, edges, 3.0, 8, 16, 1, 0, 0, 0, 0 |

## Write Rules

Stop the app first. Cheats and the overlay apply the next time the game starts.
