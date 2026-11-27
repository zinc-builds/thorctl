---
name: cocoon-library
description: Read and change anything in the Cocoon front-end (rip.moth.cocoonshell) on the AYN Thor without driving its menus - any Settings option (theme, dock, grid, hero, audio, scraping, screens), wrong art or names, adding or removing games, platforms and ROM folders, which emulator ("player") a platform launches, home-screen folders, and the automatic ROM import watcher (cocoon-sync). Use whenever the task touches Cocoon's settings, what shows up in Cocoon, or how it launches games.
---

# Cocoon Library Work

The tool is `thorctl` (on PATH; set `ANDROID_SERIAL` when several devices are attached). Its source is the repo root, two levels above this skill after resolving symlinks; every path below is relative to that root. **Read its `README.md` first**: it documents the DB schema, how writes work, the watcher, and per-platform emulator notes. This skill is the workflow summary. Device basics are in the `thor-device` skill.

## Settings (Any Menu Option)

Never navigate Cocoon's menus to change a setting. Every option is a prefs key:

```bash
thorctl settings find WORDS                # keys + Settings pages; current values
thorctl settings get 'glob*' [--all]       # --all adds unset keys with defaults
thorctl settings set KEY=VALUE [...]       # validated, ~2 s, Cocoon restarts, verified
thorctl settings set scrape_config.FIELD=VALUE   # one field of a JSON setting
thorctl settings set --unset KEY           # back to default
thorctl settings watch --seconds 60        # key unclear? change it once on device, read the key
thorctl settings open "Label" | TAB:CARD   # jump straight to a Settings card
thorctl shot DIR                           # both screens, to confirm the visible effect
```

- "no catalog for Cocoon X" after an update: run `catalog/rebuild.sh` (3 min), then retry.
- Things with no stored value (start a scrape, theme store downloads, backup/restore, sign-ins): `settings open` the card, then drive it with `ui` (below).

## Driving the Screen

Never use raw `input tap` coordinates or screenshots-and-guess first. The `ui` agent reads both screens' labels and presses real controller buttons:

```bash
thorctl ui tree [-d bottom]        # what is on screen, with centre coords
thorctl ui click "Label"           # click by label; ui wait "Label" [--gone]
thorctl ui type "text"             # Cocoon's keyboard (clipboard + Paste); B is backspace there
thorctl ui pad DOWN A | B | Y      # real controller presses; Y = item menu, B = back, X on home swaps screens
thorctl ui home "Name" [--open]    # reach a home tile or a game in a manual folder, name-verified
thorctl ui focused                 # which grid item has focus
```

Toggle on/off states are not in the tree; read them with `settings get`. Grid tiles have no labels; use `ui home` / `ui focused`. Take a `shot` when you need to see artwork or layout.
- After a `set`, take a `shot` when the change is visible, and tell the user the old files' backup folder it printed.

## Core Commands

```bash
thorctl games -m "text" -p platform      # find game ids
thorctl sql "SELECT ..."                  # read-only live query
thorctl sql --write "UPDATE ...;"         # backup + transaction + Cocoon restart
thorctl rename ID "Name"
thorctl sgdb-search "Title"               # SteamGridDB game ids
thorctl set-art ID=SGDBID [...] [--dry-run] [--asset boxArt=ASSETID]
thorctl set-art-file ID --asset boxArt=PATH --asset logo=PATH --asset hero=PATH
thorctl sync-status | sync-install | sync rescan <platform>...
```

Every write backs up the DB to `/data/local/tmp/cocoon_db_backup_<time>` and restarts Cocoon; never swap DB files (Cocoon is the home app and respawns).

## Fixing Art

1. Find the SteamGridDB id: `sgdb-search`, or for Steam games `sgdb.Client.game_by_steam_appid(appid)` (404 = not on SGDB; fall back to name search).
2. `set-art` uses the first 1024x1024 static grid as icon. It fails with "has no boxArt" when none exists: list any-size grids via `client._get("grids/game/<id>")` and pass `--asset boxArt=<assetid>` (512x512 or crop).
3. Nothing on SGDB at all: use Steam's CDN (`cdn.cloudflare.steamstatic.com/steam/apps/<appid>/{library_600x900.jpg,logo.png,library_hero.jpg}`), centre-crop the cover square with `sips -c 600 600`, then `set-art-file`.
4. Duplicated or wrong art across games: `thorctl art-dupes`.
5. Recomps and other Android-app ports: use the SGDB id of the game being ported, not the port's name (`thorctl sgdb-search "<original game>"`; the ids in use on this device are in `local/README-device.md` when present). Android apps Cocoon never scraped point at its private `android_app_icons/`; `set-art` writes their art to `downloaded_media/android_app/{icon,logo,hero}/` instead. Preview candidates before applying: `client.assets(kind, id)` lists them in rank order.

## Removing Games

Delete from `games` **and** from `grid_membership` / `grid_placement` (`itemType='GAME' AND itemId IN (...)`); those tables have no FK. A deleted ROM row comes back on rescan unless the file is gone; use Hide to keep a file but hide it. Uninstalled Android apps keep rows with `androidPackageAvailable=0`; delete them too.

## Adding a Platform or ROM Folder

- New platform for an existing folder on the SD card: start `SettingsActivity` with `settings_discovered_platform_id/_name/_folder_uri/_folder_name` extras (see README) and confirm the Add Platforms dialog. This only works where Cocoon already holds a SAF grant (SD `Roms` tree).
- Folder on internal storage or anywhere new: Settings → Library & data → scroll to the platform → **Add new ROMs folder** → DocumentsUI → Use this folder → Allow. Keep "Include subfolders" off unless needed.
- Adding a platform can make Cocoon create its own `BY_PLATFORM` smart folder on the home grid; check `folders` for duplicates and delete the extra (plus its grid rows).
- Home-screen folders: `folders.isSmartFolder=1, smartFolderType='BY_PLATFORM', smartFolderQuery='<platformId>'` auto-include every game of that platform. Manual folders need `grid_membership` rows per game.

## Players (Which App Launches a Platform)

- Table `players`: `amStartArguments` uses newline-separated am args with `{file.uri}`, `{file.path}`, `{tags.<key>}` placeholders. Tags come from `[key] value` lines inside small files (`.dpt`, `.steam`); for PC storefront files (`.steam`) Cocoon also takes the first plain line as `app_id` and sets `game_source`.
- Cocoon uses the first **installed** player by `sortOrder` unless `default_player_<platform>` is set in `cocoon_settings.xml`, or chosen in the platform's settings page.
- To add an app Cocoon doesn't know (e.g. DroidDeck), `INSERT` a row (copy columns from a sibling row, `sortOrder` -1). A Cocoon update may rewrite the list; re-check after updates.
- Find an emulator's real intent with jadx (see `thor-device`).

## Auto-Import Watcher (cocoon-sync)

- Root service started at boot; watches every enabled ROM folder's backing path and runs Cocoon's own Rescan for that platform, normalising multi-disc layout per `modes.conf`.
- `sync rescan` exit code 2 = "Cocoon busy": the screen is off, an app is in front, or Recents/a dialog has focus on display 0. Wake, go Home (`am start --display 0 -a android.intent.action.MAIN -c android.intent.category.HOME`), retry.
- It reloads its folder list when Cocoon's prefs change and the enabled `rom_folders` differ; `sync-install` forces a reload.
- Change `device/cocoon-sync/` sources, then `sync-install`. Disc tests: `device/cocoon-sync/tests/test_discs.sh`.

## Steam / PC Games

DroidDeck writes `.steam` files to `/storage/emulated/0/Roms/Steam` every 30 s while running → watcher imports them into the `windows` platform → the home "Steam" smart folder shows them → player `windows.droiddeck` launches with `LAUNCH_GAME --es app_id`. New games only get scraper art; fix with the art steps above.
