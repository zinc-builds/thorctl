# WatermelonDS (me.magnum.melondualds)

Adapter: `apps/watermelonds.json` (41 keys). Checked 2026-11-27 against versionName `0.8.0.rc3` (versionCode 41) on an AYN Thor and the decompiled APK (jadx).

WatermelonDS is a melonDS fork for dual-screen Android handhelds, built on rafaelvcaetano's melonDS Android port (Java package `me.magnum.melonds`). The checked build has no published source: everything below comes from the APK's preference XMLs, string/array resources and decompiled code, plus the files on the test device.

## Files

| Path | What it holds |
|---|---|
| `/data/data/me.magnum.melondualds/shared_prefs/me.magnum.melondualds_preferences.xml` | Every global setting (AndroidX preferences). Root only. |
| `/data/data/me.magnum.melondualds/files/rom_data.json` | One-line JSON array of the scanned ROMs; each element's `config` object holds that game's overrides. |
| `/data/data/me.magnum.melondualds/files/rom_metadata_mirror.json` | Backup copy of each ROM's config with short keys (`c` = fileName, `d` = config). Read only when a rescan re-adds a ROM. |
| `/data/data/me.magnum.melondualds/files/layouts.json` | Custom layouts. `[]` when only the built-in default layout (UUID all zeros) exists. |
| `/data/data/me.magnum.melondualds/files/rom_directory_state.json` | Scan cache. Not settings. |
| `/data/data/me.magnum.melondualds/files/wfcsettings.bin`, `databases/melon-database` | Wi-Fi settings blob, Room DB. Not touched by the adapter. |
| `/sdcard/Android/data/me.magnum.melondualds/cache/rom_icons/` | Icon cache. |

Owner `u0_a<N>`, prefs mode 660, files mode 600, SELinux `u:object_r:app_data_file:s0:c<N>,c256,c512,c768`. A root write must restore owner and this label (`chcon`), or the app cannot read the file. The tool already handles this.

## Write Rules

- Prefs: strings are `<string>` (including numbers-as-strings such as `video_internal_resolution` = `6`, `frame_limit_speed_multiplier` = `0.75`); switches are `<boolean>`; sliders (`input_opacity`, `volume`, `video_conservative_coverage_px`) are `<int>`. Raw values in the JSON are JSON-encoded (`"vulkan"`, `true`, `50`).
- Enum prefs read through `SPSettingsRepository` are matched case-insensitively against enum names; an unknown value logs a warning and falls back to the default.
- A missing key means the default listed in the JSON.
- `stop_before_write: true`. The app caches SharedPreferences in memory and writes the whole file on any settings change, so an edit made while it runs is lost. Settings are turned into an `EmulatorConfiguration` at each game launch, so a cold start picks up the edit.

## Dual Screen On The Thor

- `external_display_mode` = `melon_dual_ds` puts the second DS screen on the Thor's bottom panel; `mirror` duplicates the main display.
- `dual_screen_preset` (absent = `off`) chooses which panel shows which DS screen: `internal_top_external_bottom` or `internal_bottom_external_top`. With a preset selected, `external_display_keep_ratio`, `dual_screen_integer_scale`, the four `dual_screen_*_fill_*` switches and the two `dual_screen_*_vertical_alignment` values (`top`/`center`/`bottom`, absent = preset default) shape each screen. With `off`, the layout from Input > Layouts decides.
- `soft_input_behaviour` = `always_invisible` hides the on-screen button bar on the bottom screen.

## Per-Game Settings

Per-game overrides are not in a separate file. They are fields of the `config` object in the `rom_data.json` element whose `fileName` matches the game:

| Field | Values | Global counterpart |
|---|---|---|
| `videoRenderer` | `SOFTWARE`, `OPENGL`, `VULKAN`, `COMPUTE` | `video_renderer` |
| `internalResolutionScaling` | integer 1-8, 12, 16 | `video_internal_resolution` |
| `threadedRendering` | `true` / `false` | `enable_threaded_rendering` |
| `videoFiltering` | `NONE`, `LINEAR`, `XBR2`, `HQ2X`, `HQ4X`, `QUILEZ`, `LCD`, `SCANLINES`, `RETROARCH` | `video_filtering` |
| `retroArchShaderPresetPath`, `retroArchShaderParameters` | strings | `video_retroarch_shader_preset`, `..._parameters` |
| `layoutId` | UUID of a layout in `layouts.json` | `input_layout_id` |
| `runtimeConsoleType` | `DEFAULT`, `DS`, `DSi` | `console_type` |
| `runtimeMicSource` | `DEFAULT`, `NONE`, `BLOW`, `DEVICE` | `mic_source` |
| `inputMode` | `GLOBAL`, `CUSTOM` (+ `customControllerConfiguration`) | global key mapping |
| `retroAchievementsEnabled`, `useHgEngineFix`, `customName`, `iconSource`, `dsiProfileId`, `gbaSlotConfig` | see JSON | none |

- A field that is absent, `DEFAULT` or `GLOBAL` uses the global setting. On the test device, games with no overrides had only `runtimeConsoleType: DEFAULT`, `runtimeMicSource: DEFAULT`, `gbaSlotConfig`, `useHgEngineFix: false`, `inputMode: GLOBAL`, `iconSource: DEFAULT`, so their video settings are global.
- Game id = `fileName`, e.g. `Some Game (USA).nds`. Elements are created by the ROM scan; do not add them by hand.
- Edit the matching element of `rom_metadata_mirror.json` (`c` == fileName, field `d`) the same way, or a rescan restores the old config.
- The format is `other` in the JSON: the parent's reader has to select the array element by `fileName` and edit `config.<field>`.

## Gotchas

- `theme` can hold `system`, a value missing from the 0.8.0.rc3 picker list (light/dark). Leave it.
- `enable_jit` default depends on the ABI list; true on arm64.
- `video_internal_resolution` does nothing with the Software renderer.
- Dynamic internal resolution (`video_vulkan_drs`) and Show rendered IR (`rendered_ir_position`) are Vulkan-only.
- Custom Vulkan drivers are imported through the UI (`video_vulkan_driver_import`); the adapter only switches `video_vulkan_driver_mode`.

## Verified On Device vs From Source

- On the test device: file paths, owner, mode and SELinux label; every key present in the prefs file (`verified_on_device: true` keys); the rom_data.json and mirror structure; that no WatermelonDS process was running.
- From source only: defaults, enum values and labels (`res/xml/pref_*.xml`, `res/values/arrays.xml`, `strings.xml`), dual-screen preset keys (`SPSettingsRepository`, `VideoPreferencesFragment`), per-game field names (`RomConfigDto`), load/save timing. No write was tested (read-only task).

## Sources

- APK `/data/app/.../me.magnum.melondualds-.../base.apk`, versionName 0.8.0.rc3, decompiled with jadx.
- Project: https://github.com/SapphireRhodonite/WatermelonDS (releases), upstream https://github.com/rafaelvcaetano/melonDS-android.
