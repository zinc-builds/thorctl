# Adapter Schema (apps/<name>.json)

Read by `thorctl app` (cocoonlib/apps.py). Real examples: eden.json, dolphin.json, armsx2.json, droiddeck.json. Command reference: tools/cocoon/README.md "App Settings".

```json
{
 "name": "short-name", "package": "com.example.app", "aliases": ["..."],
 "category": "emulator | recomp | tool",
 "version_checked": "<versionName from dumpsys package>",
 "stop_before_write": true,
 "files": {"<fileId>": {"path": "<absolute device path>", "format": "ini|qtini|qtini-game|cfg|yaml|prefs|json|toml|other",
            "notes": "...", "template": "<optional initial content when the file may not exist yet>",
            "string_values": false}},
 "per_game": {"path": "<path with {game}>", "format": "...", "game_id": "how to get the id", "create": true,
              "key_map": {"from": "<global key prefix>", "to": "<per-game key prefix with {game}>"},
              "notes": "..."},
 "keys": {"<friendly_name>": {"file": "<fileId>", "key": "<Section/key for ini-like; plain key for cfg/prefs; slash path for yaml/json/toml; JSON stored inside a pref uses pref#json/path>",
          "label": "<UI label in the app>", "type": "enum|int|float|bool|string",
          "values": {"<raw value exactly as stored>": "<meaning>"}, "default": "<raw>",
          "per_game": false, "verified_on_device": true, "notes": "..."}}
}
```

- `per_game.section_map` (`{fileId: {section: per-game section}}`) renames ini sections when a global key is written per game (Dolphin: GFX.ini `[Settings]` -> `[Video_Settings]`).
- Per-game extras (all optional):
  - `keys.<name>.per_game_key`: the key's name in the per-game file when it differs (Vita3K yaml `resolution-multiplier` -> XML `config/gpu@resolution-multiplier`; `{game}` allowed).
  - `keys.<name>.per_game_values`: global raw value -> per-game raw value (WatermelonDS `"vulkan"` -> `"VULKAN"`).
  - `per_game.template`: content for a new per-game file; `{name}` / `{name:type}` placeholders are filled from the app's current global values.
  - `per_game.seed_from`: path (with `{game}`, matched case-insensitively) copied into a new per-game file first (Cemu's shipped profile).
  - `per_game.mirror`: `{"path", "from", "to"}` - a second file kept in step (WatermelonDS `rom_metadata_mirror.json`).
  - `extends`: `{"name", "extends": "<base>", "package"}` reuses a whole adapter for another package (Eden Nightly).
- `per_game` may be null. `key_map` is only for apps that keep per-game settings in the same file under a different key (ARMSX2).
- Formats: `kv` = sectionless `key = value` lines; `spaced` = `key value // comment` (PICO-8); `xml` = element paths from the root, `@attr` for attributes (Cemu settings.xml); json paths may select list items with `[field=value]` (WatermelonDS `[fileName={game}]/config/videoRenderer`); `ini` = `Key = Value` under `[Sections]` (BOM and CRLF kept); `qtini` = Qt INI with `key\default` flags (yuzu/Eden/Citra family, global); `qtini-game` = per-game Qt INI with `key\use_global`; `cfg` = RetroArch-style `key = "value"`; `prefs` = Android SharedPreferences XML; `yaml`, `json`, `toml`. For anything else (custom text, binary) use `other` and describe it exactly in notes; the parent adds support.
- Raw values are strings exactly as stored (JSON-encoded scalars for json/prefs, e.g. `true`, `3`, `"vulkan"`).
- `stop_before_write`: true when the app keeps settings in memory and rewrites the file (most apps). Say in notes when the app reads the file (start-up, game launch).
