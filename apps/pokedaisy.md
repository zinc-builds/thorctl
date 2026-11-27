# PokeDaisy (com.pokedaisy.app)

Adapter: [pokedaisy.json](pokedaisy.json) (24 keys). Checked 2026-11-27 against **1.6.1** (versionCode 22). A Game Boy / GBC / GBA / DS player for Pokemon games and ROM hacks with a live companion screen. Site: <https://pokedaisy.com/> (latest listed 1.6.2.2). Source repo not identified (see the catalog entry).

## File

`/data/data/com.pokedaisy.app/shared_prefs/pokedaisy.xml` (SharedPreferences `pokedaisy`, `Prefs.java`). Enum settings are stored as the enum's name (`game_aspect = WIDE`); feature toggles use the names in `companion/NewFeatures.java`. The adapter covers display, DS, speed and the main gameplay helpers; `thorctl app get pokedaisy --all` shows the rest.

## Secrets

Once signed in, the file holds `ra_token`, `ra_web_api_key`, `ss_user`/`ss_password` and `steamgriddb_api_key`. Never print or copy them.

## Write Rules

Stop the app first: SharedPreferences are kept in memory and rewritten on any change.
