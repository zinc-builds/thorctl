---
name: thor-emulators
description: Set up, update, configure (any setting, global or per game, without menus) and benchmark emulators on the AYN Thor - Switch (Eden), Vita3K, PS2 (ARMSX2), PS3 (ARMSX3), DS (WatermelonDS/melonDS), 3DS (Azahar), RetroArch cores (Saturn, N64), PSX, Dreamcast, PC/Steam (DroidDeck) - including custom Adreno/Turnip GPU drivers, BIOS placement, hiding on-screen controls and measuring performance. Use when installing or updating an emulator, swapping GPU drivers, or debugging how a game runs.
---

# Thor Emulators

## Changing Settings (Do This, Not Menus)

`thorctl app` edits emulator settings in their own config files; adapters exist for **eden** (switch), **dolphin** (gc/wii), **armsx2** (ps2), **retroarch** (ra) and **droiddeck** (steam/pc). Notes per app (write rules, gotchas, sources): `apps/<name>.md`, plus `local/apps/<name>.md` for this device's own state when it exists. Put new device-specific findings (installed versions, games, chosen values) in the `local/` file, never in `apps/`. Paths here are relative to the repo root (two levels above this skill, after resolving symlinks).

```bash
thorctl app keys eden resolution          # find a setting: name, UI label, allowed values
thorctl app get dolphin                   # current values (defaults shown when not in file)
thorctl app set eden resolution=2X        # meaning or raw value; refuses while the app runs
thorctl app set ps2 upscale=3x --game <disc serial>   # per-game override, e.g. SLUS-XXXXX
thorctl app set steam dxvk_hud=fps --game <appid>     # DroidDeck per Steam app id
thorctl app unset eden resolution --game <title id>
thorctl app watch dolphin                 # learn an unknown key: change it in the app, read the diff
```

- The app must be closed: emulators rewrite their config from memory. `--stop` force-stops it (ends a running game). Every write is backed up to `snapshots/apps/` and read back.
- To confirm an effect, open the app's settings with `thorctl ui` (labels and toggle states are readable in all five apps) or take a `thorctl shot` in game. For Steam games, `dxvk_hud=fps` is a quick visible check.
- Start any Thor emulator task with `thorctl app coverage`. For an app marked missing or NEW: `thorctl app discover <package>` drafts the adapter from the device, then finish it by following the research brief it writes (`local/apps/<name>.md`, schema `apps/SCHEMA.md`; move the finished adapter and generic notes to `apps/`), and test one write through the app's own UI. `autodiscover.sh` drafts newly installed apps; when it runs as a daily launchd job (README → Coverage and New Emulators), check its log first.
- Recomps and ports: `thorctl recomps` (catalog in `recomps/CATALOG.md`; this device's install state in `local/recomps/CATALOG.md` when present) says what each one is, where its game data and saves live, how it updates, and which adapter holds its settings.

Device control basics: `thor-device` skill. Library and launch wiring: `cocoon-library` skill. Per-platform notes and exact paths: `README.md` → Emulator Notes.

## Current Setup

`thorctl app list` shows the installed emulators and versions. If `local/skills/thor-emulators.md` exists, it records this device's setup (apps, versions, GPU drivers, preferences); read it before changing an emulator.

Never source BIOS files, keys or games yourself; the user supplies them.

## GPU Drivers (Adreno 740)

Driver packs are zips with `meta.json` + a `.so`. Sources: Balemuni/Balemunis-Aurora (Apex), MrPurple666/purple-turnip (T-series), bmdhacks/armsx2-turnip (ARMSX2-specific), Banners-Turnip. Verify GitHub `digest`.

- **Eden**: push zip to `/storage/emulated/0/Android/data/dev.eden.eden_emulator/files/gpu_drivers/` (chown to the app uid, group `ext_data_rw`, 660), then Settings → GPU driver manager → select. Active driver is extracted to `/data/data/<pkg>/files/gpu_driver/` on next game start.
- **Vita3K**: install by hand: `/data/data/org.vita3k.emulator/files/driver/<zip stem>/` containing the zip contents, `driver_name.txt` (library name + newline), empty `file_redirect/`; chown app uid, `chcon` the app's MLS label; set `custom-driver-name:` in `Android/data/org.vita3k.emulator/files/config.yml`.
- **ARMSX2**: Settings → Renderer → Graphics API must be **Vulkan** (the GPU Driver section is hidden on Auto) → GPU Driver → Download → ARMSX2 · turnip. The axfl2 driver's 7xx speedup needs ARMSX2 >= commit `5a5c24bc46` (2.8.4 has it). Prefs: `customDriverId` in `shared_prefs/ARMSX2.xml` `config.global`.
- **WatermelonDS**: Settings → Video → Renderer (default Software! set Vulkan) → Internal resolution 6x fills 1080p.

## Updating

- Check installed: `dumpsys package <pkg> | grep -E 'versionName|lastUpdateTime'`. Compare with GitHub releases / project sites, or Obtainium if the app is tracked there.
- `adb install -r`; on signature mismatch stop and ask (melonDS nightly 2.0.x re-signed). ARMSX2/ARMSX3 have in-app "check on launch" updaters that pop dialogs over games; dismiss with "Later" when automating.

## Hiding On-Screen Controls

- ARMSX3: `shared_prefs/ARMSX2.xml` `touch.visibilityMode=0`, `touch.pauseTapToReveal=true`.
- WatermelonDS: `soft_input_behaviour=always_invisible` in `me.magnum.melondualds_preferences.xml` (options: always visible / hide console buttons with controller / hide assigned / always invisible). Bind "Toggle Soft Input" or "Toggle Microphone" to a controller button for games that need them.
- Edit prefs only with the app force-stopped, then fix owner + label (`thor-device/scripts/fix-pref-owner.sh`).

## RetroArch Cores

Play Store RetroArch loads cores copied to `/data/data/com.retroarch/cores/` (owner = app uid, mode 600, `restorecon`), from `buildbot.libretro.com/nightly/android/latest/arm64-v8a/`. BIOS in `/storage/emulated/0/RetroArch/system/` (and `Roms/BIOS`).

## Measuring Performance

- **ARMSX2**: `scripts/armsx2-perflog.sh "Game (USA).chd" 6` prints `PerfLog: <fps> | EE GS VU GPU %` every 30 s plus the driver banner, backing up and restoring save states (ARMSX2 autosaves on exit). Launching without a state load boots the same attract sequence each run, so timed runs are comparable; GS at 99% = GS-thread bound. The log also lists the GPU-profile workarounds the driver triggers.
- **ARMSX3**: logcat tag `ARMSX3` prints `Framerate: N fps`.
- **WatermelonDS**: logcat tag `melonDS` prints `VulkanPerf[...]` lines (cpu ms per frame, presented frames per 2 s).
- **Eden**: logcat `YuzuNative` (pipeline cache, renderer).
- **Vita3K**: `Android/data/org.vita3k.emulator/files/vita3k.log`.
- Launch games with the exact Cocoon player intent (query `players.amStartArguments`) so the test matches real use.
