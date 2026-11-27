# Cemu (info.cemu.cemu)

Adapter: `apps/cemu.json`. Checked 2026-11-27 against a Cemu install on the AYN Thor (Android 13, read-only adb and root reads) and the Cemu Android source (SSimco/Cemu, branch `android-port`, commit `8759323e`, 2026-04-27), cross-checked against a jadx decompile of the installed APK.

## Build Checked

- Checked against versionName `0.5.2`, versionCode 52 (`dumpsys package`). `libCemuAndroid.so` and `log.txt` both say `Cemu 0.5.1`.
- This build does not come from any public SSimco release. SSimco's releases stop at `0.5` (2026-04-25), and its `build.gradle.kts` hard-codes `versionCode = 1`. The APK also contains classes that no public SSimco branch has: `CemuDataStorage`, `CemuSaveSyncManager`, `StorageSettings` (a movable data root with save mirroring), `PadPresentation`, and the in-game options "External PAD screen" and "Rotate external screen left". GitHub code search finds none of these names. It is a third-party fork of `android-port` from about 2026-04-27, since it includes the emulated USB devices that commit `a4c911a2` added on 2026-04-25. I could not identify the fork.
- I took the core settings code (settings.xml, game profiles, the driver loader) from `android-port` `8759323e`. Every key name below also appears in the installed `libCemuAndroid.so`. I took the Android UI labels, the DataStore settings and the dual-screen options from the decompiled APK. Upstream `cemu-project/Cemu` has no Android code. The Android port is open as PR #1909 from SSimco's `android` branch.

## Files

The data root is `/sdcard/Android/data/info.cemu.cemu/files`. It is `getExternalFilesDir(null)` unless the "Data storage" setting moved it (`storageSettings.dataRootPath` / `customRootUri` in `appSettings.json`). Cemu's user, config and cache paths are all this root, and its data path is `<root>/data`.

| Path | What it holds |
|---|---|
| `<root>/settings.xml` | All core settings: graphics, overlay, audio, language, game paths, graphic packs, custom driver. XML. Owner `<app uid>:ext_data_rw`, mode 660, label `media_rw_data_file:s0:c<N>,c256,c512,c768` (categories follow the app uid). |
| `/data/data/info.cemu.cemu/files/datastore/appSettings.json` | Android-side settings (GamePad position, external PAD screen, input overlay, hotkeys, UI language, storage root). Can be absent (only `.lock` and `.version` exist); then everything is at its default. |
| `<root>/gameProfiles/<titleid>.ini` | User game profile (per-game settings). The folder may not exist until a profile is saved. |
| `<root>/data/gameProfiles/default/<titleid>.ini` | 236 shipped profiles. The app replaces them after every update. Never edit them. |
| `<root>/title_list_cache.xml` | Game list with title ids. |
| `<root>/controllerProfiles/controller0.xml` | Controller 1 mapping: emulated controller type, input API and input device. |
| `<root>/shaderCache/{transferable,precompiled,driver}` | Shader and pipeline caches, named `transferable/<titleid>_{shaders,vkpipeline}.bin`. |
| `<root>/log.txt` | Last session log. It prints the active settings and the game profile path at boot. |
| `<root>/customDrivers/<name>/` | Drivers installed in the app (`meta.json` and a `.so`). Created when the first driver is installed. |
| `<root>/graphicPacks/downloadedGraphicPacks/` | Graphic packs, after they are downloaded in the app. |

## settings.xml Format (`other`: the parent needs a reader)

Cemu writes this file with tinyxml2 through `XMLConfigParser` (`src/config/XMLConfig.h`, `src/config/CemuConfig.cpp`).

- It starts with the `<?xml version="1.0" encoding="UTF-8"?>` declaration. The root element is `<content>`, and the indent is 4 spaces.
- A key is the slash path of element names from the root, for example `content/Graphic/VSync`, `content/Graphic/Overlay/FPS` or `content/Audio/TVVolume`. A value is the element's text.
  - Bools are `true` or `false`.
  - Integers and enums are decimal.
  - Floats look like `2.2`.
  - Strings are plain text and may be empty (`<PadDevice></PadDevice>`).
- To set a value, replace the element's text. If the element is missing, add it under its parent. On load a missing element takes the default given in `CemuConfig::Load`, which is not always the struct default:
  - `Graphic/api` missing means 0 (OpenGL). Never remove it.
  - `UpscaleFilter` missing means 2.
  - `TVVolume`, `InputVolume` and `PortalVolume` missing mean 20.
- These parts use attributes or repeated elements:
  - `Input/DSUC` has the attributes `host` and `port`.
  - `GamePaths/Entry` repeats, one SAF tree URI each.
  - `AccountService/SelectedService` uses the attributes `PersistentId` and `Service`.
  - `GraphicPack/Entry` repeats; see Graphic Packs below.
  - An empty container is written self-closed (`<GraphicPack/>`).
- On save Cemu rewrites the whole file from memory in its own element order. Unknown elements are dropped.

## When Cemu Reads and Writes settings.xml

Source: `CemuApplication` (APK), `NativeEmulation.cpp` `initializeEmulation`, `main.cpp` `CemuCommonInit`, `MainActivity.kt`.

- **Read once** when the app process starts. `CemuApplication.onCreate` calls `initializeEmulation`, which calls `CemuCommonInit` and then `GetConfigHandle().Load()`. A game launched from an outside intent (`EmulationActivity`, `ACTION_VIEW` with a launch path) starts the process the same way, so it also reads the file at start.
- **Written** from memory by `NativeSettings.saveSettings()`. It runs on `MainActivity.onPause` and `onDestroy`, and right before a game starts from the list. An edit made while the process is alive is never read, and the next pause overwrites it. **Force-stop Cemu, edit, then start it** (`stop_before_write: true`).
- Some values are only used later. Audio devices and volumes take effect at game start. VSync is checked every frame. The custom driver loads when Vulkan first initialises in the process.

## appSettings.json (DataStore)

- `MultiProcessDataStoreFactory`, file `files/datastore/appSettings.json`, read with kotlinx `Json.Default`. Field names come from the APK's serializers:

  ```json
  {"guiSettings":{"language":"…"},
   "emulationSettings":{"gamePadPosition":"RIGHT","isPadVisible":false,"isPadOnExternalDisplay":false,"isExternalScreenRotatedLeft":false},
   "storageSettings":{"dataRootPath":null,"customRootUri":null,"mirrorRootPath":null,"pendingDeleteDataRootPath":null,"isSaveMirrorDirty":false,"lastSaveSyncAtMillis":null,"lastManualSyncAtMillis":null,"isMirrorDirty":false,"lastStorageError":null},
   "inputOverlaySettings":{"isVibrateOnTouchEnabled":false,"isOverlayEnabled":false,"controllerIndex":0,"alpha":64,"inputVisibilityMap":{},"inputOverlayRectMap":{}},
   "hotkeySettings":{}}
  ```

- The app writes only fields that differ from their defaults, so `{}` is a valid starting file. Enums are stored by name and bools are unquoted.
- Parsing is strict. An unknown key, a wrong type or invalid JSON turns the **whole file** into defaults with no error (`readFrom` catches the exception), and the next app write then replaces it.
- Do not edit `storageSettings`: it moves the data root.
- Writing needs root. Keep owner `<app uid>:<app uid>`, mode 600 and label `app_data_file:s0:c<N>,c256,c512,c768`. Stop the app first, because DataStore caches the file in memory and tracks changes through the `.version` counter file.
- `isPadVisible`, `isPadOnExternalDisplay` and `isExternalScreenRotatedLeft` are written whenever those in-game menu items change (`DataStoreImpl$data$1` line 861). That the app reads them back when emulation starts comes from the decompile, which jadx could not fully decompile there. A UI test should confirm it.

## Dual Screen (Thor Bottom Screen)

- "Show PAD" (`isPadVisible`) shows the Wii U GamePad view.
- "External PAD screen" (`isPadOnExternalDisplay`) moves the GamePad view to a second Android display through an Android `Presentation`. It works only while Show PAD is on and a second display exists. On the Thor this should put the GamePad image on the bottom screen.
- "Rotate external screen left" rotates that view. "Swap screens" and "Replace TV with PAD" are in-game only and are not saved.
- When the GamePad shares the main screen, its place comes from "GamePad position" (`gamePadPosition`: ABOVE, BELOW, LEFT, RIGHT; default RIGHT).
- I have not tested any of this on the Thor.

## Per-Game Settings (Game Profiles)

Source: `src/Cafe/GameProfile/GameProfile.cpp`, `src/android/app/src/main/cpp/NativeGameTitles.cpp`, `GameProfileEditScreen.kt`.

- **Path.** `GameProfile::Load` tries `ActiveSettings::GetConfigPath("gameProfiles/{:016x}.ini")`, which is `<root>/gameProfiles/<id>.ini`. If that file does not exist, it uses `<root>/data/gameProfiles/default/<id>.ini`. The log line `gameprofile path: gameProfiles/default/<id>.ini` shows when the fallback is in use.
- **Game id.** The 16-digit lowercase hex title id of the base game, from `title_list_cache.xml` (`titleId`, with `app_type="80000000"`) or from the `Mounting title` line in the log. Use the base id (`00050000…`), not the update id (`0005000e…`). Cemu names files with lowercase hex; shipped defaults mix cases (`000500001010EB00.ini`). I did not check whether `/sdcard` matches names case-insensitively, so always write lowercase.
- **No merging.** Once a user file exists, the default profile is ignored completely. Make a new user file by copying the default profile and then changing keys. The Android "Edit game profile" screen does this itself: it loads the user or default profile, applies the change and saves the full result to the user path.
- **Format.** An INI with `key = value` lines and an optional first line `# Game name`. The sections are:
  - `[General]`: `loadSharedLibraries`, `startWithPadView`.
  - `[CPU]`: `cpuMode`, `threadQuantum`.
  - `[Graphics]`: `accurateShaderMul`, `precompiledShaders`, `graphics_api`.
  - `[Audio]`: `disableAudio`.
  - `[Controller]`: `controller1` to `controller8` (controller profile names).
  - `[AndroidDriver]`: `mode`, `customPath`.

  Section names are case-insensitive. Bools accept `true`, `false`, `1` and `0`.
- **What it overrides.** Only the keys above exist per game. Every settings.xml setting is global only. The exception is the GPU driver, which per game uses `[AndroidDriver]`.
- **No effect on Android.** `precompiledShaders` is ignored (hard-wired to auto). `graphics_api` must not be set because Android always renders with Vulkan. CPU mode has no global setting: the save line in `CemuConfig.cpp` is commented out, so the default is Auto everywhere.
- **When it is read.** At every game boot (`CafeSystem` calls `gameProfile_load`), whatever started the game. A per-game edit can be made while the app sits in the game list, as long as that game's "Edit game profile" screen is not open (each change on that screen rewrites the file). Stopping the app is still the safe default.
- **Creating files by hand.** This works. Create `<root>/gameProfiles/` with owner `<app uid>:ext_data_rw`, mode 770 and the same label as settings.xml.
- **What the app writes.** `[General]`, `[CPU]`, `[Graphics]`, `[Controller]` and `[AndroidDriver]`, in that order. `[AndroidDriver] mode` is written as 0, 1 or 2. `cpuMode` is written as a name, such as `Multi-core recompiler`. `[Audio] disableAudio` is dropped on rewrite.

## Resolution and Graphic Packs

Wii U render resolution, FPS unlocks and similar fixes are graphic packs, not settings. Until packs are downloaded there is no `graphicPacks/` folder and `<GraphicPack/>` is empty. Download them once in the app (Graphic packs, then download). After that, activation is stored in settings.xml:

```xml
<GraphicPack>
    <Entry filename="graphicPacks/downloadedGraphicPacks/TwilightPrincessHD/Graphics/rules.txt">
        <Preset>
            <category>Resolution</category>
            <preset>2560x1440</preset>
        </Preset>
    </Entry>
</GraphicPack>
```

- `filename` is the pack's `rules.txt` path relative to the root.
- Having an Entry means the pack is enabled. A pack that is on by default is disabled with `disabled="true"`.
- `category` is left out for presets that have none. Preset names must match the `[Preset]` `name =` values in that `rules.txt`. The folder and preset names above are an example only.
- Packs and presets load at app start (`GraphicPack2::LoadAll`) and are applied at game boot.
- Packs apply to the title ids listed in their `rules.txt`, so they work per game even though they are stored globally.

## GPU Driver

- Global: `content/custom_driver_path`. Empty means the system driver; otherwise it is the absolute path of a folder under `<root>/customDrivers/` that holds a `meta.json` (with a `libraryName`) and the `.so`.
- Per game: `[AndroidDriver] mode` set to 0 (Global), 1 (System) or 2 (Custom, with `customPath`). Custom falls back to the global driver if `customPath` does not exist (`VulkanAPI.cpp` `get_custom_driver_path`).
- The `.so` is copied into the app's internal folder and loaded with adrenotools.
- The log's `Driver Build:` line names the driver in use.
- Install drivers through Graphics settings > Custom drivers. The other emulators' Turnip zips can be installed from there.

## Gotchas

- With `content/Graphic/Overlay/Position` at `0` (Disabled), no overlay shows even when `FPS` is true. Set Position to 1–6 to see FPS.
- `content/Audio/delay` counts 12 ms steps. The menu's "Latency" in ms is `delay × 12`, from 0 to 276.
- `TVDevice` and `PadDevice` work as switches. Android always uses Cubeb and ignores the name. Empty means off; anything else means on. The menu writes `Default`.
- `content/Audio/api` is ignored on Android.
- VSync "Off" (0) asks for Vulkan Immediate, which the Adreno system driver does not offer (log: "Can't find immediate present mode").
- `data/` is wiped and re-extracted from the APK whenever `data/hash.txt` changes, which happens on app updates. Never keep user files there.
- The shared app UI language is `guiSettings.language` in `appSettings.json`, separate from `console_language`.

## Verified on Device vs Taken From Source

Verified on a device by read-only adb and root reads:
- The package version and the native version string (`Cemu 0.5.1`).
- The data root and every listed path that exists, plus owners, modes and SELinux labels.
- 29 settings.xml glossary keys exist in the file (`verified_on_device: true`).
- The 236 default profiles.
- The log's active-settings block and the game profile path it used.

Taken from source or the APK decompile, not tested on device:
- What each enum value means, and the defaults.
- When settings.xml is read and written.
- How game profiles are looked up, merged (they are not), parsed and written.
- The DataStore format and the dual-screen keys (all `verified_on_device: false`).
- The graphic pack entry format.
- Driver selection.

No writes were made and nothing was launched, so no edit has been round-tripped through the app yet.

## Sources

- SSimco/Cemu `android-port` at `8759323e5b72594665b55e02f99db3c1e1e7de8a` (2026-04-27): https://github.com/SSimco/Cemu/tree/8759323e5b72594665b55e02f99db3c1e1e7de8a
  - `src/config/CemuConfig.{h,cpp}`, `src/config/XMLConfig.h`, `src/config/ActiveSettings.cpp`: settings.xml keys, enums, load and save defaults, CPU mode.
  - `src/Cafe/GameProfile/GameProfile.{h,cpp}`: profile paths, keys, parsing, writing.
  - `src/Cafe/GraphicPack/GraphicPack2.cpp`, `src/android/app/src/main/cpp/NativeGraphicPacks.cpp`: graphic pack entries.
  - `src/Cafe/HW/Latte/Renderer/Vulkan/VulkanAPI.cpp`: custom driver choice. `.../Vulkan/SwapchainInfoVk.h`: VSync enum.
  - `src/android/app/src/main/cpp/{NativeEmulation,NativeSettings,NativeGameTitles,NativeActiveSettings}.cpp`: Android load and save, audio, latency × 12, driver.
  - `src/android/app/src/main/java/info/cemu/cemu/{MainActivity.kt, settings/**, games/profile/GameProfileEditScreen.kt, nativeinterface/*.kt, common/customdrivers/CustomDrivers.kt}`: labels, menu values, save triggers.
- Installed APK, decompiled with jadx: `CemuApplication`, `common/settings/*` (`AppSettings`, `EmulationSettings`, `StorageSettings` serializers), `common/storage/CemuDataStorage.resolveCurrentRoot`, `emulation/EmulationScreenKt` (side-menu labels), `androidx/datastore/core/DataStoreImpl$data$1` (pad flags persisted), `FileStorage$$ExternalSyntheticLambda0` (DataStore path).
- Android port PR: https://github.com/cemu-project/Cemu/pull/1909 (head `SSimco:android` `7c2324ed`, 2026-07-02).
