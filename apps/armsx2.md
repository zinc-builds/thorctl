# ARMSX2 (com.armsx2) Settings Adapter

ARMSX2 (checked against 2.9.3, versionCode 1792) keeps every emulator setting as JSON inside one SharedPreferences file. The PCSX2-style INI files on the SD card are regenerated from that JSON at every game boot, so editing them does nothing lasting. Edit the prefs, with the app stopped.

This adapter covers the `com.armsx2` package. The `come.nanodata.armsx2` package was not checked.

## Files

| File | Role | Edit? |
|---|---|---|
| `/data/data/com.armsx2/shared_prefs/ARMSX2.xml` | Source of truth. `<string name="config.global">` holds the full global settings JSON (242 keys on the test device). `<string name="config.game.<SERIAL>">` holds each game's sparse overrides. App-only prefs sit beside them (`ui.osdMode`, `touch.*`, `bios`, `systemDir`, `romsDirs`, `gamesCache`, `playtime.*`). | Yes, app stopped |
| `<systemDir>/PCSX2-Android.ini` | PCSX2 base layer the native core reads. Rewritten from the resolved settings (global merged with the booting game's overrides) at every boot and on every save. It shows what the last game ran with, not the global choices: after a game with overrides boots, it holds that game's values (for example widescreen patches, upscale multiplier and upscaler) even where `config.global` differs. | No (read-only diagnostics) |
| `<systemDir>/gamesettings/<SERIAL>_<CRC>.ini` | PCSX2 per-game layer. Regenerated from `config.game.<SERIAL>` at boot (staged, then written just before the core loads it) and on every in-game settings save. | No |
| `<systemDir>/armsx2-settings.json` | Mirror `{"global":{…},"games":{"<serial>":{…}}}` written on each app-side save. Read back only when `config.global` is missing from prefs (fresh install pointed at an old folder). | No |
| `/data/data/com.armsx2/files/drivers/<id>/` | Installed custom Vulkan drivers (`meta.json` + the `.so` named in `libraryName`). | Install via the app |

`systemDir` comes from the `systemDir` pref and can be on the SD card, for example `/storage/<sdcard>/Android/data/com.armsx2/files`. In that case `/sdcard/Android/data/com.armsx2/files` holds only `bios/` and `logs/`, and the `bios` pref points to a BIOS file there.

## Formats

- `ARMSX2.xml` is standard Android SharedPreferences XML. The settings are a JSON object stored as an XML-escaped string (`&quot;`). The adapter uses the `prefs` format with `#` JSON paths: `config.global#renderer`.
- Raw values are JSON scalars: `true`, `2`, `1.5`, `"vulkan"`. Numbers are bare. `upscaleFloat` is stored as `1`, `1.5`, `4`.
- Unknown keys are ignored. A missing key takes the code default (`Settings.fromJson` uses `optInt`/`optBoolean` with defaults), so adding a key that a newer version introduced is safe.
- Values outside a field's range are clamped when written to the core (for example `nominalSpeedPercent` 10..1000, `audioVolume` 0..200, `aspectRatio` 0..8, `halfPixelOffset` 0..5).

## Write Rules

1. **Stop the app first** (`am force-stop com.armsx2`). Android caches SharedPreferences in memory, and the app rewrites the whole file from that cache on any save (playtime counters, game list cache, settings), which would overwrite an outside edit. `stop_before_write: true`.
2. Keep the owner (the app's uid, for example `u0_a<N>:u0_a<N>`), mode `660`, and SELinux label (`u:object_r:app_data_file:s0:` plus the app's categories). Write in place (for example `cat > file`), not by replacing the file.
3. Delete `ARMSX2.xml.bak` if one exists. Android restores the `.bak` over the main file when it finds one.
4. The app reads `config.global` and `config.game.<serial>` again at each game boot (`ConfigStore.resolveForGame`, no caching), so the next boot after a cold start applies the edit. It also reads them when a settings screen opens.
5. Some one-time migrations rewrite `config.global` on the first start after an update (`ConfigStore.loadGlobal` and the `migrate*` functions: OSD defaults, affinity 0 to 7, IOP thread lag, IOP thread on for narrow-tier devices, low-latency queue). If the prefs were last written by an older version (`lastRunVersionCode`), expect the next start to add keys such as `iopThread`, `iopThreadLag`, `vuAot` and possibly flip `iopThread` on. Re-read after the first launch following an update.
6. `armsx2-settings.json` goes stale after a direct prefs edit. That is harmless while `config.global` exists. Never delete `config.global`: the app would then restore everything from the mirror.

## Per-Game Overrides

- Key: `config.game.<SERIAL>` in the same `ARMSX2.xml`. The serial is the disc serial (`SCUS-97265`), as in `gamesCache[].serial` or the `gamesettings/<SERIAL>_<CRC>.ini` filenames. Serial-less ELF/homebrew use the ROM filename stem (`GameInfo.settingsKey`).
- Content: a sparse JSON object with the same key names as `config.global`, holding only the overridden fields. Example: `config.game.<SERIAL> = {"upscaleFloat":4,"upscaler":3}`.
- Merge at boot: per-game key if present, else global, else code default (`Settings.merge`). Every field can be overridden per game, renderer, upscale and GPU driver included. Exceptions: `pineEnabled`/`pineSlot` are process-wide and always come from global.
- To override a setting for a game, add the key to that game's object; create `<string name="config.game.<SERIAL>">{}</string>` first if the game has none. To return a setting to global, remove the key. Removing the whole entry returns the game to global.
- Overrides are sticky in the app: once a key is in the per-game object, later global changes do not reach it, even if the value happens to equal global.
- **Adapter gap:** in `armsx2.json` the per-game file is the same XML and the per-game key is the glossary key with `config.global#` replaced by `config.game.{game}#`. The current `cocoonlib/apps.py` reuses the glossary key unchanged for `--game`, so `app set armsx2 X=… --game SERIAL` would write the global key. `apps.py` needs to swap the prefix (and create the missing `config.game.<SERIAL>` string) before per-game writes are safe.

## GameDB Precedence

ARMSX2 applies the PCSX2 GameDB (`GameDbFields.kt` lists the fields it contends: EE/VU clamp and round modes, MTVU, IOP thread, EE cycle rate, mipmap, half-pixel offset, round sprite, native scaling, auto flush, texture inside RT, skipdraw, CPU sprite render, minimum blending level, gamefixes…). A GameDB value beats the **global** value for that game. Only a **per-game** key beats the GameDB. If a global change to one of those fields appears to do nothing for a game, set it per game. `enableGameFixes = false` stops the GameDB's gamefixes.

## GPU Driver

- Stored as `customDriverId` in the settings JSON (global and per game). `""` means the system driver. An id looks like `armsx2turnip-axfl2-003-turnip-axfl2-003-android` ("ARMSX2 Turnip axfl2-003", Mesa 27.0.0-devel, from its `meta.json`).
- The id is the directory name under `/data/data/com.armsx2/files/drivers/`. The app lists a driver only when that directory has `meta.json` and the library it names. Drivers must stay in app-private storage because `dlopen` is refused from `/storage`.
- Resolution at boot (`CustomDriver.effectiveId`): the game's id if installed; if a game names a driver that is no longer installed, the global id; otherwise the system driver.
- The driver is applied only with `renderer = "vulkan"`. The GPU Driver picker is hidden in Settings unless the Graphics API is Vulkan (`RendererBackendSection.kt`: `if (settings.output.renderer == "vulkan")`), which matches the project note.
- The pre-2.x global prefs `customDriverId`, `renderer`, `upscaleFloat`, `ui.orientation` are vestigial after the `config.migrated.*` flags are set. Do not edit them.

## Other Gotchas

- `ui.osdMode` (`Full`/`Min`/`Custom`/`Off`) is re-applied at every boot on top of the per-stat `osdShow*` flags. Those flags show only in `Custom`.
- Hardware fixes do not need `manualUserHacks`: the app sets `EmuCore/GS/UserHacks` whenever any fix is non-default.
- `aspectRatio` index order is fixed (0 Stretch … 8 Custom); 16:9 output also needs `enableWideScreenPatches` and a patch for the game.
- `upscaler` value 1 (MetalFX) is Apple-only; the Android UI never offers it.
- Shader caches are `<systemDir>/cache/vulkan_shaders_*.bin/.idx` and `cache/vulkan_pipeline_keys/`.
- ARMSX2 reads controllers through SDL and ignores injected key events (project note, not rechecked here).
- A full app reset deletes `PCSX2-Android.ini`, `gamesettings/` and the mirror in every data root (`ConfigStore.purgeAllSettingsFiles`).

## Verified on Device vs From Source

Verified on a Thor, read-only, 2026-11-27, against 2.9.3 (versionCode 1792): the structure of `ARMSX2.xml` (`config.global` with 242 keys, `config.game.*` entries, `ui.osdMode`, `systemDir`, migration flags, `lastRunVersionCode`); file owner, mode and SELinux label; `PCSX2-Android.ini`, `gamesettings` INIs, `armsx2-settings.json` (matched prefs exactly) and an installed driver's `meta.json`/`MANIFEST.json`. 39 of the 40 glossary keys were present on the test device with values inside the documented sets; `iopThread` was absent because those prefs predated it. The adapter was parsed with `cocoonlib.appconf.read("prefs", …)` against the pulled XML and every key resolved.

From source only (not exercised on the device, since this was read-only): that the app overwrites outside prefs edits while running, that the INIs are regenerated at boot, merge order, GameDB precedence, driver fallback, clamping, and the one-time migrations. UI labels come from the English string table in `i18n/I18n.kt` plus hard-coded labels in `RendererTab.kt` (for example "VSync"). Value meanings come from the KDoc in `Settings.kt` and the core enums in `pcsx2/Config.h`; the display strings for enum values follow upstream PCSX2 wording where ARMSX2's own picker text was not checked (EE cycle rate percentages, trilinear, round sprite, deinterlacing names).

Not checked: an actual write-and-boot round trip.

## Sources

- Repository: https://github.com/ARMSX2/ARMSX2, tag `2.9.3`, commit `1d680349c8f3e6ceb856412033e1346bd3ef9cbd` (2026-11-09). Matches versionName 2.9.3.
- `platforms/android/app/src/main/java/com/armsx2/config/ConfigStore.kt`: storage tiers, save/merge, mirror, reconcile, purge, migrations.
- `platforms/android/app/src/main/java/com/armsx2/config/Settings.kt`: every field, default, range, INI mapping (`applyTo`), per-game INI writer (`writeGameSettingsIni`, `stageGameSettingsIni`), `fromJson`/`merge`/`diff`.
- `platforms/android/app/src/main/java/com/armsx2/config/GameDbFields.kt`: GameDB-contended fields.
- `platforms/android/app/src/main/java/com/armsx2/runtime/MainActivityRuntime.kt`: `applyRendererPrefs`, `stagePerGameSettingsFile` (boot path), prefs name `ARMSX2`.
- `platforms/android/app/src/main/java/com/armsx2/CustomDriver.kt`: driver directory, `listInstalled`, `effectiveId`.
- `platforms/android/app/src/main/java/com/armsx2/ui/settings/RendererTab.kt`, `RendererBackendSection.kt`, `ui/InGameOverlay.kt`, `i18n/I18n.kt`: UI labels, upscale presets, GPU-driver visibility, OSD mode.
- `pcsx2/Config.h`: `GSRendererType`, `GSTextureInRtMode`, `GSNativeScaling`.
