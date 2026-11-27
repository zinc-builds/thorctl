# openDE (com.opende.deusex)

Adapter: `apps/opende.json` (34 keys). Checked 2026-11-27 against 0.5-beta on an AYN Thor and the source of [JMAccorsi/OpenDE-Android](https://github.com/JMAccorsi/OpenDE-Android) at tag **v0.5** (Android port of [jarmitage99/OpenDE](https://github.com/jarmitage99/OpenDE), MIT).

## Checked Build

- versionName `0.5-beta`, versionCode 6.
- APK SHA-256 `3f1fec60…a229530` equals release v0.5 `openDE-v0.5-arm64-v8a.apk` (2026-11-20).
- Newer pre-releases: v0.6, v0.6.1, v0.6.2, **v0.7-beta (2026-11-27)**. v0.7 replaces the Java launcher with an SDL3 launcher; the keys below come from v0.5 and should be re-checked after an update. The app has a built-in updater (GitHub releases API).

## Files

| Path | What it holds |
|---|---|
| `/sdcard/Android/data/com.opende.deusex/files/DeusEx.ini` | Live system ini. OpenDE options in `[WinDrv.WindowsClient]`, controller options in `[DXController.ControllerSettings]`, `[DXController.AutoSaveManager]`. |
| `/sdcard/Android/data/com.opende.deusex/files/User.ini` | Live user ini: `[DeusEx.DeusExPlayer]` HUD/gameplay toggles, `[Engine.Input]` bindings. |
| `…/files/System/DeusEx.u`, `DXController.u` | Overlay packages the app installs over the game's own. |
| `/data/data/com.opende.deusex/shared_prefs/opende_prefs.xml` | `game_root` = the folder that holds the game files. Also cached in `files/opende_game_root.txt`. |
| `…/files/Save/` | Save games (`userDirectory/System/..\Save`). |

`src/core/config.cc` `userDirectory()` is the app's external files dir on Android, so the `DeusEx.ini` and `User.ini` inside `<game_root>/System` are only the seeds, not the live files.

## Write Rules (`ini`)

- Unreal-style `Key=Value` with no spaces. The repo's writer keeps the existing separator.
- Repeated keys (`Paths=`, `ServerActors=`, `EditPackages=`, `Suppress=`) are lists. The adapter only touches single-valued keys; do not set list keys with `thorctl`.
- `videoSetting()` reads OpenDE keys as `True`/`False` (also `Verdadeiro`/`Falso`) or an integer. Enum keys hold the **menu index**, clamped to range: Anisotropy 0-4, Multisampling 0-3, DetailDistance 0-2, VSync 0-2 (Off/On/Adaptive), FrameRateLimit 0-7 (Off, 30, 60, 75, 120, 144, 165, 240), AmbientOcclusion 0-3, UIScale 0-11, PerformanceHUD 0-2, FieldOfViewIndex 0-12 (60 + 5×index degrees).
- `UseTrilinear`: the renderer reads it from `[WinDrv.WindowsClient]`, while the menu seeds its switch from `[OpenGLDrv.OpenGLRenderDevice]`. Set both if the menu should agree.
- The section for video keys is whatever `[Engine.Engine] ViewportManager` names (`WinDrv.WindowsClient` on the test device).

## When the App Reads and Writes

OpenDE loads the inis at start and saves `DeusEx.ini` when options change (menus, gyro/perf toggles), so stop the app before editing. Not verified whether every option applies live.

## Not Verified

No setting was changed and checked in game. The menu labels for Brightness and the resolution keys were not checked. Save path is from source; not confirmed with a real save.
