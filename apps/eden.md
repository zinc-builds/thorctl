# Eden (dev.eden.eden_emulator)

Adapter: `apps/eden.json`. Checked 2026-11-27 against an Eden install on the AYN Thor (Android 13) and the Eden source at tag `v0.2.1`.

## Build Checked

- Checked against versionName `1f6734c`, versionCode 32873047 (from `dumpsys package`).
- `1f6734c` is not a commit or ref in `git.eden-emu.dev/eden-emu/eden`, so it is probably a CI build id. The APK's `libyuzu-android.so` contains `Eden v0.2.1`, and the keys this build writes to a per-game file match the `v0.2.1` settings list. Master changed some keys afterwards: `rescale_hack` was removed on 2026-10-08, and `frame_gen*`/`post_shader*` were added. All source facts below come from tag **v0.2.1** (commit `58c1e20ee`, 2026-06-01). Rerun this check after any Eden update.

## Files

| Path | What it holds |
|---|---|
| `/sdcard/Android/data/dev.eden.eden_emulator/files/config/config.ini` | Every emulator setting (global), in Qt INI form. Owner `<app uid>:ext_data_rw` (`u0_a<N>`), mode 660, label `media_rw_data_file`. |
| `/sdcard/Android/data/dev.eden.eden_emulator/files/config/custom/<TITLEID>.ini` | Per-game overrides, one file per game. |
| `/sdcard/Android/data/dev.eden.eden_emulator/files/gpu_drivers/*.zip` | Driver zips imported through the Driver Manager. |
| `/data/data/dev.eden.eden_emulator/files/gpu_driver/{meta.json,vulkan.freedreno.so}` | The extracted driver Eden loads. Root only. |
| `/data/data/dev.eden.eden_emulator/shared_prefs/dev.eden.eden_emulator_preferences.xml` | Game list cache and UI state only (games, last played, sort, first launch). It holds no emulator settings. |

The adapter has no `files/gpu_driver/meta.json` path. That file is at `/data/data/.../files/gpu_driver/meta.json`, and `/sdcard/Android/data/.../files/` has `gpu_drivers/` (the zips), not `gpu_driver/`.

## Write Rules (Global, `qtini`)

Source: `src/frontend_common/config.cpp`, `ReadSettingGeneric` (line 912), `ReadBooleanSetting` (line 717), `WriteSettingGeneric` (line 939).

- Every saved setting is two lines: `key\default=true|false` and `key=value`.
- On read, a missing `key\default` counts as **true**. When `\default` is true, Eden ignores the value line and uses the built-in default.
- To set a value, write both `key\default=false` and `key=<raw>`. Writing only `key=<raw>` does nothing.
- To revert to the default, set `key\default=true`. The value line can stay; Eden rewrites it on the next save.
- On save, Eden recomputes `\default` as `value == default`. A value that equals the default is written back as `\default=true`, which has the same effect.
- Bools are parsed with `input == "true"`, so write lowercase `true`/`false` only. Enums are written as integers. Ranged settings are clamped (for example `cpu_ticks` 77–65535, `volume` 0–200, `speed_limit` 0–9999). An unparseable value falls back to the default.
- Spaces in section names become `%20`, as in `[Data%20Storage]`. Paths use `/`, and the reader strips `"` quotes. Lines have no spaces around `=`.
- Keys from older versions stay in the file because SimpleIni keeps everything it loaded, and they are ignored. A file carried over from older builds can still have `shader_backend`, `use_fast_gpu_time`, `use_fast_cpu_time`, `frame_skipping`, `enable_raii` and others that v0.2.1 does not read.

## Override Semantics (Per-Game, `qtini-game`)

- Only `SwitchableSetting`s are read from a per-game file. Each glossary key marked `per_game` is listed in a per-game file this build wrote. The `[Overlay]`, `[Android]` and `[UI]` keys are global only.
- On read, a missing `key\use_global` counts as **true**, which means the global value is used.
- When `use_global=false`, Eden applies the same `\default` rule as in the global file. A per-game override therefore needs **three** lines:

  ```
  key\use_global=false
  key\default=false
  key=<raw>
  ```

  With `use_global=false` and a missing or true `\default`, the game gets the **built-in default**, not the global value and not the written value.
- To revert to global, set `key\use_global=true`. The other lines can stay, and Eden stops writing them.
- Per-game files the app wrote on the test device show its own format: `use_docked_mode\use_global=false`, `use_docked_mode\default=true`, `use_docked_mode=0`.

### Gap in `cocoonlib`

`cocoonlib/appconf.py` `qt_write(..., "use_global")` writes only `key\use_global=false` and `key=value`. If the per-game file has no `key\default` line, or it holds `true`, Eden applies the built-in default instead of the value. The `qtini-game` writer must also write `key\default=false`, and `qt_read` should report `(default)` when `use_global=false` and `\default` is true. This is not fixed yet (outside this research task).

## When Eden Reads and Writes the Files

Sources: `DirectoryInitialization.kt:26`, `native_config.cpp`, `android_config.cpp`, `EmulationFragment.kt:292-340`.

- **Global.** `initializeGlobalConfig()` runs once when the app process starts. It loads `config.ini` into an in-memory SimpleIni object, reads it, and immediately writes it back (`Config::Reload` = read + save). Later `reloadGlobalConfig()` calls re-read the **in-memory** copy, not the disk. `saveGlobalConfig()` overwrites the file with the in-memory values. It runs from the settings screens, the in-game menu (overlay toggles, control edits), the Driver Manager, the game list and others. An edit made while the process is alive is never read, and the next save erases it. **Force-stop Eden before editing, and the edit takes effect at the next cold start** (`stop_before_write: true`).
- **Per-game.** `initializePerGameConfig()` builds a fresh config object from disk each time it runs, then rewrites the file. It runs at game launch, on the per-game settings screen and in the Driver Manager. A per-game edit is therefore picked up at the next launch of that game even if the process is alive, as long as that game's settings screen is not open. Stopping the app first is still safest.
- **Launch path decides whether the per-game file is used.**
  - Game list tap: `GameAdapter.kt:271` passes `custom=true`. Eden loads the per-game file and creates it if it is missing.
  - External intent with a ROM URI (how a frontend such as Cocoon launches): the per-game file is used **only if it already exists**. Otherwise Eden uses global settings.
  - Intent action `dev.eden.eden_emulator.LAUNCH_WITH_CUSTOM_CONFIG` with extras `title_id` and `custom_settings` (full INI text): Eden **overwrites** `custom/<TITLEID>.ini` with that text and launches (`CustomSettingsHandler.kt`). I have not tested it.

## Per-Game File Naming and Creation

- Name: `{:016X}` of the program ID (16-digit uppercase hex, e.g. `01001234ABCD0000.ini`), from `native_config.cpp:56` and `Game.settingsName`. Homebrew with program ID 0 uses the ROM file name with its extension (`<file>.nro.ini`).
- Eden creates the file whenever it loads per-game config for a game: on a game-list launch, on opening the game's properties or settings, or in the Driver Manager for that game. Every key then gets `use_global=true`.
- We can create the file ourselves. Eden reads any file at that path, missing `use_global` lines count as true, and Eden fills in the rest on its next save. A minimal file needs only the sections and keys being overridden, each with the three lines above.

## GPU Driver Selection

Sources: `GpuDriverHelper.kt`, `DriverViewModel.kt:218` (`onLaunchGame`).

- The choice is stored in `config.ini` as `[GpuDriver] driver_path`, which is per-game switchable. It is neither the prefs XML nor `meta.json`.
  - Empty or default means the system driver.
  - Otherwise it is the absolute path of a zip in `gpu_drivers/`, written as `driver_path\default=false`, `driver_path=/storage/emulated/0/Android/data/dev.eden.eden_emulator/files/gpu_drivers/<driver>.zip`.
- At each game launch, Eden reads `meta.json` inside the selected zip and compares it with `/data/data/.../files/gpu_driver/meta.json`.
  - If they differ, Eden deletes `files/gpu_driver/` and extracts the zip there.
  - If the zip is missing or has no name, Eden installs the system driver.
  - If a selected zip has no readable `meta.json` with a `name`, Eden **deletes the zip** (`installCustomDriver`). Point `driver_path` only at zips that work in the Driver Manager.
- The installed `meta.json` holds the driver's `name` and `libraryName` (for Turnip builds, `vulkan.freedreno.so`). It matches the zip named by `driver_path`.
- To switch drivers by file, copy the zip into `gpu_drivers/` (keep its owner and label) and set `driver_path` to its `/storage/emulated/0/...` path. A per-game driver uses the three-line per-game form in `[GpuDriver]`.

## Gotchas

- **Docked mode.** In the core, `use_docked_mode` is the enum `ConsoleMode {0=Handheld, 1=Docked}`, and the core checks `== 1`. The Android toggle reads and writes it through `getSetting<bool>` over JNI (`BooleanSetting.kt:23`, `native_config.cpp`). A global file can hold a garbage value such as `use_docked_mode=3019898881` (0xB4000001) with `\default=false`. From the source, the core treats that value as **not docked** while the Android toggle probably shows Docked on. I did not check this at runtime. Write `0` or `1` only. If player 1's controller type is Handheld (`[Controls] player_0_type=4`), docked mode is forced off. `player_0_type=0` is Pro Controller.
- **NVDEC.** The Android menu writes `3` for "None", but the core treats only `0` as Off, so `3` decodes on the CPU. Write `0` to turn decoding off.
- **Scaling filter labels.** The Android menu lists 8–12 as MMPX, Zero-Tangent, B-Spline, Mitchell, Spline-1. The core enum is 8=ZeroTangent, 9=BSpline, 10=Mitchell, 11=Spline1, 12=Mmpx. The glossary follows the core, which is what renders.
- **Keys with no Android menu entry.** `astc_recompression`, `frame_pacing_mode`, `use_multi_core`, `use_vulkan_driver_pipeline_cache`, `vulkan_device`, `enable_compute_pipelines` and `barrier_feedback_loops` are still read by the core on Android. Their glossary labels come from the desktop UI (`qt_common/config/shared_translation.cpp`).
- **Platform defaults.** These Android defaults differ from desktop: `gpu_accuracy` 0, `max_anisotropy` 1, `fsr_sharpening_slider` 0, `use_asynchronous_gpu_emulation` false, `use_reactive_flushing` false, `dyna_state` 0, `vertex_input_dynamic_state` false, `rescale_hack` true, `use_docked_mode` 0, `cpu_backend` 1 (NCE).
- **Path aliases.** `/sdcard/...` and `/storage/emulated/0/...` are the same storage (`/data/media/0/...` underneath). The labels are `media_rw_data_file` with category `c<N>,c256,c512,c768`. Writes need root and must keep the owner (the app uid, `u0_a<N>`), group `ext_data_rw`, mode 660 and the label.
- **Settings reset.** Eden's "Reset settings" deletes `config.ini` or the per-game file and recreates it from defaults.

## Verified on Device vs Taken From Source

Verified on device by read-only adb and root reads:
- Package version, file paths, owners, modes and SELinux labels.
- Every glossary key exists in `config.ini` with a `\default` line (`verified_on_device: true` for all 40).
- The per-game key list, from a per-game file written by this build.
- The three-line per-game format the app writes, using `use_docked_mode`.
- `driver_path` and the installed `meta.json`.
- The prefs contents.
- Stale keys staying in the file.
- Eden was not running at check time.

Taken from source, not tested on device:
- What each enum value means.
- Defaults.
- The read-time `\default`/`\use_global` logic.
- When Eden reads and saves the files.
- Launch paths that use or ignore the per-game file.
- The driver re-extraction at launch.
- The NVDEC, scaling-filter and docked-mode mismatches.
- The `LAUNCH_WITH_CUSTOM_CONFIG` intent.

I made no writes and launched nothing, so no edit has been round-tripped through the app yet.

## Sources

Eden source, tag v0.2.1 (`58c1e20ee`): https://git.eden-emu.dev/eden-emu/eden/src/tag/v0.2.1
- `src/frontend_common/config.cpp`: read, write and reload logic.
- `src/common/settings.h`, `src/common/settings_enums.h`, `src/common/settings_setting.h`: keys, defaults, ranges, enums, parsing.
- `src/android/app/src/main/jni/{native_config.cpp,android_config.cpp,android_settings.h}`: JNI bridge, Android-only settings, per-game file name.
- `src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/EmulationFragment.kt`: config choice at launch.
- `.../utils/{DirectoryInitialization.kt,GpuDriverHelper.kt,CustomSettingsHandler.kt}`, `.../model/{DriverViewModel.kt,Game.kt}`, `.../adapters/GameAdapter.kt`, `.../features/settings/utils/SettingsFile.kt`.
- `.../features/settings/model/view/SettingsItem.kt`, `.../features/settings/model/{IntSetting,BooleanSetting,ShortSetting,ByteSetting,StringSetting}.kt`, `src/android/app/src/main/res/values/{strings.xml,arrays.xml}`: Android labels and menu values.
- `src/qt_common/config/shared_translation.cpp`: desktop labels for keys with no Android menu entry.
- Master commit `67bada77f` (2026-10-08): removed `rescale_hack`.
- Eden CI layout: https://github.com/Eden-CI/Workflow (`.ci/config/fj.json`).
