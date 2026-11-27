# Super Metroid (com.raekwon.supermetroid)

Adapter: `apps/supermetroid.json` (17 keys). Checked 2026-11-27 against the release APK on an AYN Thor and the source of [Raekwon1603/super_metroid-android](https://github.com/Raekwon1603/super_metroid-android) (fork of [snesrev/sm](https://github.com/snesrev/sm)).

## Checked Build

- versionName `0.1`, versionCode 1.
- APK SHA-256 `57dddd0b…8f` equals the release assets of both v1.1 (`Super.Metroid.Dual.Screen.apk`) and v1.2 (`app-debug.apk`). v1.2 (2026-09-08) is the last release; the author has moved to MetroidArch, a dual-screen RetroArch fork.
- The app was not launched during the check, so every key is `verified_on_device: false`.

## Files

| Path | What it holds |
|---|---|
| `/sdcard/Android/data/com.raekwon.supermetroid/files/sm.ini` | Engine settings. Copied from the APK by `SetupActivity.installDefaultIniIfMissing` on first launch. The adapter carries the same text as `template`. |
| `/data/data/com.raekwon.supermetroid/shared_prefs/secondscreen.xml` | Bottom-screen Setup tab: `showStatusOnMap`, `hideMainHud`, `autosaveOnExit` (bools), `mapPins` (string). |
| `…/files/sm.smc` | The ROM, copied there from the document picker. |
| `…/files/saves/` | `sm.srm` (+ `.bak`) in-game SRAM, `save%d.sav` states, `autosave_thumb.bin`. |

## Write Rules (`ini`)

Source: `src/config.c`, `src/main.c`, `src/platform/android/android_impl.c`.

- Same snesrev format as Zelda3: `Key = Value`, `#` comments, `ParseBool` accepts 0/1/true/false/yes/no/on/off. `Autosave` uses `strtol` (digits only).
- The native code `chdir`s to the external files dir, then reads `sm.user.ini` if it exists and otherwise `sm.ini`. They are not merged: a partial `sm.user.ini` would drop every other setting. Do not create one.
- The app never writes `sm.ini` after the first copy, so in principle editing while the app runs is harmless, but the prefs file is held in memory, so `stop_before_write` is true.
- Ignored on Android: `OutputMethod` (always SDL_Renderer; `opengl.c` is not compiled), `Fullscreen`, `WindowSize`, `WindowScale`. `AutoRun` does nothing: gameplay runs on snesrev/sm's bundled 65816/SPC700 emulator core, and AutoRun was a hook in the decompiled C.
- No widescreen or `ExtendedAspectRatio` in this port (the parser has no such key).

## Editing Before First Launch

The external files dir does not exist before the first launch. `thorctl app set supermetroid …` would create `sm.ini` from the template; the app then keeps it because it only copies when missing. Launching once (and picking the ROM) first is cleaner, because it creates the dir with the app's own ownership.

## Controls Notes

- `[GamepadMap] Controls` ships as `…, B, A, Y, X, Lb, Rb`; `main.c` additionally swaps A/B on Android for the Thor's Nintendo layout.
- L2/R2 cycle armed ammo; on the Thor this is done in `MainActivity.dispatchKeyEvent` (keycodes 104/105), not through `CycleAmmoNext/Prev` in the ini.
- Quicksave `L1+R1+Start`, quickload `L1+R1+Back` (slot 0).

## Not Verified

Nothing was run. To finish the check: launch the app once, pick the ROM, and re-check the ini and prefs.
