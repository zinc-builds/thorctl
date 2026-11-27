# Luigi's Mansion Recompiled (com.personal.luigismansion)

Adapter: `apps/luigismansion.json` (20 keys). Checked 2026-11-27 against an install on the AYN Thor and the decompiled APK (`org.libsdl.app.GameSettings`, `OptionsView`, `DisplayRates`, `SaveBackup`).

## Build Checked

- Checked against versionName `1.2`, versionCode 3. The Android port's repo `github.com/JayElDragon/luigis-mansion-android` is at V3.2 (versionName 3.2.1, versionCode 8, 2026-11-18), so the checked build is older. Keys may differ in newer builds.
- Before the first launch there are no prefs or files. The adapter comes from the APK; no setting has been checked against a written file.

## Files

| Path | What it holds |
|---|---|
| `/data/data/com.personal.luigismansion/shared_prefs/lm.xml` | Launcher settings (source of truth). |
| `.../files/xdg/Luigi's Mansion Recompiled/settings.ini` | Engine config, regenerated from the prefs at every game start. |
| `.../files/xdg/Luigi's Mansion Recompiled/USA/` | Saves. |
| `.../files/xdg_dlc/Luigi's Mansion Recompiled/` | DLC (Premium Deluxe) engine data. |
| `/sdcard/Download/Luigi's Mansion Android/` | Automatic save backups (zip). |

## Write Rules

- Edit `lm.xml`. `GameSettings.write` runs in `MyGame.onCreate` and overwrites the managed keys in `settings.ini` from the prefs (list in the JSON file notes). Unmanaged ini keys (`[controls]` and others) survive.
- `settings.ini` lines are `key=value` without spaces.
- Prefs are ints, bools and floats as typed in the adapter. `g_msaa` is 1 or 4.
- On first launch the app writes a device-tier preset (`g_fps`, `g_res`, `g_msaa`, maybe `g_perf`) unless those keys already exist.
- Safe Mode (offered after a crash) saves the current values as `safe_bak_*`, forces 30 fps / 1x / no AA / no textures, and restores them when turned off.

## Frame Rate

Choices are 30, 60 and every display refresh rate from 62 to 240 Hz (120 is added if the display reports none). `target_fps` is capped at 60 by Performance Mode and lowered further by Auto Cool-down when the device is hot. `unlimited_fps` and `match_display_refresh` are always written false.

## UI Tests Still Needed

- First launch: link the game's `.rvz` (for example from `/storage/<sdcard>/Roms/Gamecube/`) and note which tier preset gets written.
- Set `g_fps`=120, `g_res`=2 through the adapter, start the game, and check `settings.ini` `[video] target_fps=120`, `resolution_scale=2`.
- Consider updating to V3.2.1 before relying on the adapter.
