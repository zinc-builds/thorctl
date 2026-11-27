# God Hand Android (com.owaissseeee.godhand)

Adapter: `apps/godhand.json` (13 keys). Checked 2026-11-27 against an install on the AYN Thor and the decompiled APK (`SettingsRepository`, `ui/SettingsDialog`, `MainActivity`, `IsoCacheProcessor`, `NativeBridge`).

## Build Checked

- Checked against versionName `1.0.0-godhand-recomp`, versionCode 1. Releases at `github.com/owaissseeee/godhand-android-port`: Beta (2026-10-25), v2.1 (2026-11-21), v2.2 (2026-11-22). The versionName does not identify which release it is.
- Before the first launch there are no prefs or files. The adapter comes from the APK; no setting has been checked against a written file.

## What It Is

A static recompilation of the PS2 game (upstream `github.com/LasVola/godhand-recomp`, GPL-3.0) with PCSX2's GS renderer (`libpcsx2gs.so`) and a Kotlin launcher with touch controls.

## Files

| Path | What it holds |
|---|---|
| `/data/data/com.owaissseeee.godhand/shared_prefs/godhand_settings.xml` | All settings and the custom touch layout. |
| `.../files/godhand_cache/` | Extracted disc (SLUS_215.03, AFS archives, MODULES). |
| `.../files/` | Memory cards `Mcd001.ps2`/`Mcd002.ps2` and save states (sub-folder not confirmed). |

## Write Rules (`prefs`)

- All index settings are `<int>`; volume and touch opacity are `<float>`; toggles `<boolean>`.
- Values are clamped on read (resolution 0-7, aspect 0-2, fps 0-1, frameskip 0-4, others 0-2).
- Missing keys take the defaults in the JSON.

## When It Reads

Renderer, resolution, aspect, FPS and frameskip are passed to native code when the game surface is created; renderer, aspect and FPS are locked while a game runs. Resolution, aspect, frameskip, audio and volume also have live setters used by the in-game dialog. Force-stop before editing.

## UI Tests Still Needed

- First launch: pick your God Hand (USA) `.iso`, let it build the cache, and confirm `godhand_settings.xml` appears after changing one setting.
- Set `res_idx`=3 (2x) and `fps_idx`=1 through the adapter and confirm the launcher shows them.
