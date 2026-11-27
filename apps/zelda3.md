# Zelda3 (com.dishii.zelda3)

Adapter: `apps/zelda3.json` (39 keys). Checked 2026-11-27 against v2.0 on an AYN Thor and the source of [samyost1/zelda3-android](https://github.com/samyost1/zelda3-android) at tag **v2.0** (fork of Waterdish/zelda3-android, itself a port of [snesrev/zelda3](https://github.com/snesrev/zelda3)).

## Checked Build

- `dumpsys package`: versionName `2.0`, versionCode 5.
- APK SHA-256 `ccea2445…73df` equals the v2.0 release asset `zelda3-dualscreen.apk`. v2.0 is the latest release.

## Files

| Path | What it holds |
|---|---|
| `/sdcard/Android/data/com.dishii.zelda3/files/zelda3.ini` | All engine settings: `[General]`, `[Graphics]`, `[Sound]`, `[Features]`, `[KeyMap]`, `[GamepadMap]`. |
| `/data/data/com.dishii.zelda3/shared_prefs/secondscreen.xml` | `hideTopHud` only. |
| `…/files/zelda3_assets.dat` | Game assets built from the ROM on first run. |
| `…/files/saves/` | `sram.dat` (+ `.bak`) in-game save; `save0.sav` autosave state, `save1.sav` quick save, `save2+` the four bottom-screen slots; `ref/` 13 reference chapter saves. |
| `…/files/map_pins.txt` | Bottom-screen map pins (absent until a pin is placed). |

## Write Rules (`ini`)

Source: `app/jni/src/src/config.c` (parser), `MinimapView.java` (`updateIni`, `readIni`).

- `Key = Value`, `#` comment lines. Section and key names are matched case-insensitively by the engine; the adapter writes them as they appear.
- Booleans go through `ParseBool`: `0/1`, `true/false`, `yes/no`, `on/off`. The adapter uses `0`/`1`, as the app does. Exception: `Autosave` is parsed with `strtol`, so it must be a digit.
- A missing line means the engine default, which is 0/off for everything except `MSUVolume` (100). The adapter's `default` is the value in the v2.0 shipped `zelda3.ini`, because the file always exists.
- `ExtendedAspectRatio` is a comma list: optional `extend_y`, then `4:3`/`16:9`/`16:10`/`18:9`, then optional `unchanged_sprites`, `no_visual_fixes`. Any other token rejects the line.
- If `zelda3.user.ini` exists next to `zelda3.ini`, the engine reads it instead (no merge).

## When the App Reads and Writes

- The native game reads `zelda3.ini` once at start.
- The bottom-screen Settings list rewrites single lines in place, and inserts a missing key directly under its section header. Several rows also apply live (widescreen, CRT top, HUD). So stop the app before editing (`stop_before_write: true`).
- `MainActivity` copies `zelda3.ini` from the APK only when the file does not exist. Updates never replace it, so an ini first copied by an older version lacks newer lines (such as `SecondScreenSwap`), keeps older defaults (`ExtendedAspectRatio = 4:3`; v2.0 ships `16:9`), and has keys the app inserted at the top of their sections.
- `SecondScreenSwap` is read by `SetupActivity` at launch; `EnableMSU` only at engine start.

## Bottom-Screen Settings Map

Rows 0-3 are actions (save states, remap, quick save, quick load). Then: AUTOSAVE `[General] Autosave`, WIDESCREEN `ExtendedAspectRatio` (4:3 ↔ 16:9 only), CRT TOP `[Graphics] CrtFilter`, CRT BOTTOM `[General] SecondScreenCrt`, HIDE TOP HUD (pref `hideTopHud`), X ITEM RING `SecondScreenXItemRing` (also forces `ItemSwitchLR = 1`), SWAP SCREENS `SecondScreenSwap`, MSU MUSIC `[Sound] EnableMSU`, then 12 feature toggles: ItemSwitchLR, TurnWhileDashing, MirrorToDarkworld, CollectItemsWithSword, BreakPotsWithSword, DisableLowHealthBeep (shown inverted as LOW HP BEEP), SkipIntroOnKeypress, ShowMaxItemsInYellow, MoreActiveBombs, CarryMoreRupees, CancelBirdTravel, DimFlashes (in `[Graphics]`). Turning ItemSwitchLR off also turns the X ring off.

## Not Verified

- Effect of `OutputMethod = OpenGL`/`OpenGL ES` and `Shader` on Android (not tried).
- `SecondScreenSwap` and `LinkGraphics` were not in the checked ini, so neither was seen in a real file.
- No setting was changed and checked in game in this pass.
