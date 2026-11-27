# Dusklight (dev.twilitrealm.dusk)

Adapter: `apps/dusklight.json` (30 keys). Checked 2026-11-27 against an install on the AYN Thor (Android 13) and the Dusklight source at tag **v2.0.2** (`github.com/TwilitRealm/dusklight`).

## Build Checked

- Checked against versionName `2.0.2`, versionCode 20002000 (release APK `Dusklight-v2.0.2-android-arm64.apk`). Upstream has v2.0.3 (2026-09-30).
- The config read was written after the **Dusklight** preset was applied (`backend.wasPresetChosen = true`).

## Files

| Path | What it holds |
|---|---|
| `/data/data/dev.twilitrealm.dusk/files/config.json` | Every setting (`video.*`, `audio.*`, `game.*`, `backend.*`, `actionBindings.*`). Root only. |
| `.../files/USA/Card A/01-GZ2E-gczelda2.gci` | Save (GCI folder memory card). |
| `.../files/Odin Controller_2020_0111.controller`, `controller_ports.dat`, `keyboard_bindings.dat` | Binary controller maps. Edit in the app. |
| `.../files/bundled_mods/*.dusk`, `mod_cache/` | Cosmetics, Luau runtime, randomizer mods. |
| `.../files/texture_replacements/` | Texture packs. |
| `.../files/pipeline_cache.db`, `dawn_cache.db` | Shader/pipeline caches. |
| `.../files/logs/dusklight-*.log` | Run logs. |

## Write Rules (`json`)

Sources: `src/dusk/settings.h`, `settings.cpp`, `config.cpp`, `config_var.hpp`, `ui/settings.cpp`, `ui/graphics_tuner.cpp`, `ui/preset.cpp`.

- One flat object. Each key is the full dotted name as a single key (`"game.bloomMode": 2`), not nested.
- Enums are integers; bools are JSON bools; floats plain numbers. Enum values outside the range are clamped to the default on load (`sanitizeEnumValue`).
- Only values that were set are written. A missing key means the source default; a key set to its default stays in the file.
- `game.enableFrameInterpolation` also accepts an old bool (`true` = Unlimited).
- Saved atomically through `.config.json.tmp`.

## When Dusklight Reads and Writes the File

Read once at start-up. The app rewrites the whole file when a setting changes, so force-stop it before editing. Backend changes (`backend.graphicsBackend`) need a restart. Command-line overrides can also be passed: `am start -n dev.twilitrealm.dusk/.DuskActivity --es borealis_args "..."` (not tested).

## Presets

`ui/preset.cpp` has two presets. **Classic**: lock aspect, bloom and DoF Classic, internal resolution 1x, shadows 1x, GameCube menu scaling, no toasts, no menu pointer. **Dusklight**: Unlimited frame interpolation, internal resolution Auto, shadows 4x, bloom/DoF Dusklight, gyro aim, autosave, instant saves, many QoL toggles.

## UI Tests Still Needed

- Confirm the Graphics Backend list on the Thor (expected Auto, Vulkan, OpenGL ES).
- Change Internal Resolution to 2 and Frame Interpolation to Capped with a 120 cap through the adapter, start the game, and check the tuner shows the new values.
