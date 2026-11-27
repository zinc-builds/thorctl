# PPSSPP Gold (org.ppsspp.ppssppgold)

Adapter: `apps/ppsspp.json` (42 keys). Checked 2026-11-27 against PPSSPP Gold v1.20.4 on an AYN Thor and the PPSSPP source at tag **v1.20.4** (commit `fa50bb1976065c4f8b1b47af227d367fe9771555`). Gold is built from the same public source as the free version.

## Checked Build

- `dumpsys package`: versionName `v1.20.4`, versionCode 120040000. The tag `v1.20.4` exists in `github.com/hrydgard/ppsspp`, so the source facts below match the checked version.
- PPSSPP was not running during the check.

## Files

The memory stick folder is chosen in the app. `/data/data/org.ppsspp.ppssppgold/files/memstick_dir.txt` holds it as a SAF tree URI. The adapter assumes a folder `PPSSPP` at the root of the SD card: URI `content://com.android.externalstorage.documents/tree/<sdcard>%3APPSSPP`, path `/storage/<sdcard>/PPSSPP/`, where `<sdcard>` is the card's volume id (`ls /storage`). The adapter JSON uses the literal placeholder `<sdcard>` in its paths.

| Path | What it holds |
|---|---|
| `/storage/<sdcard>/PPSSPP/PSP/SYSTEM/ppsspp.ini` | All global settings. Owner `media_rw:media_rw`, mode 770. |
| `/storage/<sdcard>/PPSSPP/PSP/SYSTEM/controls.ini` | Button mapping, `[ControlMapping] Up = 10-4033,10-19` (`<device>-<keycode>`). |
| `/storage/<sdcard>/PPSSPP/PSP/SYSTEM/<GAMEID>_ppsspp.ini` | Per-game config. |
| `…/PSP/SAVEDATA`, `PPSSPP_STATE`, `TEXTURES`, `Cheats`, `PLUGINS`, `GAME`, `SYSTEM/CACHE` | User data. |
| `/data/data/org.ppsspp.ppssppgold/shared_prefs/` | Empty. PPSSPP does not use SharedPreferences for settings. |

## Write Rules (`ini`)

Sources: `Core/Config.cpp`, `Core/ConfigSettings.cpp`, `Common/Data/Format/IniFile.cpp`, `Common/Data/Text/Parsers.cpp`.

- **The files start with a UTF-8 BOM** (`EF BB BF`), and PPSSPP writes one on every save. `cocoonlib/appconf.ini_read` does not strip it, so the first section is not recognised: `thorctl app get psp auto_load_save_state` reports "not in file" although `[General] AutoLoadSaveState = 0` is present. A `set` of any `[General]` key would append a second `[General]` section, and PPSSPP would probably ignore it (not tested). **The parent needs to make the ini reader and writer skip a leading BOM and keep it on write.** Other sections are not affected.
- Lines are `Key = Value`. Bools are written `True`/`False`; `1`, `0`, `true` and `false` in any case are also read. Floats are written with 6 decimals (`1.000000`).
- `GraphicsBackend` is written `3 (VULKAN)`. On read the leading integer is used, and plain `3`, `VULKAN`, `0` or `OPENGL` also parse.
- On save PPSSPP loads the file, overwrites every key it knows and keeps lines it does not know. Stale keys from older versions survive. An install upgraded to 1.20.4 had `[Graphics] VSync`, `FrameSkipType`, `UnthrottlingMode`, `AudioBackend`, plus the old display-layout keys in `[Graphics]` (`BufferFiltering`, `DisplayStretch`, `DisplayAspectRatio`, …). They are ignored. Edit the current keys listed in the JSON.
- Display layout moved to `[DisplayLayout.Landscape]` and `[DisplayLayout.Portrait]` in 1.19+. The `[Graphics]` copies are only read when `[DisplayLayout.Landscape]` is missing, which is no longer the case once 1.19+ has saved the file.
- Some UI actions change two keys:
  - Choosing a GPU texture upscaler sets `TextureShader` and `TexHardwareScaling = (TextureShader != Off)`. Write both.
  - Turning on Auto FrameSkip turns off `SkipBufferEffects`.
  - Alternative speed is stored as a frame rate, not a percent: `FrameRate = percent × 60 / 100`; `0` means unlimited and `-1` means disabled.

## When PPSSPP Reads and Writes

- It reads `ppsspp.ini` and `controls.ini` once at start (`NativeInit` → `Config::Load`).
- It saves from memory when leaving any settings screen, when a game exits (`EmuScreen` "exitGame"), and in `onDestroy` (`NativeShutdown`). A force-stop skips the save.
- **Force-stop before editing global settings** (`stop_before_write: true`). Edits apply at the next start.

## Per-Game Settings (`PSP/SYSTEM/<GAMEID>_ppsspp.ini`)

Sources: `Core/Util/PathUtil.cpp` `GetGameConfigFilePath`; `Core/Config.cpp` `LoadGameConfig`, `SaveGameConfig`, `UnloadGameConfig` and `Save`; `Core/PSPLoaders.cpp`.

- The game ID is the `DISC_ID` from `PSP_GAME/PARAM.SFO`, without a dash (`ULUS10051`). The file name is `<ID>_ppsspp.ini`, or `_ppssppvr.ini` in VR builds.
- When a game boots, PPSSPP loads the file only if it exists. It then reads every setting present in the file over the global values; missing keys keep the global value. **A hand-made file with a few lines works** (`create: true`). It uses the same section and key names as `ppsspp.ini`, plus `[PostShaderList]`, `[PostShaderSetting]` and `[ControlMapping]` (per-game button mapping).
- When the game exits, or when its Game Settings screen closes, PPSSPP rewrites the file with **every** PER_GAME setting at its current value, a full snapshot. After that, changing a global per-game setting no longer reaches that game. To go back to global, delete the file (Game info → Delete game config does the same).
- While a game config is active, the main `ppsspp.ini` save skips PER_GAME keys, so global values are not overwritten by per-game ones.
- Which keys are per-game is set by `CfgFlag::PER_GAME` in `Core/Config.cpp`, and is mirrored in the JSON `per_game` field. Global-only keys in the glossary are `graphics_backend`, `display_resolution`, `inflight_frames`, `audio_playback_mode` and `framerate_mode`. A game ini can technically contain them, because `LoadGameConfig` reads every setting, but PPSSPP never writes them there. Treat them as global.
- Edit per-game files while the app is stopped, or at least while that game is not running. Otherwise the exit-time save overwrites the edit with the in-memory values.

### Finding a Game ID

Read the ISO9660 root → `PSP_GAME/PARAM.SFO` → key `DISC_ID`. `[PlayTime]` in `ppsspp.ini` lists the IDs of games that have been played.

## Gotchas

- `InternalResolution` 0 is "Auto (1:1)", meaning it matches the window. The Android default is 2 when the longest display side is at least 1000 px.
- `TexScalingLevel` on mobile builds offers 1 (Off), 2 and 3 only.
- `iShowStatusFlags` is a bit mask: 2 = FPS, 4 = speed, 8 = battery.
- `MultiSampleLevel`: the option is shown only when the GPU driver reports MSAA support (`multiSampleLevelsMask != 1`). Do not write levels the GPU lacks.
- `AutoLoadSaveState` 3–7 means Slot 1–5.
- `[Achievements] AchievementsUserName` and `[SystemParam] NickName`/`MacAddress` are identity data. Never print them. The RA token is saved separately with `NativeSaveSecret` (`Core/RetroAchievements.cpp`), not in the ini.
- The SD card is FUSE-mounted at `/storage/<sdcard>`. Root writes through that path keep the `media_rw` owner. PPSSPP accesses the folder through SAF, which sees the same files.

## Verified on Device vs From Source

- Checked on the test device: package version; memstick location; file paths, owners, modes and the BOM; every glossary key except `post_shader` (no `[PostShaderList]` in the checked file); stale keys; reading game IDs from PARAM.SFO; that the app was not running; and that `thorctl app get psp …` resolves keys, including `--game <GAMEID>`. The BOM problem showed up in a live `thorctl app get`.
- From source (v1.20.4): key names, defaults, PER_GAME flags, enum values, UI labels (`UI/GameSettingsScreen.cpp`, `UI/DisplayLayoutScreen.cpp`, `UI/DeveloperToolsScreen.cpp`), save and load timing, per-game semantics, and shader names (`assets/shaders/defaultshaders.ini`).
- No write was made (read-only task).

## Needs a UI-Driven Test

1. After the BOM fix: force-stop the app, set `auto_load_save_state` or another `[General]` key, start the app, and confirm Settings shows the new value.
2. Create `PSP/SYSTEM/<GAMEID>_ppsspp.ini` by hand with `[Graphics]` / `InternalResolution = 2`. Boot that game and confirm in-game Settings shows 2x and is marked game-specific. Then exit, and confirm the file was rewritten as a full snapshot.
3. Set `TextureShader = TexSpline36` together with `TexHardwareScaling = True`, and confirm the upscaler is active.
4. Check that a root-written file on `/storage/<sdcard>` is seen through SAF without a media rescan.

## Sources

- https://github.com/hrydgard/ppsspp/tree/v1.20.4 (commit `fa50bb1976065c4f8b1b47af227d367fe9771555`)
  - `Core/Config.cpp` (setting table, `Save`, `LoadGameConfig`, `SaveGameConfig`, `UnloadGameConfig`), `Core/ConfigValues.h` (enums), `Core/ConfigSettings.cpp`
  - `Core/Util/PathUtil.cpp` (`GetGameConfigFilePath`), `Core/PSPLoaders.cpp`, `Core/ELF/ParamSFO.cpp`
  - `UI/GameSettingsScreen.cpp`, `UI/DisplayLayoutScreen.cpp`, `UI/DeveloperToolsScreen.cpp`, `UI/EmuScreen.cpp`, `UI/NativeApp.cpp`, `android/jni/app-android.cpp`, `android/src/org/ppsspp/ppsspp/PpssppActivity.java`
  - `Common/Data/Format/IniFile.cpp` (BOM), `Common/Data/Text/Parsers.cpp` (bool parsing), `GPU/Vulkan/TextureCacheVulkan.cpp` (TexHardwareScaling), `assets/shaders/defaultshaders.ini`
