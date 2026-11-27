# thorctl

Command-line access for AI agents (Claude Code, Codex and others) to a rooted AYN Thor: the Cocoon front-end (`rip.moth.cocoonshell`, v3.12), the settings of 35 emulators, recomps and ports, and both screens. An agent can read and change settings, art and the library without driving menus. Cocoon is closed source; everything here comes from its on-device data and a jadx decompile.

## What Is Here

| Path | What it is |
|---|---|
| `thorctl.py` | The CLI (`cocoonctl.py` is an alias). |
| `cocoonlib/` | Cocoon database and prefs, app settings, SteamGridDB, the UI agent client. |
| `apps/` | One adapter (`<name>.json`) and one research note (`<name>.md`) per emulator or recomp. |
| `recomps/` | Catalog of recomps, decompilations and source ports that run on the Thor (`CATALOG.md`). |
| `catalog/` | Every Cocoon setting key, built from the APK (`rebuild.sh` after a Cocoon update). |
| `device/cocoon-ui/` | The on-device UI agent (Java, run with `app_process`): reads both screens, clicks by label, sends controller presses. |
| `device/cocoon-sync/` | Optional on-device watcher that imports new ROMs into Cocoon. |
| `skills/` | Agent skills (`SKILL.md`): `cocoon-library`, `thor-emulators`, `thor-device`, `thor-home-and-navbar`. |

## Setup

Needs: a rooted Thor where `adb shell su -c id` works, `adb` over USB or Wi-Fi, and Python 3.9+ on the computer (standard library only).

```bash
git clone https://github.com/zinc-builds/thorctl && cd thorctl
ln -s "$PWD/thorctl.py" ~/.local/bin/thorctl          # or anywhere on PATH
# Two device binaries, from the latest release or built here:
gh release download -p sqlite3 -D device-bin && chmod +x device-bin/sqlite3      # or device-bin/build_sqlite3.sh (Android NDK)
gh release download -p cocoon-ui.jar -D device/cocoon-ui                          # or device/cocoon-ui/build.sh (JDK + Android SDK)
thorctl settings get theme                            # first check: reads Cocoon's prefs
```

Set `ANDROID_SERIAL` when more than one device is attached, and `THOR_SDCARD` to the SD card's volume id if auto-detection picks the wrong one. For the SteamGridDB commands, sign in to SteamGridDB inside Cocoon; `thorctl` reads that key from the device and never prints it.

Agents: link the skills into your agent's skills folder (for Claude Code, `ln -s "$PWD/skills/"* ~/.claude/skills/`). Start with `skills/cocoon-library/SKILL.md`.

## Private Notes (`local/`)

Facts about your own device (installed versions, your games, chosen settings) go in `local/`, which git ignores: `local/apps/<name>.md` beside each `apps/<name>.md`, `local/recomps/<package>.json` merged over each recomp entry, `local/skills/<name>.md`, and `local/cocoon-sync/modes.conf`. Agents read the public note first, then the local one if it exists. Keep personal data out of the tracked files.

## Safety

Writes go through checksums, back up the old file to `snapshots/` (git-ignored; it can hold secrets), and re-read the device to prove the change. Still: this edits app data as root. Use it on a device you can restore.

## Cocoon

```bash
thorctl games -m "zelda"                # id, platform, file, SGDB id, art source, md5
thorctl sql "SELECT id, fileName FROM games WHERE platformId='gba'"
thorctl sgdb-search "Game Title"
thorctl set-art 42=12345 --dry-run      # Cocoon game id = SteamGridDB game id
thorctl set-art 42=12345
thorctl sql --write "UPDATE games SET displayName='X' WHERE id=1"
thorctl rename 43 "New Name"            # displayName + title
thorctl art-dupes                       # games sharing an identical icon file
```

## Settings

Every option in Cocoon's menus is either a row in its database (platforms, players, folders: use `sql`) or a key in a SharedPreferences file under `/data/data/rip.moth.cocoonshell/shared_prefs/` (mostly `cocoon_settings`, `ui_prefs`, `audio_prefs`, `dock_prefs`). Cocoon reads them at start-up, so `settings set` writes the file and restarts Cocoon. A write takes about 2 seconds.

```bash
thorctl settings find dock hide          # keys + Settings pages matching the words
thorctl settings get 'hero_*' swap_screens
thorctl settings get --all 'now_playing*' # include keys not set yet (shows defaults)
thorctl settings set auto_hide_dock=true animation_speed=FAST
thorctl settings set scrape_config.replaceProtectedFields=true   # one field of a JSON setting
thorctl settings set --unset floating_folders                    # back to Cocoon's default
thorctl settings set dock_prefs:dock_slot_2=com.android.chrome   # FILE: prefix for a new key
thorctl settings watch --seconds 60      # print each key as it changes on the device
thorctl settings open "Dock settings"    # open Settings at that card (label, TAB:CARD, or Activity)
thorctl restart
thorctl shot /tmp/cocoon                 # both screens
```

- `set` checks values against Cocoon's own rules (enum options and ranges from its backup-restore validator), refuses keys Cocoon never uses, and asks for `FILE:` when a key is not set yet and its file is unknown. It saves the old files to `snapshots/prefs-<time>/` and re-reads the device after the restart to prove the values stuck.
- Secrets (API keys, passwords) print as `<redacted>`; `--reveal` shows them.
- **When a setting's key is unclear**, run `settings watch`, change it once on the device (or ask the user to), and the key, file and value print. `settings open` gets to the right card without menu navigation.

How a write works (Cocoon is the home app; Android respawns it within ~200 ms and Cocoon rewrites a whole prefs file from memory whenever it saves): freeze Cocoon with SIGSTOP, check each file still has the checksum it was read with, overwrite it in place (owner and SELinux label kept), delete any `.bak` (Android would restore it over the edit), force-stop, start the home activity on display 0 (Android only respawns the secondary-display home by itself), then re-read and compare.

### Settings Catalog

`catalog/cocoon-<version>.json` lists every SharedPreferences key Cocoon's code uses (368 in 3.12) with its type, default and file, the dynamic key families (`folder_zoom_<folderId>`, `default_player_<platform>`, `dock_slot_<n>` …), Cocoon's validation rules, and the 66-entry Settings search index (label, section, tab and card for `settings open`). `build_catalog.py` reads only things R8 does not rename: string keys, the `rip.moth.cocoonshell.backup.AppearanceRestorePlanner` rule tables, and the search index found by its section names.

**After a Cocoon update**, commands stop with "no catalog for Cocoon X". Rebuild it (about 3 minutes; needs `jadx` from brew):

```bash
catalog/rebuild.sh
```

`find`, `get`, `pages` and `open` fall back to the newest catalog with a warning; `set` refuses until the matching catalog exists. If the rebuild's sanity check fails, a code pattern in `build_catalog.py` changed.

### What Still Needs the UI

Actions that run inside Cocoon rather than change a stored value have no data path: starting a scrape, theme-store downloads, creating or restoring a backup, Hive/RetroAchievements sign-in. Use `settings open` to reach the card, then the `ui` commands below. Platform rescans already have a path (`sync rescan`).

## Driving the Screen (`ui`)

`device/cocoon-ui` is a small Java server (`cocoon-ui.jar`, run with `app_process` as the adb shell user like scrcpy; no root, no APK, nothing enabled in Settings). `thorctl ui …` starts it on first use (pushing a new build when the local jar changed) and talks to it over `adb forward tcp:17120 localabstract:cocoon-ui`.

```bash
thorctl ui tree [-d top|bottom]   # labelled elements on both screens, with centre coords (~0.2 s)
thorctl ui click "Dock settings"  # ACTION_CLICK on the element (or its clickable parent); a whole-label match beats a substring one
thorctl ui settext "zelda" [--field LABEL]  # ACTION_SET_TEXT on the first editable match (a search field, not the list row with the same text)
thorctl ui wait "Auto-hide" [--gone] [--timeout 10]
thorctl ui type "zelda"           # Cocoon's keyboard: sets the clipboard, presses Paste
thorctl ui pad DOWN DOWN A        # real controller presses (A B X Y UP DOWN LEFT RIGHT L1 R1 L2 R2 START SELECT MODE L3 R3)
thorctl ui home --list            # home grid + manual folders as rows/cols with names
thorctl ui home "Sega Saturn" [--open]   # D-pad there, confirm the name via the Y menu, then A
thorctl ui focused                # name of the focused grid item
thorctl ui tap X Y -d bottom | swipe … | key back|home|wakeup | settext | clip | stop
```

What was found on the Thor (Cocoon 3.12, 2026-11-27):
- Settings, menus and dialogs expose their text to accessibility; `uiautomator dump` only sees display 0, the agent reads every display. Toggle states are not exposed: read them with `settings get`.
- The home grid's tiles are not in the tree (only the dock and the X/Y hints are). `ui home` therefore counts D-pad moves from the database layout (`grid_placement` at `home_zoom_level`, or a manual folder's `folder_zoom_<id>`), anchored by LEFT…UP… onto the dock (or folder header) then DOWN = row 0, col 0, and checks the result by opening the item's Y menu and reading its name. Smart (platform) folders have no stored layout: open them and walk with `pad` + `focused`.
- Cocoon ignores `input keyevent` gamepad keys, but accepts events written into the built-in controller's evdev node (AYN's virtual "Xbox Wireless Controller", `/dev/input/event9`, writable by shell). On home, X swaps the screens (`swap_screens`), Y opens the focused item's menu, B closes it. While Cocoon's keyboard is up, B is backspace.
- Cocoon's text boxes are drawn labels, not Android text fields (`settext` fails); its keyboard has a Paste button, hence `ui type`.
- The agent drops its UiAutomation connection after 4 s idle so `uiautomator dump` (cocoon-sync) still works. It uses about 135 MB while running; `ui stop` ends it, and it does not survive a reboot (the next `ui` command restarts it).
- Rebuild after editing the Java: `device/cocoon-ui/build.sh` (JDK 17 + Android SDK).

## App Settings (`app`)

Emulators and other apps keep their settings in files: ini, Qt ini, RetroArch cfg, YAML, JSON or Android prefs XML. `thorctl app` reads and edits them directly. Each app has an adapter in `apps/<name>.json`: its files, its per-game file pattern, and a glossary of friendly setting names with their allowed values. `apps/<name>.md` holds the notes behind each adapter (sources, write rules, gotchas).

```bash
thorctl app list                                  # adapters + installed versions
thorctl app keys eden resolution                  # glossary entries matching words
thorctl app get dolphin                           # glossary settings with current values
thorctl app get dolphin --all                     # every key in the app's files
thorctl app set eden resolution=2x --dry-run      # a value's meaning or its raw value
thorctl app set eden resolution=2x --game <title id>         # per-game override
thorctl app unset eden resolution --game <title id>          # back to the global value
thorctl app set dolphin GFX:Settings/InternalResolution=4    # any key, as FILE:Section/key
thorctl app games eden                            # per-game files that exist
thorctl app restore ps3 snapshots/apps/armsx3-<time>   # put back the files a write replaced
thorctl app watch ps2                             # change a setting in the app; the file and key print
thorctl app get org.example.app --all --file /sdcard/.../x.ini   # any app, no adapter
```

Adapters (`thorctl app list`; notes in `apps/<name>.md`). Live-tested 2026-11-27 by writing a setting and seeing it in the app's own settings screen or in game, then reverting: eden (+ per game), dolphin (+ per game), armsx2 (+ per game), droiddeck (per game, in game), retroarch, duckstation (+ per game), ppsspp, azahar, cemu, vita3k (start-up rewrite kept it), watermelonds (per game), armsx3, skies, dusklight (in game), zelda3 (in game). The rest are read-checked against the device only; many recomps have no settings file until first launch.

Emulators and apps: `armsx2` (ps2), `armsx3` (ps3, rpcs3), `azahar` (3ds, lime3ds, citra, n3ds), `cemu` (wiiu, wii-u), `dolphin` (gc, wii, gamecube, ngc), `droiddeck` (steam, pc), `duckstation` (psx, ps1, psone, playstation), `eden-nightly` (switch-nightly, eden nightly), `eden` (switch), `hakux` (xbox, ogxbox, xbox1, haku, haku_x, xemu), `pico8` (pico8, pico-8, pico), `ppsspp` (psp, ppssppgold, ppsspp-gold), `retroarch` (ra, libretro), `vita3k` (vita, psvita, vita3k), `watermelonds` (nds, ds, melonds, melondualds, watermelon), `xendroid` (xbox360, x360, xenia, 360).

Recomps: `am2r`, `banjorecomp`, `dualsouls`, `dusklight`, `ff7recomp`, `godhand`, `lighthouse`, `luigismansion`, `majoraremasked`, `mareshine`, `metroidfusion`, `opende`, `papercut`, `pokedaisy`, `skies`, `smwr`, `supermetroid`, `tmc`, `zelda3`. What each recomp is: `recomps/CATALOG.md`.

- Writes refuse while the app is running: most emulators rewrite their config from memory when they close, which would undo the edit. `--stop` force-stops the app first (this ends a game in progress). Each write checks the file has not changed since it was read, keeps owner and SELinux label, saves the old file to `snapshots/apps/<app>-<time>/`, and reads the result back.
- `watch` is how to learn a key the glossary lacks: start it, change the option in the app's own menu (by hand or with `ui`), and the exact file, key and old -> new value print. Add what you learn to the adapter.
- Eden's Qt ini needs `key\default=false` next to a value for it to take effect; per-game files also need `key\use_global=false`. The `qtini` and `qtini-game` formats write those flags, and `unset` sets `\default` (global) or `\use_global` (per-game) back to true.

### Coverage and New Emulators

```bash
thorctl app coverage            # every installed emulator/recomp: covered, draft or missing; NEW = first time seen
thorctl app discover <package>  # draft local/apps/<name>.json + .md from the app's real config files
thorctl app autodiscover        # discover every NEW app that has no adapter (what the daily job runs)
```

- Candidates are the apps Cocoon launches games with (its `players` table), apps in the Recomps folder, apps in the recomp catalog, and packages whose name looks like an emulator or port.
- `discover` finds the app's config files under `/data/data/<pkg>` and `/sdcard/Android/data/<pkg>` (skipping logs, caches and data files), reads every key with its current value and type, pulls the APK to look for its source repository, and writes a draft adapter (`"draft": true`, raw keys only) plus a research brief. `get`, `set` (raw values) and `watch` work on a draft straight away.
- Finishing a draft is agent work: hand it `apps/<name>.md`. It fills labels, allowed values, defaults and per-game rules from the app's source, then removes `"draft"`.
- `autodiscover.sh` is meant for a daily launchd job (for example `~/Library/LaunchAgents/com.thorctl.autodiscover.plist`, logging to `~/Library/Logs/thorctl-autodiscover.log`): it finds the Thor on Wi-Fi adb, drafts adapters for newly installed apps, and posts a macOS notification when there is a brief to finish. It runs no agent and costs nothing.
- Variants of an app with a different package (Eden Nightly) use `"extends": "<base adapter>"`; every path is rewritten to the new package.

## Recomps Catalog

`recomps/CATALOG.md` (and `catalog.json`) lists every recomp, decompilation port and fan remake checked on the Thor: the original game, the project and its repository, the version checked, update channel, what game data it needs, settings adapter, controls, display behaviour and save locations. Each app has one source file, `recomps/entries/<package>.json` (schema in `recomps/ENTRY_SCHEMA.md`); `thorctl recomps build` merges them. Device-specific facts (installed version, Cocoon game id, whether the game data is present, your own ROM paths) go in `local/recomps/<package>.json`, which is not committed; when it exists, `build` also writes the merged catalog to `local/recomps/CATALOG.md`.

```bash
thorctl recomps                 # one line per recomp
thorctl recomps show banjo      # the full entry
thorctl recomps build           # rebuild CATALOG.md / catalog.json after editing entries
```

## Automatic Import (`cocoon-sync`)

Cocoon only looks for new ROMs on its first resume after starting, or every 6 hours. Even then it only posts a "new games found" notification and waits for you to review it. A full rescan also re-adds any entry you deleted, because Cocoon has no ignore list; only **Hide** survives a rescan. `device/cocoon-sync` removes the manual step:

- A root watcher, started at boot from `/data/adb/service.d/cocoon-sync.sh`, uses `inotifyd` on every enabled ROM folder's backing path (`/mnt/media_rw/...`). It blocks while nothing changes, so it adds no wakeups.
- When a game file is written, renamed or deleted, it waits until the folder has been quiet for 10 s and no file has changed for 20 s (a copy in progress keeps updating mtime).
- It then normalizes the multi-disc layout for that platform and runs Cocoon's own **Rescan Games** for just that platform. It does this by starting Cocoon's settings screen as root with `settings_discovery_rescan_platform_ids` and tapping start and OK, found through `uiautomator` on display 0. Cocoon ignores injected gamepad keys.
- If anything other than Cocoon is in front (a game, another app) or the screen is off, it waits and retries every 60 s.
- Deleted files are dropped from Cocoon the same way. The watcher also reacts to Cocoon's own discovery results. It reloads its folder list whenever a Cocoon prefs write coincides with a change to the enabled `rom_folders`, so a ROM folder added or removed in Cocoon is picked up without a restart.

Multi-disc layout per platform is set in `modes.conf` on the device (`/data/adb/cocoon-sync/modes.conf`; reinstalling keeps your edits). The first install copies `local/cocoon-sync/modes.conf` when it exists, else the example in `device/cocoon-sync/modes.conf`:

| Mode | Layout | Use For |
|---|---|---|
| `group` | `Name (Disc N).ext` in the folder and no `.m3u`. Cocoon shows one entry and launches Disc 1. | DuckStation (cannot open a `.m3u` passed as `content://`, tested), ARMSX2 (no `.m3u` support) |
| `m3u` | `Name.m3u` in the folder, discs in `.hidden/` | RetroArch cores that read `.m3u` (Flycast, Beetle Saturn) |

The normalizer never deletes anything. It moves discs between the folder and `.hidden/`, and parks or replaces `.m3u` files inside `.hidden/`. In group mode it also renames `Name CD-1.ext` to `Name (Disc 1).ext`. Tests: `device/cocoon-sync/tests/test_discs.sh`.

```bash
thorctl sync-install                  # push, (re)start the watcher, install the boot script
thorctl sync-status                   # pid + last log lines (/data/adb/cocoon-sync/sync.log)
thorctl sync normalize psx --dry-run  # show what would move
thorctl sync rescan psx dreamcast     # normalize + rescan now
```

## Emulator Notes

- Cocoon launches each platform with the first **installed** app in its `players` list (by `sortOrder`), unless a `default_player_<platform>` pref is set. It does not check that a RetroArch core exists.
- RetroArch is the Play Store build: bundled cores are symlinks into the APK. It still loads a core `.so` copied into `/data/data/com.retroarch/cores/` (owner = the app's uid, mode 600, `restorecon`), taken from `https://buildbot.libretro.com/nightly/android/latest/arm64-v8a/`.
- N64: `mupen64plus_next_gles3_libretro_android.so` installs the same way; a game launched from Cocoon runs (tested 2026-10-23).
- Saturn: Beetle Saturn (`mednafen_saturn_libretro_android.so`) installs that way. It reads the BIOS files `mpr-17933.bin`, `sega_101.bin` and `saturn_bios.bin` from `/storage/emulated/0/RetroArch/system/`. Tested 2026-10-23: a steady 60 FPS, and a multi-disc game boots from its `.m3u`.

- Vita: Cocoon launches Vita3K with `{tags.vita_game_id}`, read from a `.dpt` file in the Vita ROM folder containing `[vita_game_id] <TITLEID>` (Daijishou `[key] value` tag format). Games must already be installed in Vita3K (`/storage/emulated/0/Vita3K/ux0/app/<TITLEID>`). `.pkg` subfolders are install sources and are ignored by the scan. A folder can be added with SettingsActivity extras `settings_discovered_platform_id/_name/_folder_uri/_folder_name`, which opens Cocoon's own Add Platforms picker.
- PS3: ARMSX3 1.3.2 from the official GitHub release (`ARMSX2/ARMSX3`, a13 build) needs All files access, PS3 firmware (4.92 tested) and a games folder. Cocoon's launch reaches ARMSX3 and starts the boot, but encrypted redump ISOs fail with "Invalid or unsupported file format ... EBOOT.BIN" and "missing key file". They need a `<same name>.dkey` next to the ISO, or decrypted ISOs or folder dumps. Starting an app with `am start --display 0` can leave Cocoon's bottom-screen activity on display 0; `am force-stop` Cocoon to restore it.
- GPU drivers (checked 2026-10-23):
  - Eden v0.2.1 standard (from `stable.eden-emu.dev`; `adb install -r` works over an Obtainium build) runs with Balemuni Apex v2 ULTIMATE, selected in Settings → GPU driver manager. The zips go in `Android/data/dev.eden.eden_emulator/files/gpu_drivers/`; MrPurple T30 works as a fallback. A test game boots.
  - Vita3K runs with MrPurple T30. Install it by hand as `files/driver/<zip stem>/` containing `meta.json`, the `.so`, `driver_name.txt` (the library name), and an empty `file_redirect/`, owned by the app uid with the app's MLS `chcon` label. Select it with `custom-driver-name:` in `Android/data/org.vita3k.emulator/files/config.yml`. A test game boots.
  - ARMSX2 2.8.4 (the official `a13-armv8.2-sdk33` APK updates 2.7.1 in place) runs with ARMSX2 Turnip axfl2-003 (bmdhacks/armsx2-turnip). Install it through Settings → Renderer → Graphics API **Vulkan** (the GPU Driver section is hidden while the API is Auto) → GPU Driver → Download → ARMSX2 · turnip. The prefs then show `renderer: vulkan` and `customDriverId: armsx2turnip-axfl2-003-…`. The driver's Adreno 7xx speedup needs ARMSX2 commit `5a5c24bc46` or later, which 2.8.4 has. With the Qualcomm driver, ARMSX2 enables nine driver-bug workarounds. `emulog.txt` in `<SD>/Android/data/com.armsx2/files/logs/` prints a `PerfLog:` line (FPS and EE/GS/VU/GPU load) every 30 s.
- DS: WatermelonDS 0.8.0.rc3 (`me.magnum.melondualds`, a melonDS-android fork, from the SapphireRhodonite/WatermelonDS GitHub release) installs alongside melonDS nightly. Cocoon's `nds` players list it at sortOrder 1, ahead of the nightly, so with no `default_player_nds` set Cocoon launches it (`-a me.magnum.melondualds.LAUNCH_ROM -e uri {file.uri}`). Vulkan at 6x internal resolution fills 1080p. The default layout puts the top screen on display 0 and the touch screen on the bottom display. Saves (`.sav`) and states (`.ml0`…) sit beside the ROMs and are shared with melonDS. Tested games run at 60 FPS (2026-10-23). The melonDS nightly APK changed signing key in 2.0.x, so it cannot update in place.
- Steam / PC: DroidDeck (`com.droiddeck.launcher`) serves as the PC frontend. The pipeline:
  1. **DroidDeck → files.** DroidDeck's frontend game-file sync (`shared_prefs/game_files.xml`, `folder` = `/storage/emulated/0/Roms/Steam`) writes `<Game>.steam` (contents: the Steam app ID) plus `images/` for every installed game. It rewrites the folder every 30 s while DroidDeck runs, so installs and uninstalls show up within half a minute. DroidDeck targets SDK 28 with legacy storage, so it can write anywhere on internal storage but not the SD card.
  2. **Files → Cocoon.** Add `Roms/Steam` as a Windows ROM folder (subfolders off); the `cocoon-sync` watcher imports new `.steam` files.
  3. **Folder.** A home "Steam" folder made as a smart `BY_PLATFORM windows` folder collects every Windows game. Adding the platform makes Cocoon create its own "Windows" smart folder; delete it if it duplicates yours.
  4. **Launch.** Add a Cocoon player `windows.droiddeck` by hand (sortOrder -1, and the default for Windows and `.steam`); it runs `-a com.droiddeck.launcher.LAUNCH_GAME -n com.droiddeck.launcher/.MainActivity --es app_id {tags.app_id} --es game_source STEAM`. Cocoon reads `{tags.app_id}` from the first line of the `.steam` file. DroidDeck also accepts GameNative's `app.gamenative.LAUNCH_GAME` and `droiddeck://game/<appid>`. If a Cocoon update rewrites its player list, re-add this row.
  5. **Art.** `set-art` with SteamGridDB IDs from `games/steam/<appid>` (`sgdb.Client.game_by_steam_appid`). When SteamGridDB has nothing, `set-art-file GAME --asset boxArt=PATH …` uses local images, such as Steam's `cdn.cloudflare.steamstatic.com/steam/apps/<appid>/{library_600x900.jpg,logo.png,library_hero.jpg}`. New games arrive with whatever art Cocoon's scraper finds.
- `set-art --asset boxArt=ID` picks a specific SteamGridDB asset (e.g. a 512x512 grid when no 1024 one exists). Games with no art yet get files in `downloaded_media/<platform>/<kind>/`; so do Android apps whose icon still points at Cocoon's private `files/android_app_icons/` (they land in `downloaded_media/android_app/{icon,logo,hero}/`).
- Recomps can show the original game's art: give each Recomps-folder entry the SteamGridDB game of the game it ports, not the port's name (for example Banjo: Recompiled uses Banjo-Kazooie, `thorctl sgdb-search "Banjo-Kazooie"`). Original games and multi-game hubs keep their own art.

## How Cocoon Stores Things

- Database: `/data/data/rip.moth.cocoonshell/databases/cocoon_db` (Room, WAL mode). The `games` table holds everything per ROM.
- Artwork: `boxArtLocal` (the icon), `logoLocal`, and `heroLocal` are SAF URIs into `/sdcard/Cocoon/downloaded_media/<platform>/{icon,logo,hero}/`. `screenshotLocal` follows the same pattern.
- `boxArtSource`/`logoSource`/`heroSource` are `legacy`, `scraped`, `user`, or `none`. A `user` value is kept by rescrapes while Settings → Scraping → Replace Protected Fields is off.
- User edits are named `<rom stem>__cocoon_edit_<game id>_<uuid>.<ext>`. A new file name also invalidates Cocoon's image caches.
- API keys (SteamGridDB, ScreenScraper, RetroAchievements) live in `shared_prefs/ui_prefs.xml`. `snapshots/` therefore contains secrets; keep it local.
- Logs: `/sdcard/Cocoon/scan_debug.log`, `cocoon-database-log.txt`, and per-session scrape reports in `/sdcard/Android/data/rip.moth.cocoonshell/files/scrape_reports/`.

## How Writes Work

Cocoon is the home app, so Android respawns it within about 200 ms of a force-stop. Its database can never be swapped while it is down. Writes therefore go through a static `sqlite3` binary (`device-bin/`, pushed to `/data/local/tmp/cocoonctl-sqlite3`) that shares SQLite's locks with Cocoon's connection:

1. `.backup` of the live database to `/data/local/tmp/cocoon_db_backup_<time>`.
2. Your SQL runs in one `BEGIN IMMEDIATE … COMMIT` transaction with `persist_wal` on, so root never deletes or recreates Cocoon's `-wal` file.
3. Cocoon is force-stopped and relaunched, so Room drops its caches.

To restore a backup, run `thorctl sql` to confirm the state first, then run this with root on the device:

```
/data/local/tmp/cocoonctl-sqlite3 /data/data/rip.moth.cocoonshell/databases/cocoon_db ".restore /data/local/tmp/cocoon_db_backup_<time>"
```

Run `device-bin/build_sqlite3.sh <amalgamation dir>` to rebuild the binary with the NDK.

## Driving the UI

The top screen is display 0 (1920×1080). The bottom screen is display 4 (1240×1080), where the grid lives. Use `adb exec-out screencap -p -d <physical id>` with the ids from `dumpsys SurfaceFlinger --display-id`. Use `input -d 4 tap x y` for taps and `input keyevent KEYCODE_DPAD_*` / `KEYCODE_BACK` for navigation. The first tap on an icon focuses it, and the second opens it. `grid_placement` (by `home_zoom_level` from `cocoon_settings.xml`) maps folders to grid cells. On a game, `KEYCODE_BUTTON_Y` opens its menu, Y again opens Edit, and `KEYCODE_BUTTON_A` selects.

Cocoon's text fields use its own on-screen keyboard. It ignores `input text` and key events, and it drops taps that come less than about a second apart. Send one `adb shell input -d 4 tap` per key with a 1 s pause, and give `adb` `</dev/null` inside `while read` loops, because otherwise it swallows the loop's input. Shift is one-shot. Prefer `thorctl rename` or `sql --write` over typing.
