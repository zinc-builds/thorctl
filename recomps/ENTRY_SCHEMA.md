# Recomp Catalog Entry (recomps/entries/<package>.json)

One file per recomp, decompilation, source port or fan remake. `thorctl recomps build` merges them into `recomps/catalog.json` and `recomps/CATALOG.md`.

## Public Entry

`recomps/entries/<package>.json` is committed. It holds what is true of the app on any Thor: where it reads files, what its settings do, which version was checked.

```json
{
 "package": "com.example.port",
 "name": "Display name as in Cocoon",
 "original": {"title": "Banjo-Kazooie", "platform": "N64", "year": 1998},
 "kind": "static recompilation | decompilation | source port | fan remake | engine reimplementation | wrapper",
 "project": {"name": "e.g. BanjoRecomp", "repo": "https://...", "android_repo": "https://... or null", "license": "..."},
 "version_checked": "<versionName the notes below were checked against>",
 "update": {"channel": "GitHub releases | Obtainium | Play | itch | manual APK", "url": "https://..."},
 "assets": {"needs": "what the user must supply (ROM, ISO, game data, BIOS) and in what form",
            "location": "where the app reads it (app paths, not your own ROM folders)", "notes": "..."},
 "settings": {"adapter": "<apps/<name>.json name or null>", "files": ["device paths"], "in_app_menu": "how to open settings in the app",
              "summary": "the settings worth knowing (graphics, framerate, enhancements)"},
 "controls": "built-in controller support, remapping, touch overlay notes",
 "display": "single screen / uses the bottom screen / resolution behaviour on the Thor",
 "saves": "where saves live (path) so they can be backed up",
 "notes": "anything else worth knowing (known issues on Adreno 740, required driver, etc.)",
 "verified": "what was checked on a device vs taken from the web"
}
```

Unknown fields: use null and say so in `verified`. Never invent a repo URL: if the source can't be identified, say what was tried.

Keep these out of the public entry: your own ROM and disc file names and paths (`/storage/<sd-card>/Roms/...`), the SD-card volume id, what you have imported, played or opened and when, your settings values ("on this device"), install dates, play counts, account names and tokens.

## Local Overlay

`local/recomps/<same file name>.json` is not committed. `cocoonlib/recomps.py` merges it over the public entry key by key: nested objects merge, any other value replaces the public one. It holds what is true of one device:

```json
{
 "cocoon_game_id": 123,
 "version_installed": "<versionName>", "version_code": 0, "installed": "YYYY-MM-DD (firstInstallTime)",
 "update": {"obtainium_tracked": true},
 "assets": {"present": true, "notes": "full text, including your ROM path and import date"},
 "notes": "full text, including what you saw on your device"
}
```

A free-text field in the overlay replaces the public text, so write the complete text there, not only the device-specific part.

`thorctl recomps build` writes the public catalog to `recomps/` from the public entries only, and, when any overlay exists, the merged catalog to `local/recomps/` (title "Recomps on This Thor").
