# Banjo: Recompiled (com.aure.banjorecomp)

Adapter: `apps/banjorecomp.json` (20 keys). Checked 2026-11-27 against an install on the AYN Thor and the source of `github.com/AurelioB/BanjoRecomp-Android` (fork of `BanjoRecomp/BanjoRecomp`; RecompFrontend and N64ModernRuntime submodules at HEAD).

## Build Checked

- Checked against versionName `0.1.2`, versionCode 102, the release `android-v0.1.2` (2026-07-13).
- Before the first launch `/data/data/com.aure.banjorecomp` has only `cache` and `code_cache`. The adapter comes from source; no setting has been checked against a written file.

## Files

All under `APP_FOLDER_PATH` = `/data/data/com.aure.banjorecomp/files/data` (set by `BanjoSDLActivity`). Program assets are copied to `files/program`, GPU drivers to `files/gpu-drivers`.

| File | What it holds |
|---|---|
| `graphics.json` | Resolution, downsampling, aspect, framerate, MSAA, HUD placement, cutscene aspect, graphics API, high-precision framebuffer. |
| `general.json` | Note saving, analog camera and sensitivity, invert modes, rumble, deadzone, background input. |
| `sound.json` | `main_volume`, `bgm_volume`. |
| `controls.json` | Controller/keyboard bindings. Edit in the app. |
| `mods/`, `mod_config/`, `mods.json` | Installed mods and their settings. |
| ROM copy | Stored here after the picker import (name from the game entry). |

## Write Rules (`json`)

Source: `librecomp/src/config.cpp` (`get_storage_json`, `save_config_json`), `recompui/src/config/ui_config_tab_*.cpp`, `src/game/config.cpp`.

- Flat object, one key per option id.
- Enum options are stored as their key string (`"res_option": "Auto"`), except `ds_option`, which is stored as an integer (0, 2, 4).
- Number options with precision 0 are stored as integers (`rr_manual_value`, percent options).
- Files are written through a backup copy; a parse failure falls back to the backup.
- Missing keys take the source default.

## When It Reads and Writes

Loaded at start-up (load callback applies graphics); saved when settings change in the UI. Force-stop before editing. `api_option` and `hpfb_option` need a restart.

## Android Extras

- Settings > Graphics > Graphics Driver imports a Turnip/Vulkan driver zip; the intent extra `banjo_force_system_driver` forces the system driver.
- Settings > Save Management: import/export `banjo-kazooie.bin`, or bind a SAF folder that becomes authoritative.
- The bottom screen shows a stats companion while playing; double-tap it to turn it off.

## UI Tests Still Needed

- First launch: import the ROM (for example `/storage/<sdcard>/Roms/N64/<game>.n64`; check a byte-swapped `.n64` is accepted) and confirm the four JSON files appear in `files/data`.
- Then set `res_option`, `rr_option`=Manual + `rr_manual_value`=120 and `msaa_option` through the adapter and confirm the Graphics tab shows them.
