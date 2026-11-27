# Dolphin (org.dolphinemu.dolphinemu)

Adapter: `apps/dolphin.json` (40 keys). Checked 2026-11-27 against a Dolphin install on the AYN Thor (Android 13) and the Dolphin source at tag **2609b** (commit `3a5b3743b18da3e8f04cbc44f20dc50fbd3a9ef3`).

## Build Checked

- Checked against versionName `2609b`, versionCode 43134 (`dumpsys package`). The tag `2609b` exists in `github.com/dolphin-emu/dolphin`, so every source fact below is version-matched.
- Starting the app does not rewrite the config files: with Dolphin running, the inis kept modification times from days before the process started.

## Files

| Path | What it holds |
|---|---|
| `/sdcard/Android/data/org.dolphinemu.dolphinemu/files/Config/Dolphin.ini` | Main system: `[Core]` (CPU, GFXBackend, audio buffer), `[DSP]` (audio backend, volume), `[General]`, `[Interface]`, `[Android]`, `[Analytics]`. |
| `.../files/Config/GFX.ini` | Graphics: `[Hardware]`, `[Settings]`, `[Enhancements]`, `[Hacks]`, `[Stereoscopy]`, `[ColorCorrection]`. |
| `.../files/Config/GCPadNew.ini`, `WiimoteNew.ini`, `GCKeyNew.ini`, `GBA.ini`, `Hotkeys.ini`, `FreeLookController.ini` | Controller mappings (`Device = Android/1/Odin Controller`, controls in backticks). |
| `.../files/Config/RetroAchievements.ini`, `DSUClient.ini`, `Logger.ini`, `FreeLook.ini` | Empty until used. RetroAchievements.ini holds a token after sign-in. |
| `.../files/Config/TimePlayed.ini` | `[TimePlayed] <GameID> = 0x<hex ms>`. |
| `.../files/GameSettings/<GameID>.ini` | User per-game overrides, e.g. `GZ2E01.ini` with `[Video_Settings] BackendMultithreading = True`. |
| `/data/data/org.dolphinemu.dolphinemu/files/Sys/GameSettings/*.ini` | 1883 built-in per-game files from the APK. Root only. Re-extracted on update: never edit. |
| `/data/data/org.dolphinemu.dolphinemu/files/Sys/Shaders/*.glsl` | Post-processing shaders (value of `PostProcessingShader` = file name without `.glsl`). |
| `/data/data/org.dolphinemu.dolphinemu/files/GPUDrivers/` | Custom Vulkan drivers (`DriverLibName`). |
| `/data/data/org.dolphinemu.dolphinemu/shared_prefs/org.dolphinemu.dolphinemu_preferences.xml` | Touch overlay button positions and UI state. No emulation settings. |

The sdcard files are owned by the app's uid with group `ext_data_rw`, mode 660.

## Write Rules (`ini`)

Sources: `Source/Core/Core/ConfigLoaders/BaseConfigLoader.cpp`, `Source/Core/Common/StringUtil.cpp`, `Source/Core/Core/Config/{MainSettings,GraphicsSettings}.cpp`.

- Lines are `Key = Value` with spaces around `=`. Keys are case-sensitive as written in source (`wideScreenHack` is lower-case w).
- Bools are written `True`/`False`. On read, `true` in any case or a number equal to 1 counts as true.
- Enums and ints are written as decimal integers (`InternalResolution = 3`). Floats are written with fmt `{:#}`; any decimal such as `1.5` parses.
- A file holds only keys that were set at some point. A missing key means the source default. Dolphin keeps a key once set, even at its default value (for example `wideScreenHack = False`). To return to the default, delete the line.
- Keys Dolphin does not know are loaded into the base layer and written back unchanged.
- Some UI switches are inverted relative to the stored value: "Skip EFB Access from CPU" = `EFBAccessEnable False`, "Disable Bounding Box" = `BBoxEnable False`, "Emulate Disc Speed" = `FastDiscSpeed False`.
- Two UI choices span two keys: Synchronize GPU Thread (`SyncGPU`, `SyncOnSkipIdle`) and DSP Emulation Engine (`DSPHLE`, `[DSP] EnableJIT`). See the key notes in the JSON.

## When Dolphin Reads and Writes the Files

Sources: `Source/Android/jni/MainAndroid.cpp` (`NativeLibrary_Initialize`), `Source/Android/app/.../features/settings/model/Settings.kt` (`saveSettings`), `.../settings/ui/SettingsActivityPresenter.kt` (`onSettingChanged`, `onStop`), `Source/Core/Core/ConfigManager.cpp`.

- The base layer (all `Config/*.ini`) is loaded once, when the app process initialises its directories (`UICommon::Init`). `NativeLibrary.ReloadConfig` exists but nothing in the Java code calls it. An edit made while the process is alive is not read.
- Every change in the settings screens (main menu or in-game) calls `saveSettings()`, which saves the whole base layer from memory: Dolphin loads each ini from disk, overwrites every key it holds in memory, deletes keys it has unset, and writes the file. An external edit to a key Dolphin already holds is reverted. A new key added externally survives the save but is still not applied.
- `SConfig::~SConfig()` also saves on full shutdown.
- **Force-stop Dolphin before editing global inis, then start it** (`stop_before_write: true`).
- Game layers are built from disk at each game boot (`GenerateGlobalGameConfigLoader`/`GenerateLocalGameConfigLoader`). A per-game edit is picked up at the next launch of that game even if the process is alive, as long as that game's per-game settings screen is not open (it saves the LocalGame layer from memory). Stopping the app first is still safest.

## Override Semantics (Per-Game)

Source: `Source/Core/Core/ConfigLoaders/GameConfigLoader.cpp`, `Source/Core/Common/Config/Enums.h`.

- Layers, lowest to highest: Base (`Config/*.ini`) < CommandLine < GlobalGame (`Sys/GameSettings`) < LocalGame (`GameSettings/` under the user dir) < Movie < Netplay < CurrentRun. The highest layer that sets a key wins.
- Each game layer reads, in order, `<first letter>.ini`, `<first 3 characters>.ini`, `<GameID>.ini`, `<GameID>r<revision>.ini`; later files override earlier ones. The app writes only `<GameID>.ini`.
- Game inis use legacy section names: Dolphin.ini `[Core]`, `[DSP]`, `[Display]` keep their names; GFX.ini `[Settings]` → `[Video_Settings]`, `[Hacks]` → `[Video_Hacks]`, `[Enhancements]` → `[Video_Enhancements]`, `[Hardware]` → `[Video_Hardware]`, `[Stereoscopy]` → `[Video_Stereoscopy]`. Anything else is written `[<System>.<Section>]` (for example `[Main.General]`). Unknown sections are ignored with a log warning.
- A built-in Sys game ini can set values that beat the global file. Example: `Sys/GameSettings/GZ2.ini` sets `[Video_Settings] CPUCull = True` and `[Video_Hacks] VISkip = False` for Twilight Princess. To change such a value for one game, set it in the user `GameSettings/<GameID>.ini`.
- Controller mappings cannot be overridden per game, except the Wii Remote source settings (`ConfigLoaders::IsSettingSaveable`). `[Android]` keys are global only.
- Game inis also hold `[OnFrame]`, `[ActionReplay]`, `[Gecko]` and their `_Enabled` sections; leave those intact when editing.

### Getting the Game ID

The ID is the first 6 bytes of the disc header:

- RVZ/WIA: 6 bytes at file offset `0x58` (checked on an RVZ file).
- CISO: offset `0x8000` (checked on a CISO file).
- ISO/GCM: offset 0 (not checked).

```bash
adb shell su -c "dd if='/storage/<sdcard>/Roms/Gamecube/<game>.rvz' bs=1 skip=88 count=6 2>/dev/null"   # e.g. GZ2E01
```

## Gotchas

- `MaxAnisotropy`: the core enum is `Default=-1, 1x=0, 2x=1, 4x=2, 8x=3, 16x=4`, but the 2609b Android UI array labels value 0 as "Default". Write `-1` for "let the game decide".
- There is no audio-stretching key any more. Its replacements are `[Core] AudioFillGaps` and `[Core] AudioPreservePitch`.
- The audio backend (`[DSP] Backend`) is not in the Android settings UI. The Android default is `OpenSLES`.
- Default video backend on Android is `OGL` (the first backend registered). With no `GFXBackend` key, Dolphin runs OpenGL ES.
- Dual Core (`CPUThread`) defaults to True on Android, False on desktop.
- `RetroAchievements.ini` holds the API token after sign-in. Never print it.

## Verified on Device vs From Source

- On the test device: file paths and owners; the keys present in `Config/*.ini` and a user `GameSettings/<GameID>.ini`; Sys GameSettings count (1883) and `GZ2.ini` content; shader list; ROM game-ID offsets for RVZ and CISO; that the app does not rewrite the inis on start.
- Present in the test device's files (`verified_on_device: true`): `internal_resolution`, `widescreen_hack`, `vertex_rounding`, `dsp_thread`, `show_input_overlay`. All other keys are absent because they were never set; their names and defaults come from source.
- From source only (tag 2609b): key names, types, defaults, enum values, UI labels (`Source/Android/app/src/main/res/values/{strings,arrays}.xml`, `SettingsFragmentPresenter.kt`), load/save timing and layer order. No write was tested (read-only task).

## Sources

- https://github.com/dolphin-emu/dolphin/tree/2609b (commit `3a5b3743b18da3e8f04cbc44f20dc50fbd3a9ef3`)
  - `Source/Core/Core/Config/GraphicsSettings.cpp`, `MainSettings.cpp`, `MainSettings.h`
  - `Source/Core/VideoCommon/VideoConfig.h` (enums), `Source/Core/Core/PowerPC/PowerPC.{h,cpp}` (CPU cores)
  - `Source/Core/Core/ConfigLoaders/BaseConfigLoader.cpp`, `GameConfigLoader.cpp`, `IsSettingSaveable.cpp`
  - `Source/Core/AudioCommon/AudioCommon.cpp`, `Source/Core/VideoCommon/VideoBackendBase.cpp`
  - `Source/Android/jni/MainAndroid.cpp`, `Source/Android/app/src/main/java/org/dolphinemu/dolphinemu/features/settings/`
