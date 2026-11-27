# The Minish Cap (dev.picori.tmc)

Adapter: `apps/tmc.json` (36 keys). Checked 2026-11-27 against v1.2 (versionName 0.8.3) on an AYN Thor and the source of [samyost1/tmc-android](https://github.com/samyost1/tmc-android) at tag **v1.2** (Thor dual-screen mod of the Project Picori PC port of [zeldaret/tmc](https://github.com/zeldaret/tmc)).

## Checked Build

- versionName `0.8.3`, versionCode 80300.
- APK SHA-256 `9f666877…424d` equals release v1.2 `tmc-dual-screen-v1.2.apk` (2026-08-19), the latest.
- Lineage: zeldaret/tmc → MatheoVignaud/tmc (PC port) → 999sian/tmc ("Project Picori") → Raekwon1603/tmc-android → samyost1/tmc-android. The native code still contains the PC port's update check against MatheoVignaud/tmc; it does not track this APK.

## Files

| Path | What it holds |
|---|---|
| `/sdcard/Android/data/dev.picori.tmc/files/config.json` | Every port setting and the input bindings. |
| `…/files/baserom.gba` | The USA ROM. `rom_data/`, `assets/`, `assets_src/` are extracted from it. |
| `…/files/tmc.sav`, `state_quick.bin`, `state_auto_0..2.bin`, `tmc.randomizer` | Save, save states, randomizer state. |

## Write Rules (`json`)

Source: `port/port_runtime_config.cpp`, `port/port_ppu.cpp`, `port/port_gpu_renderer.cpp`, `android/…/TMCLauncherActivity.java`.

- nlohmann JSON written with 4-space indent. Bools are JSON `true`/`false`, numbers bare, strings quoted (`render_backend`, `upscale_method`, `aspect_mode`, `bg_fill`, `touch_scheme`, `shader_preset`).
- On load, each key is read with its typed default (`j.value(key, def)`); a wrong type falls back to the default, and malformed JSON falls back to all defaults. Missing keys are fine.
- Enum strings are lower-cased before matching. Unknown `upscale_method` selects **xBRZ smooth**, not nearest. Unknown `render_backend` = auto, unknown `aspect_mode` = native, unknown `bg_fill` = black.
- `frame_time_ns` = 1e9 / fps; the F8 presets are 0 (uncapped, VSync off), 30, 60, 75, 90, 120, 144, 150, 240. With `decouple_render` on, game logic stays at a fixed 60 Hz.
- `window_scale` and `internal_scale` are clamped to 1-10 (out of range resets to the default).

## When the App Reads and Writes

- Read at game start (`Port_Config_Load`). Every setter updates the in-memory JSON and calls `SaveConfig`, rewriting the whole file, so stop the app before editing.
- `second_screen_swap` is also read by `TMCLauncherActivity` before the game window is created; it takes effect on the next launch.
- `render_backend` needs a restart (the swapchain owner is chosen at PPU init).

## Menus

- Port menu: Select+Start on a gamepad (F8 on a keyboard). Ribbon style by default (`ribbon_mode`).
- Bottom screen Settings tab: HIDE TOP HUD, WIDESCREEN, PANEL BACKDROP, FOLLOW CAM, MAP FOG, WINDCREST PINS, FLOOR AUTO RETURN, SWAP SCREENS, plus the port-wide toggles.

## Not in the Adapter

Randomizer options (`rando_*`), accessibility cues (`a11y_*`), TTS voice/rate/pitch, practice-mode overlays, `bindings` (edit as JSON: each input maps to a list of `SDLK:0x…`, `SDL_GAMEPAD:0x…`, `SDL_AXIS:0x…` tokens), `touch_scale`/`touch_opacity` (may be absent from the file; clamped 0.6-1.6 and 0.3-1.5), `reborn_features` (its presence overrides compiled feature defaults: leave it absent).

## Not Verified

All keys and values were read from a device file and the v1.2 source; no setting was changed and checked in game in this pass. GPU backend on the Adreno 740 not tried.
