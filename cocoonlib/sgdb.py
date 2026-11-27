"""Minimal SteamGridDB v2 client, using the API key stored in Cocoon's prefs."""
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import quote

API = "https://www.steamgriddb.com/api/v2"
_ENDPOINTS = {"boxArt": "grids", "logo": "logos", "hero": "heroes"}
# Cocoon's icons are square grids; it takes the first-ranked asset.
_QUERY = {"boxArt": "dimensions=1024x1024&types=static", "logo": "types=static",
          "hero": "types=static"}
# Cloudflare in front of SteamGridDB rejects urllib's default user agent.
_UA = {"User-Agent": "cocoonctl/1.0"}
_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def key_from_prefs(ui_prefs_xml):
    m = re.search(r'name="steamgriddb_api_key">([^<]+)<', ui_prefs_xml)
    if not m:
        raise RuntimeError("no steamgriddb_api_key in Cocoon's ui_prefs.xml")
    return m.group(1)


class Client:
    def __init__(self, key):
        self._key = key

    def _get(self, path):
        req = urllib.request.Request(f"{API}/{path}",
                                     headers={**_UA, "Authorization": f"Bearer {self._key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
        if not body.get("success"):
            raise RuntimeError(f"SteamGridDB {path}: {body}")
        return body["data"]

    def search(self, term):
        return self._get(f"search/autocomplete/{quote(term)}")

    def game_by_steam_appid(self, appid):
        return self._get(f"games/steam/{int(appid)}")

    def assets(self, kind, sgdb_game_id):
        return self._get(f"{_ENDPOINTS[kind]}/game/{sgdb_game_id}?{_QUERY[kind]}")

    def asset_by_id(self, kind, sgdb_game_id, asset_id):
        """A specific asset of any size, e.g. a 512x512 grid when no 1024 one exists."""
        path = f"{_ENDPOINTS[kind]}/game/{sgdb_game_id}"
        for item in self._get(path):
            if item["id"] == asset_id:
                return item
        raise RuntimeError(f"SteamGridDB game {sgdb_game_id} has no {kind} asset {asset_id}")

    def first_asset(self, kind, sgdb_game_id):
        items = self.assets(kind, sgdb_game_id)
        if not items:
            raise RuntimeError(f"SteamGridDB game {sgdb_game_id} has no {kind}")
        return items[0]


def download(asset, dest_dir: Path):
    ext = _EXT[asset["mime"]]
    out = dest_dir / f"sgdb_{asset['id']}.{ext}"
    req = urllib.request.Request(asset["url"], headers=_UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        out.write_bytes(r.read())
    return out, ext
