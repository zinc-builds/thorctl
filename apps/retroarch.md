# RetroArch (com.retroarch)

Adapter: `apps/retroarch.json` (35 frontend keys, 41 core-option keys across 7 cores). Checked 2026-11-27 against RetroArch 1.22.2 on an AYN Thor (Android 13) and the RetroArch source at tag **v1.22.2** (commit `69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576`).

## Checked Build

- `dumpsys package`: versionName `1.22.2 (2026-10-30)`, versionCode 1597177398. Source facts are from tag `v1.22.2`.
- RetroArch was not running during the check.
- Core option facts come from each core's `libretro_core_options.h` on its default branch (commits listed below), not from the exact core builds checked. `.opt` files written by the checked Beetle Saturn, mGBA and Gambatte cores match those sources key for key. A Flycast `.opt` written by an older core build kept 8 keys the current source no longer defines (old keys stay in the file).

## Files

| Path | What it holds |
|---|---|
| `/storage/emulated/0/Android/data/com.retroarch/files/retroarch.cfg` | Main config, every setting. Mode 660. Holds `cheevos_*` and `netplay_*` secrets. |
| `/storage/emulated/0/RetroArch/config/` | `rgui_config_directory`. Overrides, core options and auto shader presets live here, one folder per core `library_name`. |
| `config/{core}/{core}.opt` | Every option of that core. Created when the core first unloads. |
| `config/{core}/{core}.cfg`, `{contentdir}.cfg`, `{game}.cfg` | Settings overrides; each holds only the keys it changes. |
| `config/{core}/{core\|contentdir\|game}.slangp` (or `.glslp`), `config/global.slangp` | Auto-loaded shader presets. Each holds one `#reference "<path to preset>"` line. |
| `config/<core>_libretro_android.cfg` (e.g. `gambatte_libretro_android.cfg`) | A full config written by "Save New Configuration". Not an auto-loaded override; see Gotchas. |
| `config/remaps/` | Input remap files. |
| `/data/user/0/com.retroarch/cores/` | Installed cores. Cores bundled with the APK are symlinks into it; downloaded cores are `.so` files. |
| `/data/user/0/com.retroarch/shaders/shaders_slang`, `shaders_glsl` | Shader library. |

`/storage/emulated/0/Android/data/com.retroarch/files/retroarch-core-options.cfg` is used only with `global_core_options = "true"`, or to seed a missing per-core `.opt`; `core_options_path` moves it.

## Write Rules (`cfg`)

- One setting per line: `key = "value"`. Every value is double-quoted, including numbers and bools. Bools are `"true"`/`"false"`. Floats are written with 6 decimals (`fastforward_ratio = "2.000000"`). The raw values in the JSON are the text inside the quotes.
- `retroarch.cfg` lists every setting. An override `.cfg` lists only the keys it changes. A `.opt` lists every option of the core.
- Enums are integers (`aspect_ratio_index = "22"`) or driver names (`video_driver = "vulkan"`).
- Core option values must match one of the values the core declares (case-sensitive, e.g. mGBA `"OFF"`/`"GBA"`, Saturn `"Auto Detect"`). An unknown value falls back to the core default.

## When RetroArch Reads and Writes the Files

Sources: `retroarch.c` (`retroarch_main_quit`, `command_event`), `runloop.c` (core options), `configuration.c` (`config_load_override`).

- `retroarch.cfg` is read once at start-up. With `config_save_on_exit = "true"` (default), quitting through the menu (`retroarch_main_quit`, HAVE_DYNAMIC path) saves the whole in-memory config over the file. Active overrides are unloaded first, so override values do not leak into `retroarch.cfg`. An edit made while RetroArch runs is not read and is overwritten on Quit. **Force-stop RetroArch before editing `retroarch.cfg`** (`stop_before_write: true`). If the process is killed instead of quit (swipe away, force-stop), nothing is saved (from source; not tested).
- Core options are read when a core loads and written when it unloads (close content, load another core, quit). The write flushes every option from memory into the file the core used. Editing the `.opt` of a core that is loaded is overwritten; editing it while RetroArch sits in the menu with no content, or with another core loaded, is picked up at the next load of that core.
- Override `.cfg` files are read at each content load and written only when the user saves overrides from the Quick Menu. Edits to them are picked up at the next content load.
- Auto shader presets are looked up at each content load.

## Override Semantics

Source: `configuration.c` `config_load_override`, `runloop.c` `runloop_init_core_options_path`, `gfx/video_shader_parse.c`.

`{core}` is the core's `library_name` (folder name under `config/`): `Beetle Saturn`, `Mupen64Plus-Next`, `mGBA`, `Gambatte`, `Flycast`, `Genesis Plus GX`, `Snes9x`. `{game}` is the content file name without folder or extension. `{contentdir}` is the name of the folder that holds the content (for example `Saturn`).

- Settings overrides stack (needs `auto_overrides_enable = "true"`): `retroarch.cfg` < `config/{core}/{core}.cfg` < `config/{core}/{contentdir}.cfg` < `config/{core}/{game}.cfg`. Later files win. Each holds only changed keys.
- Core options do **not** stack. RetroArch uses exactly one file, the first that exists of:
  1. `config/{core}/{game}.opt` (needs `game_specific_options = "true"`)
  2. `config/{core}/{contentdir}.opt` (same switch)
  3. `config/{core}/{core}.opt` (when `global_core_options = "false"`; if missing, it is seeded from `retroarch-core-options.cfg`)
  4. `retroarch-core-options.cfg` next to `retroarch.cfg`, or `core_options_path` (when `global_core_options = "true"`)

  A per-game `.opt` must therefore hold every option the game needs. Create one by copying `{core}.opt` and editing it.
- Shader presets (needs `auto_shaders_enable = "true"`): `{game}` > `{contentdir}` > `{core}` > `global`, searched in `config/{core}/` first, then the folder of `retroarch.cfg`, then `<video_shader_dir>/presets/`. The first match wins. Each type the video driver supports is tried (`.slangp` for Vulkan, `.glslp` for GL).
- Remaps: `config/remaps/{core}/{game|contentdir|core}.rmp` (`auto_remaps_enable = "true"`).

## Network Command Interface

Sources: `command.h` (`map[]`, `action_map[]`), `command.c`.

- Off by default: `network_cmd_enable = "false"`, `network_cmd_port = "55355"`. `stdin_cmd_enable = "false"`. Enabling needs a RetroArch restart. The Android build compiles it in (`-DHAVE_NETWORK_CMD`).
- Protocol: UDP datagrams to the port, plain text, one command per datagram. Query commands (`VERSION`, `GET_STATUS`, `GET_CONFIG_PARAM`, `READ_CORE_*`) reply to the sender's address.
- It cannot change arbitrary settings. There is no `SET_CONFIG_PARAM`. `GET_CONFIG_PARAM` reads only `video_fullscreen`, `savefile_directory`, `savestate_directory`, `runtime_log_directory`, `log_dir`, `cache_directory`, `system_directory`, `netplay_nickname`, `active_replay`.
- Commands with arguments: `SET_SHADER <path>`, `VERSION`, `GET_STATUS`, `GET_CONFIG_PARAM <name>`, `SHOW_MSG` (help text says "No argument"; not checked), `READ_CORE_RAM <addr> <n>`, `WRITE_CORE_RAM <addr> <bytes…>`, `READ_CORE_MEMORY`, `WRITE_CORE_MEMORY`, `LOAD_STATE_SLOT <n>`, `PLAY_REPLAY_SLOT <n>`, `SEEK_REPLAY <frame>`, `SAVE_FILES`, `LOAD_FILES`, `LOAD_CORE <path>`.
- Hotkey commands (no argument): `MENU_TOGGLE QUIT CLOSE_CONTENT RESET FAST_FORWARD FAST_FORWARD_HOLD SLOWMOTION SLOWMOTION_HOLD REWIND PAUSE_TOGGLE FRAMEADVANCE MUTE VOLUME_UP VOLUME_DOWN LOAD_STATE SAVE_STATE STATE_SLOT_PLUS STATE_SLOT_MINUS PLAY_REPLAY RECORD_REPLAY HALT_REPLAY SAVE_REPLAY_CHECKPOINT PREV_REPLAY_CHECKPOINT NEXT_REPLAY_CHECKPOINT REPLAY_SLOT_PLUS REPLAY_SLOT_MINUS DISK_EJECT_TOGGLE DISK_NEXT DISK_PREV SHADER_TOGGLE SHADER_HOLD SHADER_NEXT SHADER_PREV CHEAT_TOGGLE CHEAT_INDEX_PLUS CHEAT_INDEX_MINUS SCREENSHOT RECORDING_TOGGLE STREAMING_TOGGLE TURBO_FIRE_TOGGLE GRAB_MOUSE_TOGGLE GAME_FOCUS_TOGGLE FULLSCREEN_TOGGLE UI_COMPANION_TOGGLE VRR_RUNLOOP_TOGGLE RUNAHEAD_TOGGLE PREEMPT_TOGGLE FPS_TOGGLE STATISTICS_TOGGLE AI_SERVICE NETPLAY_PING_TOGGLE NETPLAY_HOST_TOGGLE NETPLAY_GAME_WATCH NETPLAY_PLAYER_CHAT NETPLAY_FADE_CHAT_TOGGLE MENU_UP MENU_DOWN MENU_LEFT MENU_RIGHT MENU_A MENU_B OVERLAY_NEXT OSK SEND_DEBUG_INFO`.
- Toggles such as `FPS_TOGGLE` change the in-memory setting, which `config_save_on_exit` then writes to `retroarch.cfg` on Quit.

## Cores in the Adapter

| Core file | `library_name` / config folder |
|---|---|
| `mednafen_saturn_libretro_android.so` | Beetle Saturn |
| `mupen64plus_next_gles3_libretro_android.so` | Mupen64Plus-Next |
| `mgba_libretro_android.so` | mGBA |
| `gambatte_libretro_android.so` | Gambatte |
| `flycast_libretro_android.so` | Flycast (keys prefixed `reicast_`) |
| `genesis_plus_gx_libretro_android.so` | Genesis Plus GX |
| `snes9x_libretro_android.so` | Snes9x |

The JSON lists 5-7 options per core; every other option is in the core's `libretro_core_options.h`. Beetle Saturn needs its BIOS files (`saturn_bios.bin`, `mpr-17933.bin`, `sega_101.bin`) in RetroArch's system directory (`system_directory`, e.g. `/storage/emulated/0/RetroArch/system/`).

## Gotchas

- Keep the owner and mode of `retroarch.cfg` when replacing it, so RetroArch can still save it (mode 660, group `ext_data_rw`).
- The Run-Ahead menu entry is three keys: `run_ahead_enabled`, `run_ahead_secondary_instance`, `preemptive_frames_enable` (see the `runahead` key notes).
- `video_swap_interval = "0"` means Auto, although the source default is `1`.
- `aspect_ratio_index` 22 = Core provided. Index 10 is "9:16" in the lookup table even though the enum name is `ASPECT_RATIO_4_4`.
- `config/gambatte_libretro_android.cfg` is the file "Save New Configuration" writes. RetroArch never loads it by itself. Not checked whether Cocoon passes it as the config file when launching Gambatte.
- Android defaults that are easy to get wrong: `video_driver` `gl`, `menu_driver` `glui`, `menu_swap_ok_cancel_buttons` `true`, `input_overlay_enable` `true`, `savestate_auto_save`/`_load` `false`.
- Secrets: `cheevos_password`, `cheevos_token`, `cheevos_username`, `netplay_password`, `netplay_spectate_password`, `netplay_nickname` and similar. Never print them.

## Verified on Device vs From Source

- On the test device: paths, owners and modes; every frontend key in the JSON exists in `retroarch.cfg` (35/35); core `library_name` folders; core-option keys for the cores that had an `.opt` (24 of 41); the override and shader preset file formats.
- From source only: defaults, value ranges, enum meanings, UI labels (`intl/msg_hash_us.h`), save/load timing, override and core-option precedence, network command list. Core option labels, values and defaults come from core source at the commits below. No write was tested (read-only task).

## Sources

- https://github.com/libretro/RetroArch/tree/v1.22.2 (commit `69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576`): `configuration.c`, `config.def.h`, `retroarch.c`, `runloop.c`, `command.c`, `command.h`, `menu/menu_setting.c`, `intl/msg_hash_us.h`, `gfx/video_defines.h`, `gfx/video_driver.c`, `gfx/video_shader_parse.c`, `input/input_defines.h`, `pkg/android/phoenix-common/jni/Android.mk`
- Core options (`libretro_core_options.h`, default branch on 2026-11-27):
  - https://github.com/libretro/beetle-saturn-libretro (`7126d65b83`)
  - https://github.com/libretro/mupen64plus-libretro-nx (`6752836de8`, `libretro/libretro_core_options.h`)
  - https://github.com/libretro/mgba (`7a12d6d4b9`, `src/platform/libretro/libretro_core_options.h`)
  - https://github.com/libretro/gambatte-libretro (`b14881d382`, `libgambatte/libretro/libretro_core_options.h`)
  - https://github.com/flyinghead/flycast (`12a7f18b81`, `shell/libretro/libretro_core_options.h`)
  - https://github.com/libretro/Genesis-Plus-GX (`51348f6573`, `libretro/libretro_core_options.h`)
  - https://github.com/libretro/snes9x (`204ea1c0b8`, `libretro/libretro_core_options.h`)
