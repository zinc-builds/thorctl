# Super Mario World Remastered+ (com.example.supermarioworldremasteredplus)

Adapter: `apps/smwr.json` (34 keys). Checked 2026-11-27 against the v1.1 release APK on an AYN Thor and the source of [BTFighter/Super-Mario-World-Remastered-Plus](https://github.com/BTFighter/Super-Mario-World-Remastered-Plus) (fork of Boswer811's Remastered Plus, originally JHDev2006's Super Mario World Remastered).

## Checked Build

- versionName `1.0.0`, versionCode 1. Godot 4.4.stable.official.
- APK SHA-256 `28bff031…bb3` equals the v1.1 release asset `SuperMarioWorldRemasteredPlus.apk` (the touch-UI build; the release also has a No Touch UI APK). The Android build was added to the v1.1 release on 2026-03-22.
- The app was not launched during the check, so every key is `verified_on_device: false`.

## Files

| Path | What it holds |
|---|---|
| `/data/data/com.example.supermarioworldremasteredplus/files/settings.cfg` | All options, as JSON (tab-indented) despite the name. |
| `…/files/Saves/*.sav` | Save slots (JSON). |
| `/storage/emulated/0/Documents/baserom.sfc` | Required ROM (checked by SHA-256). Fallback `…/files/baserom.sfc`. |

Godot's `user://` on Android is `getFilesDir()`; the project's `custom_user_dir_name` is ignored there (Godot 4.4 `OS_Android::get_user_data_dir` / `GodotIO.getDataDir`).

## Write Rules (`json`)

Source: `Scripts/Autoload/SettingsManager.gd` (matches the decompiled bytecode in the installed APK, including `modified_life_decrement`).

- On start: if the file is missing, the template is written; then the file is parsed, missing keys are filled from the template, and the file is saved again (`verify_settings`). The options menu saves on change. Stop the app before editing.
- Godot's JSON parser turns every number into a float, so after the first rewrite integers appear as `0.0`, `2.0`. Both forms work: `window_type` goes through `int()`, other enums compare equal.
- `resolution` is stored as a string such as `"(1440, 810)"`; the loader strips brackets and spaces and splits on the comma.
- Template `{}` lets `thorctl` create the file before first launch; the game would fill in the rest. This is from reading the code, not tested. Launching once first is cleaner (it also creates `files/` with the app's ownership).

## Worth Setting on the Thor

`window_type = 2` (Fullscreen). Windowed is the default and leaves Android's status and navigation bars over the game (BTFighter release notes).

## Not Verified

Nothing was run: no settings file was available to check. `hud_dragon_coin_style` and `soundtrack_type` are in the template but not in the option scenes checked; their values were not traced. `sprite_settings` (per-sprite style dictionary) is left out.
