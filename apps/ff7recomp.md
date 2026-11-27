# FF7Recomp (com.ff7recomp)

Adapter: `apps/ff7recomp.json` (17 keys). Checked 2026-11-27 against an install on the AYN Thor and the decompiled APK (`LauncherActivity`, `GameInstall`). Project: `github.com/bhuiyah/ff7-recomp-android` (GPL-3.0).

## Build Checked

- Checked against versionName `1.1.40`, versionCode 109. Upstream was at 1.1.62 on 2026-11-26.
- The launcher downloads the game files from Steam and builds them on the device (on the Thor, build.log showed 523 MB of C compiled in 605 s, then linked). `FFNx.toml` and `save/` appear only after the game is first started.

## Files

| Path | What it holds |
|---|---|
| `/data/data/com.ff7recomp/shared_prefs/launcher.xml` | Launcher settings. Holds only `update_checked` until a setting is changed. |
| `.../shared_prefs/companion.xml` | Bottom-screen panel state (created when used). |
| `.../shared_prefs/steam.xml` | Steam sign-in (`appid`, `account`, `token`). Never print or copy. |
| `/sdcard/Android/data/com.ff7recomp/files/game/` | `ff7_en.exe`, `data/`, later `FFNx.toml`, `save/`. |
| `/data/data/com.ff7recomp/files/game/libff7.so` | The recompiled game (154 MB). |
| `/sdcard/Android/data/com.ff7recomp/files/mods/` | 7th Heaven mods. |

## Write Rules

- Edit `launcher.xml`. Choices are `<int>` indexes; toggles `<boolean>`.
- `FFNx.toml` is rebuilt from `FFNx.template.toml` before every start (`writeFfnxToml`: `renderer_backend`, `fullscreen`, `ff7_fps_limiter`, `speedhack_min`, aspect, FPS counter, mod options, render-scale cap). Hand edits to it are lost. The launcher's FFNx settings page stores its own overrides (storage not traced).
- `aspect` uses 0, 2, 3 (1 unused). `fps` 5 = 60 FPS with battles at 30.

## When It Reads

Read when Play is pressed; display options go to `GameActivity` as intent extras. Force-stop before editing.

## Recommended Mods (Checked 2026-11-27)

FF7Recomp has no official list; its launcher's **Get mods** shows the Qhimm and Sega 7th Heaven catalogs, and **Auto-sort** applies 7th Heaven's load-order rules. The community list is Kuraudo's "FF7 Must Install Mods" (forums.qhimm.com topic 21345, updated 2026-11-24): Cosmo Memory, Enhanced Stock UI + AavockESUI (or Finishing Touch, or Retouch; one of the three), 60/30 FPS Gameplay, Idle Animations 60fps, Ninostyle Chibi + Fixes and Additions, Ninostyle Battle, Shinra Archaeology Cut (not with Echo-S 7), Cosmos FMV 30 FPS (or SYW Unified FMV), SYW Unified Battle / Minigame / Spells textures, AxlRose Blender (below SYW Battle), Cosmos Limit Break (Upscaled + Extended Backgrounds, Background Uncrop, 99% Animated Fields), FFNx FF7Music, Cosmos Gaia.

Port-specific findings from the repo's issues: 60/30 FPS Gameplay works since 1.1.39 but is not needed (Settings > Frame rate decides); Cosmos Gaia world map fixed (#23) and its OpenGL ES model bug fixed in 1.1.63 (#92); Echo-S 7 voice crashes fixed (#91); Enhanced Stock UI + Battle+ avatars fixed in 1.1.63 (#93); movies decode on the CPU, so 30 FPS movie packs run warmer; keep mods in internal storage (SD-card mod folders slowed start-up, #76). A Thor Pro user runs ~27 of these together (#76).

## Mod Options

Mod options are stored in `files/mods/profile.xml`. Option IDs and values come from each mod's `mod.xml` (`ConfigOption` > `ID`, `Option Value`); for example Finishing Touch `Avatars` defaults to 8 (Tactics Portraits) and 0 means native portraits. The launcher keeps the profile while the game runs in the separate `:game` process; options are read at Play.

## UI Tests Still Needed

- Start the game once so `FFNx.toml` and `save/` exist; record the generated toml values.
- Confirm the Performance index order (0 Cooler, 1 Balanced, 2 Best) by setting `perf`=2 and checking the radio button.
- Set `fps`=4 (120) and check the in-game counter.
