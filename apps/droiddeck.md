# DroidDeck Settings Adapter

Checked against DroidDeck **0.7.1** (versionCode 19, `com.droiddeck.launcher`) on 2026-11-27, on a rooted AYN Thor (Android 13, SD 8 Gen 2). Adapter: [droiddeck.json](droiddeck.json).

DroidDeck is open source (GPL-3.0): <https://github.com/Droid-Deck/DroidDeck>, tag `0.7.1`. Everything below comes from that tag's source plus read-only reads of the device. The pulled APK was also decompiled with jadx, but the source was enough.

## How DroidDeck Runs a Game

DroidDeck runs the real Steam client (ARM64 by default, x86-64 under FEX as an option) in Deck mode inside a proot Ubuntu runtime at `files/linuxfs`, under gamescope. Windows games run through Steam's compatibility tool: DroidDeck-Proton (ARM64EC Wine with FEX for x86 code; Box64 is not used, and the app ignores `BOX64_*`/`BOX86_*` variables). DXVK, VKD3D-Proton and FEXCore come from swappable `.wcp` packages. The GPU driver is Turnip (builds named like `DD-Turnip_v0.9.1`).

Every Proton launch goes through `/usr/local/bin/droiddeck-game-env` in the guest. At the `waitforexitandrun` step it reads `~/.config/droiddeck/game-environment.json`, merges `shared` with `games/<appid>`, and starts the game with that environment. **Per-game settings are mainly environment variables keyed by Steam app id.**

## Files

| id | Path | Format | Role |
|---|---|---|---|
| session | `/data/data/com.droiddeck.launcher/shared_prefs/session.xml` | prefs | All global settings, plus per-game texture filtering (`gameTextureFiltering`, a JSON string) |
| frame_gen | `.../shared_prefs/frame_gen.xml` | prefs | Global frame generation. Absent until frame generation is first set (Off) |
| game_env | `.../files/game-environment.json` | json | **Per-game and shared env vars, the source of truth.** Absent until the first override |
| guest_env | `.../files/linuxfs/root/.config/droiddeck/game-environment.json` | json | Generated copy that games read. Do not edit |
| game_proton | `.../files/linuxfs/root/.local/share/droiddeck-compat/games.json` | json | Per-game Proton picks. Absent until the first pick |
| compat_state | `.../droiddeck-compat/state.json` | json | Guest state: Proton tool list, default, auto picks. Read-only |
| components | `.../files/components/state.json` | json | DXVK/VKD3D/FEX packages per Proton build, and per game under `profiles` |
| wincomponents | `.../files/wincomponents.json` | json | VC++/d3dx9 installed per game. Leave to the app |

All files are owned by the app's uid (`u0_a<N>`), label `u:object_r:app_data_file:s0:c<N>,c256,c512,c768`. The cocoon writer keeps these for existing files; for new ones it copies the parent folder's owner and label and uses mode 660 (the app's own files are 600; DroidDeck reads either).

## Write Rules

1. **Stop DroidDeck before writing** (`stop_before_write: true`). `session.xml` and `frame_gen.xml` are SharedPreferences: the app keeps them in memory and rewrites the whole file on its next change. `components/state.json` is rewritten by auto-updates. When a session starts, `game_env` is published to `guest_env`.
2. **Edit `game_env`, never `guest_env`.** The app regenerates `guest_env` from `game_env` + `session` at every session start and whenever the display surface changes (the `SessionActivity` surface callback), so edits to `guest_env` are lost.
3. **Every value in `game_env` must be a JSON string or null.** `"60"` works; `60` does not. A single non-string value makes `GameEnvironmentStore.decode` throw (the per-game UI then fails), and `droiddeck-game-env` falls back to "invalid configuration; using inherited environment", which drops every DroidDeck variable, including the FEX preset, for every game. With cocoonctl, pass numeric values quoted (`'"60"'`, `'"3-7"'`). Enum values accept their meaning (`on`, `off`).
4. **Seed `game_env` before the first write** with exactly `{"version":1,"shared":{},"games":{}}`. `version` must be 1, otherwise the app rejects the file.
5. When reads happen:
   - Session prefs are read at session start. Some, such as the scaling filter, sharpness and texture filtering, are also pushed live from the in-session drawer.
   - `game_env` takes effect at the next **session start** (that is when it is published). The game then reads it at its next launch.
   - `game_proton` is watched live by the guest helper `droiddeck-steam-compat` while a Steam session runs, and is applied to Steam's own `CompatToolMapping` through the Steam client's DevTools.
   - Component profiles are applied at the next session start (`ComponentsManager.republish`).
   - In practice: stop the app, edit, then launch the game (Cocoon's `LAUNCH_GAME` intent starts a fresh session).

### Cocoon Tool Gap (Needs a Fix in `cocoonlib`)

`appconf.json_write` is called without `create=True` from `apps.plan_set`. It therefore refuses to add a key that does not exist yet (`games/<appid>/DROIDDECK_NO_STEAM does not exist`). That blocks every first per-game write. A dry run with `create=True` produced the correct output (all values strings). Suggested fix: in `plan_set`, pass `kw["create"] = True` for the json format when `spec.get("create")` is set or the glossary entry is per-game. Prefs `#` paths have a related limit: `gameTextureFiltering` must already exist in `session.xml` (as `{}`) before `gameTextureFiltering#<id>/...` can be written.

## Per-Game Semantics

The game id is the Steam app id (decimal). Each per-game setting lives in one of these places:

- **Environment** (`game_env` → `games/<id>/<VAR>`). This covers what the in-game **Settings** card and **Game environment** editor write:
  - *Start without Steam* sets `DROIDDECK_NO_STEAM="1"`. The game launches through `droiddeck-proton-run` without the Steam client, for launches from DroidDeck and from Cocoon's `LAUNCH_GAME` intent.
  - *FEX preset* writes six `FEX_*` keys together. Exact per-preset values are in the `fex_tso` notes in the JSON.
  - *Wine sync* writes `BL_SYNC`, `BL_FSYNC_FIRST`, `BL_SYNC_FALLBACK` and `PROTON_NO_ESYNC`.
  - Any other variable: `DXVK_HUD`, `DXVK_CONFIG` (`dxvk.maxFrameRate = N` for a D3D9-11 FPS cap), `VKD3D_FRAME_RATE`, `VKD3D_FEATURE_LEVEL`/`VKD3D_SHADER_MODEL`, `PROTON_USE_WINED3D`, `WINE_D3D_CONFIG`, `WINEDLLOVERRIDES`, `TU_DEBUG`, `DROIDDECK_GAME_CORES` (core list such as `3-7`; it also sets `WINE_CPU_TOPOLOGY`), and so on.
  - A `null` value unsets that variable for the game. Variable names must match `[A-Za-z_][A-Za-z0-9_]*`, and values can be up to 8192 characters.
  - The app adds these defaults to `shared` when it publishes: `MESA_SHADER_CACHE_DISABLE=false`, `DROIDDECK_ANTICHEAT_OFFLINE=1`, `DOTNET_GCRegionRange=800000000`, `DOTNET_EnableWriteXorExecute=0`, plus the global FEX preset's variables (Performance + TSO by default, confirmed in `guest_env` on the test device). A game's own keys override them.
- **Proton** (`game_proton` → `games/<id>` = `{"valve":false,"dir":"DroidDeck-Proton 11-11.9"}`). `dir` is the tool's folder name. Valve tools (`"valve":true`) live in `steamapps/common`, for example `Proton Experimental (ARM64)`. To follow the default (`DroidDeck-Proton-11-11.9`), remove the entry or set it to `null`.
- **Component packages** (`components` → `profiles/<id>/{dxvk|vkd3d|fex}` = `.wcp` file name in `files/components/packages`). Package names look like `DD-dxvk-arm64ec-3.1.1+235-nightly.wcp`, `DD-vkd3d-proton-arm64ec-3.1+83-nightly.wcp`, `DD-FEXCore-2611+51-nightly.wcp`. The app also records `profiledComponents` when the UI does this; a hand edit can skip it. The app republishes and unpacks the packages at session start.
- **Texture filtering** (`session` → `gameTextureFiltering#<id>/anisotropy` (0/2/4/8/16) and `/lodBias` ("0", "auto", "-0.25" … "-1.0")). The app turns these into DXVK `samplerAnisotropy`/`samplerLodBias` for that game.
- The **Default** button (Settings menu) clears all of these for the game: environment, Proton, components, texture filtering and Windows components (`GameProfileManager.reset`).

### Settings That Are Not Per Game in 0.7.1

These are global only:

- Resolution (`displayResolution.steam`, the gamescope session size)
- Scaling filter, HDR
- Frame generation (`frame_gen.xml`; LSFG uses Lossless.dll from your own copy of Lossless Scaling, Steam app 993090)
- Game cores (`gameCpus`; per game, use `DROIDDECK_GAME_CORES` instead)
- GPU driver, controller type, DirectAudio

The FPS limit is Steam's own Quick Access frame limiter (a Steam client setting, not a DroidDeck file). Per game, use `DXVK_CONFIG`/`VKD3D_FRAME_RATE` instead. Launch options and controller layouts are Steam's (`localconfig.vdf`, Steam Input), and Steam rewrites them while it runs.

## Finding Games

- Installed games: `grep -H '"name"' /data/data/com.droiddeck.launcher/files/linuxfs/root/.local/share/Steam/steamapps/appmanifest_*.acf` (root). `StateFlags` 4 means installed, 6 means an update is required.
- Cocoon's `.steam` files: `/storage/emulated/0/Roms/Steam/<Name>.steam`, each containing just the app id. DroidDeck's `game_files` prefs point at this folder.
- `files/steam-appinfo.json` maps ids to names.

Steam runtime and tool ids that are not games: 228980, 1628350, 3127680 (FEX), 4183110, 4427310 (Proton Experimental ARM64), and 993090 (Lossless Scaling, used by LSFG).

## Global Defaults

Default Proton is `DroidDeck-Proton-11-11.9`. `fexPreset`, `gameCpus` and the texture filtering keys are unset by default; an unset `fexPreset` means Performance + TSO.

## Alternative Without File Edits

`tools/droiddeckctl` in the DroidDeck repo talks to `content://com.droiddeck.launcher.agent` over adb. `env set` and `prefs set` only work after you turn on **Setup > Diagnostics > Debugging tools**, and its `env` scopes are session-wide (next session or persistent), not per game.

## How This Was Verified

- `dumpsys package` gave versionName 0.7.1; the source was checked out at tag `0.7.1` (versionCode 19 in `app/build.gradle`).
- Root reads covered every file listed above that existed on the test device. Live `guest_env` contents match what `GameEnvironmentStore.publish` produces with the default preset.
- The adapter was dry-run through `cocoonlib.apps.resolve_key` / `encode_value` / `appconf.json_write` against a seeded `game_env`. All six sample writes produced string values; `create=True` was needed (see Cocoon Tool Gap).
- `verified_on_device: true` means the key exists on the test device with the documented value. **No write was made and no game was launched**, so no setting's effect has been tested in a game.

## Open Questions for UI-Driven Tests

1. Set a per-game FEX preset and Wine sync in the UI for one game, then confirm `files/game-environment.json` matches the documented key sets.
2. Hand-edit `game_env` (app stopped), launch through Cocoon, and check the game's environment (`DXVK_HUD=fps` is visible proof) and the session log line `droiddeck-game-env: game cores ...`.
3. Hand-write `game_proton` and confirm Steam shows that compatibility tool for the game.
4. Confirm that a hand-made `frame_gen.xml` is honoured, or create it by picking Frame generation once.
5. Confirm the per-game component profile path works without `profiledComponents` being set.
