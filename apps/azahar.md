# Azahar (io.github.lime3ds.android)

Adapter: `apps/azahar.json`. Checked 2026-11-27 against an Azahar install on the AYN Thor and the Azahar source at tag `2127.0.1`.

## Build Checked

- Checked against versionName `2127.0.1-googleplay`, versionCode 34395250 (`dumpsys package`). Split APK (base + arm64 + en + xxhdpi).
- The `-googleplay` suffix is the `googlePlay` product flavor of `azahar-emu/azahar` (`src/android/app/build.gradle.kts`), which keeps the old Lime3DS application id. It differs from `vanilla` only in UI around updates and permissions (`BuildUtil.isGooglePlayBuild`) and in how external launch intents open the ROM (`GameHelper.getGameFromIntent`). Settings code is the same.
- The log at `/sdcard/Azahar/log/azahar_log.txt` names the build that last ran (`Azahar Version: ...`). See "First Launch After the Update".

## Files

| Path | What it holds |
|---|---|
| `/sdcard/Azahar/config/config.ini` | Every emulator setting (global). Plain INI. |
| `/sdcard/Azahar/config/custom/<TITLEID>.ini` | Per-game overrides. The app creates `custom/` on the first per-game save. |
| `/sdcard/Azahar/gpu_drivers/*.zip` | Driver zips imported in the Driver Manager (for example Mr. Purple Turnip `*.adpkg.zip` builds). |
| `/data/data/io.github.lime3ds.android/files/gpu_driver/{meta.json,vulkan.purple.so}` | The extracted driver Azahar loads (`meta.json` names it and its `driverVersion`). Root only. |
| `/data/data/io.github.lime3ds.android/shared_prefs/io.github.lime3ds.android_preferences.xml` | No emulator settings. User folder URI, ROM folder, game list cache, legacy input mappings, overlay positions. |
| `/sdcard/Azahar/states/<TITLEID>.<slot>.cst`, `/sdcard/Azahar/load/textures/<TITLEID>/`, `/sdcard/Azahar/shaders/{opengl,vulkan}/` | Save states, texture packs, shader caches. |

The user folder is chosen with the system folder picker. With the usual choice the prefs hold `CITRA_DIRECTORY=content://com.android.externalstorage.documents/tree/primary%3AAzahar`, which is `/sdcard/Azahar`. Nothing settings-related is in `/sdcard/Android/data/io.github.lime3ds.android/`; that folder was absent on the test device.

### Ownership

Files under `/sdcard/Azahar` belong to MediaProvider, not to Azahar. On disk (`/data/media/0/Azahar/config/config.ini`) the owner is MediaProvider's uid (`com.android.providers.media.module`, `u0_a<N>` on the test device), group `media_rw`, mode 660, label `u:object_r:media_rw_data_file:s0:c<N>,c256,c512,c768` (category numbers follow the MediaProvider uid). Azahar itself has its own app uid and reaches the folder only through SAF. Write as root through the `/sdcard/Azahar/...` FUSE path: FUSE then sets the owner and label, and a new file in `config/custom/` gets the same owner automatically. Writing to `/data/media/0/...` directly requires copying owner, mode and label by hand.

## Format (Global and Per-Game)

There are no Qt `\default` or `\use_global` flags. Azahar Android stores settings in plain INI, and two readers use the file:

- **Native core** (`jni/config.cpp`, inih `INIReader`) reads `[Section]` + key. A key in the wrong section is ignored. An empty value (`key =`) or a missing key gives the default. Section and key names are case-insensitive. Bools accept `true/false/1/0/yes/no/on/off`.
- **Kotlin settings layer** (`features/settings/utils/SettingsFile.kt`) reads every `key = value` line **regardless of section**. It skips empty values, and the last non-empty value in the file wins. It writes with ini4j `Wini`, which produces `key = value` lines with spaces around `=` and keeps comments and unknown keys.

Write rules:

- Write `key = value` under the exact section shown in the glossary. Bools as `true`/`false`, enums and ints as integers, floats as decimals (`2.25`, `1.0`).
- To reset a key to its default, make the value empty (`key =`) or delete the line.
- **Never put the same key twice in one section.** inih joins duplicates with a newline (`"1\n2"`), the number parse then fails and the core falls back to the default.
- The shipped default file (`jni/default_ini.h`) puts many layout keys under `[Storage]`, such as `screen_gap`, `small_screen_position`, `custom_*`, `screen_orientation`, `portrait_layout_option`, `swap_screen`, `secondary_display_layout` and `performance_overlay_position`. The core reads them only from `[Layout]`, and the app saves them to `[Layout]`. So a `config.ini` created from the default file has both an empty copy in `[Storage]` and the real value in `[Layout]`. Leave the `[Storage]` copies empty, because the Kotlin layer would read a non-empty one if it comes later in the file.
- Section mismatch to know about: `turbo_limit` is used only by the Kotlin layer (`TurboHelper`) and saved under `[Core]`. The default file's `[Renderer] turbo_limit` line is not what the app uses.
- `volume` is raw 0.0–1.0 in the file. The menu shows 0–100 and divides by 100 when saving.

### Defaults

Kotlin is the source of truth for defaults on Android. At game launch `CitraSettings.syncDefaultsToNative()` pushes each Kotlin default into the core (`Config::AddDefaultSettingValue`). Several of these differ from the core defaults and from the comments in `config.ini`. The glossary uses the Kotlin defaults, which are the values that apply:

- `async_shader_compilation` false (the comment says On)
- `shaders_accurate_mul` false (core true)
- `lle_applets` false (core true)
- `use_skip_duplicate_frames` false (comment On)
- `simulate_3ds_gpu_timings` false (comment 1)
- `enable_audio_stretching` false (comment 1)
- `small_screen_position` 0 (core and menu label say 2, Bottom Right)
- `large_screen_proportion` 2.25 (core 4)
- `layout_option` 2 (Large Screen)
- `secondary_display_layout` 4 (Opposite Screen)
- `render_3d` 2

## When Azahar Reads and Writes the Files

`stop_before_write: true`.

Reads:

- **Native core.** Every `Config` object reads `config.ini`, plus `custom/<TITLEID>.ini` when a game is loaded, fresh from disk. A `Config` is built at every game boot (`native.cpp` `RunCitra`, `Config game_config(program_id)`) and at every `NativeLibrary.reloadSettings()`. That happens when a settings screen closes, after quick-menu layout changes, and once per process before the first game. A disk edit therefore reaches the core at the next game boot even while the process is alive.
- **Kotlin layer.** It loads `config.ini` into `CitraSettings.activeSettings` once, in `MainActivity.onCreate`. When a game is launched by intent into a fresh process, it loads in `EmulationActivity.loadGameSettings` instead, but only if nothing was loaded yet. It uses its in-memory copy for the defaults it pushes to the core, and for the settings only it handles: performance overlay, screen orientation, cutout, secondary display on/off, turbo limit and controls.

Writes:

- `saveGlobalFile` runs when the global settings screen closes after a change, and once for the input-mapping migration. It loads the file from disk, then writes **every** setting the Kotlin layer knows from its in-memory copy. Unset values are written as an empty value. Edits you made on disk to Kotlin-known keys while the app was running are lost.
- `saveSetting` writes one key. It runs for quick-menu toggles: swap screens, landscape, portrait and secondary layout, upright, performance overlay, and the Anime4K reset. It writes to the per-game file when that key is overridden for the running game, and otherwise to `config.ini`. It preserves the rest of the file on disk.
- `saveCustomFile` runs when the per-game settings screen closes. It rewrites `custom/<ID>.ini` with only the overrides, or deletes it when none are left.
- If `config.ini` is missing or does not parse, the core recreates it from `default_ini.h`. The "Reset all settings" action deletes the file and recreates it.

So: force-stop Azahar, edit, then launch. Native-only keys, such as `audio_emulation`, which has no menu entry, would survive a running app. Everything the menu shows would not.

### First Launch After the Update

On an install upgraded from 2126 or earlier, the prefs have no `InputMapping_Migrated` key, and the first 2127 launch runs `GamepadHelper.migrateGamepadSharedPrefsToActiveSettings()`. It copies the old `InputMapping_*` prefs into `[Controls]` and calls `saveGlobalFile`, which rewrites `config.ini` with every Kotlin key, filled or empty. Keys new in 2127 then appear in the file, such as `use_vsync`, `use_integer_scaling`, `enable_secondary_display`, `performance_overlay_*`, `[Core] turbo_limit` and `aspect_ratio`. Stale keys stay: `use_vsync_new`, `vsync_enabled`, `enable_dsp_lle`, `enable_dsp_lle_thread`, `[System] language`, `use_virtual_sd` and others. Do one normal app launch, then stop the app before the first scripted edit. Keys whose `verified_on_device` is false were absent from a file last written by 2126 for this reason.

## Per-Game Settings

- **Path.** `/sdcard/Azahar/config/custom/<TITLEID>.ini`. The core uses `std::uppercase << std::hex << setw(16) << setfill('0')` of the program ID, and the app uses `String.format("%016X", titleId)`. Example: `00040000001CB400.ini`.
- **Contents.** Only the overridden keys, in normal sections:

  ```
  [Renderer]
  resolution_factor = 3
  [Layout]
  layout_option = 2
  ```

- **Semantics.**
  - A key that is present overrides global; a missing key uses global. To revert a key, delete its line.
  - Do **not** write an empty value. The core then falls back to the built-in default, not the global value, while the Kotlin layer ignores the line, so the two layers disagree.
  - Every setting in the menu can be overridden per game. The Kotlin layer has no allow-list, and the core reads every key through the same per-game-first lookup (`GetSettingFromKey`). The GPU driver and the system language cannot, because they are not in the INI.
- **Creating by hand.** This works. The app finds the file with `DocumentFile.findFile` in the SAF tree, and the core reads it by path. If `config/custom/` does not exist, create the folder too (through `/sdcard`).
- **Launch paths.** Per-game files apply both to game-list launches and to external launch intents (Cocoon), because `EmulationActivity.loadGameSettings` derives the title ID from the game the intent resolves to, and the core reads the program ID itself at boot. One exception: if the process is alive and the same game was the last one loaded, the Kotlin layer skips reloading its overrides, though the core still re-reads them. Stopping the app first avoids this.
- **UI.** In-game menu → "Per-Application Settings", or the game's long-press menu. A customized row shows "Customized: Long-press to reset to global".

### Finding Title IDs

The prefs `Games` set lists each game in the library with its `titleId` in decimal; convert it to `%016X`. Save-state file names in `/sdcard/Azahar/states/` and texture folder names in `/sdcard/Azahar/load/textures/` also carry the ID. Stray macOS `._` AppleDouble files in the ROM folder show up in the set with title ID 0; they are not games.

## Dual Screens on the Thor

The settings that decide what each Thor screen shows:

- `[Layout] layout_option` sets the main (top) display: 1 Single Screen, 2 Large Screen, 3 Side by Side, 4 Hybrid, 0 Original, 5 Custom.
- `[Layout] enable_secondary_display` (default true) lets Azahar draw on another display, here the Thor's lower panel.
- `[Layout] secondary_display_layout` sets what that display shows: 4 Opposite Screen, 1 Top, 2 Bottom, 3 Side by Side, 5 Original, 6 Hybrid, 7 Large Screen.
- `swap_screen` flips which screen is prominent. "Opposite Screen" follows it.

The usual split is `layout_option = 1`, `secondary_display_layout = 2`, `swap_screen = false`, which puts the top screen on the main display and the bottom screen on the lower display. Which physical display counts as "secondary" is picked in the quick menu and kept only in memory (`SecondaryDisplay.preferredDisplayId`). It is not a file setting. `screen_orientation = 0` locks landscape.

Custom layout coordinates: `[Layout] custom_top_{x,y,width,height}` and `custom_bottom_*` (defaults 0,0,800,480 and 80,480,640,480), and `custom_portrait_*`, used when the layout is 5 or portrait 1. They are not in the glossary.

## GPU Driver Selection

- There is no config key. The selection **is** the contents of `/data/data/io.github.lime3ds.android/files/gpu_driver/`.
- At app start, `GpuDriverHelper.initializeDriverParameters()` reads `meta.json` → `libraryName` and passes it to `NativeLibrary.initializeGpuDriver`. An empty or missing directory means the system driver.
- Choosing a driver in the Driver Manager deletes the directory and unzips the chosen zip from `/sdcard/Azahar/gpu_drivers/` into it (`installCustomDriverPartial`).
- The driver is global only and takes effect after an app restart.
- Changing it by file would mean unzipping as root into an app-private folder with owner set to Azahar's app uid and mode 600. Use the Driver Manager instead.

## Gotchas

- `texture_filter = 1` (Anime4K) with Vulkan is reset to 0 by the app at game launch, which saves the change and shows a dialog.
- These keys can't be changed while a game runs (`NOT_RUNTIME_EDITABLE`): `graphics_api`, `region_value`, `init_clock`, `is_new_3ds`, `lle_applets`, `async_shader_compilation`, `shaders_accurate_mul`, `use_vsync`, `use_cpu_jit`, `async_custom_loading` and others. File edits apply at the next boot anyway.
- `audio_emulation` (0 HLE, 1 LLE, 2 LLE multithreaded) and `antialiasing` are read by the core but have no Android menu entry. The app never touches them.
- The system language, username, birthday and country are in the emulated system save (`nand`), written through the System menu. A `[System] language` line in `config.ini` is stale.
- A `config.ini` can have a non-empty `[Debugging] use_gdbstub` and `gdbstub_port`. Android omits both keys and ignores them.
- `[WebService] network_token` is a secret field. Never print it.

## Verified on Device vs Taken From Source

Verified on a device by read-only adb and root reads:

- Package version and APK splits.
- User-folder URI → `/sdcard/Azahar`.
- File paths, owner (MediaProvider uid), mode and SELinux label.
- `config.ini` contents. 23 glossary keys exist in the right section (`verified_on_device: true`).
- No same-section duplicate keys.
- The installed driver `meta.json` and the zips.
- The prefs contents (title IDs, `InputMapping_Migrated`).

Taken from source, not tested on device:

- Every value meaning, default and label.
- Section-aware native reads vs section-blind Kotlin reads.
- The inih duplicate-key behavior. That comes from upstream `benhoyt/inih` `INIReader::ValueHandler`; I did not check the submodule commit Azahar pins.
- When the files are read and saved.
- The per-game lookup order and the empty-value pitfall.
- Per-game files used by intent launches.
- The first-launch migration rewrite.
- The driver mechanism.

No writes were made and nothing was launched, so no edit has been round-tripped through the app.

## Sources

Azahar source, tag `2127.0.1`: https://github.com/azahar-emu/azahar/tree/2127.0.1

- `src/android/app/src/main/jni/config.cpp`: native read logic, per-game file name and lookup order.
- `src/android/app/src/main/jni/default_ini.h`: default file, comments, omitted keys.
- `src/android/app/src/main/jni/native.cpp`: `RunCitra` and `reloadSettings` build a `Config`.
- `src/common/settings.h`: core enums, ranges, core defaults.
- `src/android/app/src/main/java/org/citra/citra_emu/features/settings/model/{BooleanSetting,IntSetting,FloatSetting,StringSetting,CitraSettings}.kt`: Kotlin keys, sections, defaults, runtime-editable list.
- `.../features/settings/utils/SettingsFile.kt`: Kotlin read and write, per-game path.
- `.../features/settings/ui/{SettingsFragmentPresenter,SettingsActivityPresenter,SettingsAdapter}.kt`: menu items, save on close, per-app editing.
- `.../activities/EmulationActivity.kt` (`loadGameSettings`), `.../ui/main/MainActivity.kt`, `.../features/input/GamepadHelper.kt` (migration), `.../display/{ScreenLayout,ScreenAdjustmentUtil,SecondaryDisplay}.kt`, `.../utils/{GpuDriverHelper,TurboHelper,GameHelper}.kt`, `.../viewmodel/DriverViewModel.kt`.
- `src/android/app/src/main/res/values/{strings.xml,arrays.xml}`: Android labels and menu values.
- `src/android/app/build.gradle.kts`: `googlePlay` flavor, application id `io.github.lime3ds.android`.
- inih `INIReader.cpp`: https://github.com/benhoyt/inih/blob/master/cpp/INIReader.cpp
