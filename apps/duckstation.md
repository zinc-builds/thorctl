# DuckStation (com.github.stenzek.duckstation)

Adapter: `apps/duckstation.json` (42 keys). Checked 2026-11-27 against a DuckStation install on the AYN Thor and a decompile of that exact APK. The Android app is closed source, so key names, values and UI labels come from the APK (Java with jadx, `res/xml/*_preferences.xml`, `res/values/arrays.xml`, strings in `libduckstation.so`). Core behaviour comes from the desktop source at the commit nearest the Android build date, and from the last open-source Android code (2021).

## Build Checked

- Checked against versionName `0.1-8974-g1efe969f7`, versionCode 8447 (`dumpsys package`). `libduckstation.so` carries the same version string and a build stamp of `2026-10-11T04:36:07+00:00`. It was built from a private tree (`/home/user/duckstation-android-beta`). Commit `1efe969f7` is not in `github.com/stenzek/duckstation`.
- The Android core is not the same as desktop master. For example, the Android texture filters are `Scale2x`, `Scale3x` and `MMPX`, while desktop at the same date has `MonotonicCubic`, `DCCI` and others. Use the values in the JSON (taken from the APK arrays, and each one checked as a string in the native library). Do not use desktop names.
- DuckStation was not running during the check.

## Files

| Path | What it holds |
|---|---|
| `/data/data/com.github.stenzek.duckstation/shared_prefs/com.github.stenzek.duckstation_preferences.xml` | Every global setting. Root only, owned by the app's uid. Keys are `Section/Key`, exactly as desktop `settings.ini` writes them. Also holds controller bindings (`Pad1/*` string sets with the controller's device GUID) and the `Cheevos/*` switches. |
| `/sdcard/Android/data/com.github.stenzek.duckstation/files/gamesettings/<serial>.ini` | Per-game overrides. |
| `…/files/bios/`, `memcards/`, `savestates/`, `cheats/`, `patches/`, `shaders/reshade/`, `textures/`, `inputprofiles/` | User data folders. |
| `…/files/playtime.dat` | Play time per serial, written by the app. |
| `/data/data/com.github.stenzek.duckstation/cache/gamelist.cache` | Binary game-list cache: content URI, serial and title for each game. This is the easiest place to find serials. |
| APK `assets/gamedb.yaml` | Game database: per-serial `traits` (DisableWidescreen, ForcePGXPCPUMode, ForceRecompilerICache, …), `discSet` and `settings`. These are applied on top of user settings while Apply Compatibility Settings is on. |
| APK `assets/shaders/` | Built-in GLSL post-processing shaders and the ReShade `.fx` shaders. |

## Write Rules (Global, `prefs`)

Sources: `NativeLibrary.java` and `GamePropertiesActivity.java` / `z1/e4.java` / `z1/h4.java` (jadx); `android_settings_interface.cpp` and `android_host_interface.cpp` at commit `20afc1c4` (the last open-source Android code).

- Keep each key's XML element type. ListPreferences store `<string>` even when the value is a number (`GPU/ResolutionScale` = `"5"`, `CPU/Overclock` = `"100"`, `Main/EmulationSpeed` = `"1"`). Switches are `<boolean>`. Spin boxes are `<int>` (`Audio/BufferMS`) or `<float>` (`Display/OSDScale`). The native reader calls `getString` first and falls back to `getInt`/`getFloat`. The Java preference screens throw `ClassCastException` if the type does not match. `appconf.prefs_write` already keeps the existing type. Every glossary key except `apply_game_settings` and `apply_compatibility_settings` was present in the file on the test device.
- Raw glossary values follow the schema (JSON-encoded): `"\"Vulkan\""`, `"\"5\""`, `true`, `20`.
- Two Android-only keys are converted by the native layer when settings load:
  - `GPU/MSAA` (`1`, `2`, `4`, `8`, `2-ssaa`, `4-ssaa`, `8-ssaa`) → `GPU/Multisamples` + `GPU/PerSampleShading`.
  - `CPU/Overclock` (a percentage) → `CPU/OverclockNumerator`, `OverclockDenominator` and `OverclockEnable` (on when not 100).

  Edit `MSAA` and `Overclock`. The derived keys (`GPU/Multisamples`, `CPU/OverclockEnable`, numerator and denominator) are also stored in the file.
- DuckStation ignores keys it does not know, such as a PCSX2/ARMSX2 name like `EmuCore/GS/AspectRatio`.

## When DuckStation Reads and Writes

- One process, no `android:process` split. The native core reads settings through JNI from the app's `SharedPreferences` object (`PreferenceManager.getDefaultSharedPreferences`). Android caches that object in memory for the life of the process, so an edit made on disk while the app is alive is not seen. Every settings change in the UI commits the whole file from memory, which would revert an external edit.
- **Force-stop before editing** (`stop_before_write: true`). The new values apply at the next app start.
- The app does not rewrite the prefs file just by starting or playing (the prefs file kept an older date than later `playtime.dat` and save-state writes).

## Per-Game Settings (`gamesettings/<serial>.ini`)

Sources: `z1/e4.java`, `z1/h4.java` (ini4j wrapper), `System::GetGameSettingsPath` and `System::GetGameSettingsInterface` in desktop `src/core/system.cpp` (commit `9cb25f7e`). The native library contains the same `{}.ini`, `gamesettings` and `UseSeparateConfigForDiscSet` strings.

- Plain INI: `[GPU]` then `ResolutionScale = 5`. The UI writes it with ini4j after every change in Game Properties and deletes the file when every section is empty.
- Keys are the global prefs keys split at the **last** `/`: `GPU/ResolutionScale` → `[GPU] ResolutionScale`, and `PostProcessing/Stage1/ShaderName` → `[PostProcessing/Stage1] ShaderName`.
- **Values are plain text, without the JSON quotes the glossary uses for prefs strings.** Write `Renderer = Vulkan`, not `"Vulkan"`. Bools are written `true`/`false`; `yes`, `enabled` and `1` are also read as true. The adapter's per-game path currently passes the prefs-style raw value through, so `thorctl` must strip the quotes for this file (parent to add).
- A missing key means "use the global value". The per-game tri-state switches remove the key when set back to global.
- The native core reads the file from disk when a game boots, so a hand-made file works (`create: true`). It needs `Main/ApplyGameSettings` = true, which is the default.
- Multi-disc sets listed in `gamedb.yaml` use the **first disc's** serial for every disc, unless that file contains `[Main] UseSeparateConfigForDiscSet = true`. In that case each later disc reads `<its serial>.ini`.
- The Game Properties UI shows the keys marked `per_game` in the JSON (from `*_game_settings_preferences.xml`). The core reads any core key from the file.
- Game database traits still apply after per-game settings while Apply Compatibility Settings is on. Example: Chrono Cross has `DisableWidescreen`, so a widescreen override does nothing for it unless `apply_compatibility_settings` is false.

### Finding a Game's Serial

Read serials from the game-list cache: `adb shell su -c 'cat /data/data/com.github.stenzek.duckstation/cache/gamelist.cache' | grep -aoE 'S[CL][UEP][SM]-[0-9]{5}'`. The game must be scanned once in the app first.

## Gotchas

- `GPU/Renderer`: the preference XML default is `OpenGL`, but the core default is `Automatic`. A renderer change takes effect at the next game start.
- Widescreen needs two settings: `widescreen_hack` true, plus `aspect_ratio` `16:9` or `20:9`. The Thor's panel is about 20:9 (not checked against the panel resolution). With `Auto (Game Native)` the image stays 4:3.
- PGXP sub-options do nothing unless `GPU/PGXPEnable` is true. They only work with hardware renderers.
- `Main/EmulationSpeed` values are strings. The app's own 400% entry is `4.` with a trailing dot.
- Post-processing: `PostProcessing/Enabled` (bool), `PostProcessing/StageCount` (int), and `PostProcessing/Stage<N>/ShaderName` (string). Shader options are stored as `PostProcessing/Stage<N>/<Option>`. Example shader name: `dolphinfx/crt/CRT-HYLLIAN`. To add a stage, also raise StageCount.
- Controller bindings are `<set>` string sets. Do not edit them with a scalar write.

## Verified on Device vs From Source

- Checked on the test device: package version, paths and owners; the full prefs file, with all 40 glossary keys that are present and their XML types; the `gamesettings/` folder; reading serials from `gamelist.cache`; and that `thorctl app get duckstation …` resolves the keys, including `--game <serial>` for a game with no per-game file (global values show).
- Absent from the prefs file on the test device (`verified_on_device: false`): `Main/ApplyGameSettings`, `Main/ApplyCompatibilitySettings`. Both default to true.
- From the APK: UI labels, allowed values, which keys are per-game, the per-game ini writer, the game database and the shader list.
- From source, not tested on the closed build: when settings are read, and the `MSAA`/`Overclock` conversion (2021 open-source Android code). Also the per-game load path, the first-disc rule and the ReShade shader naming (desktop commit `9cb25f7e`).
- No write was made (read-only task).

## Needs a UI-Driven Test

1. Force-stop the app, change `GPU/ResolutionScale` in the prefs file, start the app, and confirm Settings > Graphics shows the new value and a game renders at it.
2. Create `gamesettings/<serial>.ini` by hand with `[GPU]` / `ResolutionScale = 2`. Boot that game and confirm with Show Resolution. Then open Game Properties and confirm it shows the override.
3. Set `CPU/Overclock` = `"200"` only, and confirm the overclock takes effect, which shows that the native layer still converts the percentage.
4. Multi-disc: put a setting in the first disc's `<serial>.ini` (Chrono Cross: `SLUS-01041.ini`) and boot disc 2. Confirm it applies.

## Sources

- APK: `/data/app/~~<random>/com.github.stenzek.duckstation-<random>/base.apk` + `split_config.arm64_v8a.apk`, versionName `0.1-8974-g1efe969f7`.
- https://github.com/stenzek/duckstation/tree/9cb25f7e9861e8a77e43a8abf13497a47c91a844 (2026-10-10, the closest public commit to the 2026-10-11 Android build): `src/core/settings.cpp`, `settings.h`, `system.cpp`, `src/util/postprocessing.cpp`.
- https://github.com/stenzek/duckstation/tree/20afc1c4 `android/app/src/cpp/android_settings_interface.cpp`, `android_host_interface.cpp` (last open-source Android code, 2021-06-07).
