# AM2R (com.companyname.AM2RWrapper)

Adapter: `apps/am2r.json` (32 keys). Checked 2026-11-27 against an install on the AYN Thor and [AM2R-Community-Updates](https://github.com/AM2R-Community-Developers/AM2R-Community-Updates) source at HEAD (`scripts/load_gameoptions.gml`, `scripts/save_gameoptions.gml`, `objects/oOptions*.object.gmx`). Labels from the APK's `assets/lang/english.ini`.

## Build Checked

- Checked against versionName `1.5.3`, versionCode 1005003 (the wrapper template's version). The game data (`assets/game.droid`) says **V1.5.5**.
- The APK is built with AM2RLauncher or the AM2R Autopatcher from an `AM2R_11.zip` you supply, and installed with the system package installer.
- GameMaker runner, armeabi-v7a only (32-bit), target SDK 23.

## Files

| Path | What it holds |
|---|---|
| `/data/data/com.companyname.AM2RWrapper/files/config.ini` | All options. Owned by the app's uid, mode 600. |
| `/data/data/com.companyname.AM2RWrapper/files/save1` | Save slot 1 (`save2`, `save3` when used). |

## Write Rules (`ini`)

- GameMaker `ini_write_real` format: `Key="1.000000"`, no spaces, every value a double-quoted real with six decimals. The adapter's raw values include the quotes; pass a meaning (`On`, `2X`, `Toggle`) or the quoted raw value.
- `ini_read_real` would also accept `1` or `"1"`, but keep the app's own format.
- Private storage: needs root. Keep the owner and mode when writing.

## When the App Reads and Writes

`load_gameoptions` runs at game start; if `config.ini` is missing it writes one with defaults. The Options menus call `save_gameoptions`, which rewrites the whole file. Stop the app before editing.

## Value Notes

- `Scale`: 0 = Stretch (fullscreen only), 1-4 = 1X-4X.
- `ShowHUDCounter`: 0 Disabled, 1 Local, 2 Global.
- `AimStyle` 0 = 1 Button, 1 = 2 Buttons. `MissileStyle` 0 = Hold, 1 = Toggle. `MorphStyle` 1 = Classic Morph Ball on. `SpiderballStyle` 0 Toggle, 1 Classic, 2 Hold.
- `TouchScale` 1-8; the menu shows 9 minus the stored value.
- `Extras/Controller` picks the button glyphs in on-screen tips: 0 XBox (default), 2 Nintendo Pro matches the Thor's labels.
- `Widescreen` needs a room transition to apply in game.
- Pad button ids (`JoystickButton*`, `XBJoypadButton*`) are left out of the adapter; remap them in the game's Joypad menu.

## Not Verified

Source is AM2R-Community-Updates HEAD, not a 1.5.5 tag (the repo has no tags or releases). No setting was changed and checked in game. `LowEnergyNotificationStyle` meaning not traced.
