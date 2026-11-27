"""The recomp catalog: recomps/entries/<package>.json -> catalog.json + CATALOG.md.

Entries hold what is true of the app anywhere. What is true of one device
(installed version, Cocoon game id, whether the game files are there) goes in
local/recomps/<package>.json, which is not committed; it is merged over the
entry key by key. build() writes the shared catalog to recomps/ and, when any
local file exists, the merged one to local/recomps/.
"""
import json
import time
from pathlib import Path

from . import apps

ROOT = Path(__file__).resolve().parent.parent / "recomps"
LOCAL = Path(__file__).resolve().parent.parent / "local" / "recomps"


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def entries(local=True):
    out = []
    for p in sorted((ROOT / "entries").glob("*.json")):
        e = json.loads(p.read_text())
        lp = LOCAL / p.name
        if local and lp.exists():
            _merge(e, json.loads(lp.read_text()))
        e["_file"] = p.name
        out.append(e)
    return sorted(out, key=lambda e: (e.get("original") or {}).get("platform") or "", )


def _g(d, *path, default=None):
    for k in path:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return d if d not in (None, "") else default


def build():
    n = _write(entries(local=False), ROOT, "Recomps for the AYN Thor", apps.adapters(drafts=False))
    if has_local():
        _write(entries(), LOCAL, "Recomps on This Thor", apps.adapters())
    return n


def has_local():
    return any((LOCAL / p.name).exists() for p in (ROOT / "entries").glob("*.json"))


def _write(es, out, title, known):
    adapters = {a["package"]: a["name"] for a in reversed(list(known.values()))}  # public first wins
    for e in es:
        if not isinstance(e.get("settings"), dict):
            e["settings"] = {}
        if not _g(e, "settings", "adapter") and e["package"] in adapters:
            e["settings"]["adapter"] = adapters[e["package"]]
    clean = [{k: v for k, v in e.items() if k != "_file"} for e in es]
    (out / "catalog.json").write_text(json.dumps({"built": time.strftime("%Y-%m-%d"), "recomps": clean}, indent=1) + "\n")
    lines = [f"# {title}", "",
             f"Built {time.strftime('%Y-%m-%d')} by `thorctl recomps build` from `recomps/entries/*.json` "
             f"({len(es)} apps). Settings: `thorctl app get <adapter>`.", "",
             "| Game | Original | Kind | Project | Version | Updates | Assets | Settings |",
             "|---|---|---|---|---|---|---|---|"]
    for e in sorted(es, key=lambda e: e.get("name") or e["package"]):
        orig = _g(e, "original", default={})
        o = f"{orig.get('title') or '?'} ({orig.get('platform') or '?'}{', ' + str(orig['year']) if orig.get('year') else ''})"
        repo = _g(e, "project", "android_repo") or _g(e, "project", "repo")
        proj = f"[{_g(e, 'project', 'name', default='source')}]({repo})" if repo else (_g(e, "project", "name") or "unknown")
        upd = _g(e, "update", "channel", default="?")
        if _g(e, "update", "obtainium_tracked"):
            upd += " (Obtainium)"
        assets = _g(e, "assets", "needs", default="?")
        if _g(e, "assets", "present") is True:
            assets += " ✓"
        elif _g(e, "assets", "present") is False:
            assets += " (missing)"
        adapter = _g(e, "settings", "adapter")
        sett = f"`{adapter}`" if adapter else "none"
        cells = [e.get("name") or e["package"], o, e.get("kind") or "?", proj,
                 str(e.get("version_installed") or e.get("version_checked") or "?"), upd, assets, sett]
        lines.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in cells) + " |")
    lines += ["", "## Details", ""]
    for e in sorted(es, key=lambda e: e.get("name") or e["package"]):
        lines += [f"### {e.get('name') or e['package']}", "", f"`{e['package']}`" +
                  (f", Cocoon game {e['cocoon_game_id']}" if e.get("cocoon_game_id") else ""), ""]
        for label, val in (("Assets", _g(e, "assets", "notes") or _g(e, "assets", "location")),
                           ("Settings", _g(e, "settings", "summary")),
                           ("Controls", e.get("controls")), ("Display", e.get("display")),
                           ("Saves", e.get("saves")), ("Notes", e.get("notes"))):
            if val:
                lines.append(f"- {label}: {val}")
        lines.append("")
    (out / "CATALOG.md").write_text("\n".join(lines) + "\n")
    return len(es)


def find(text):
    t = text.lower()
    return [e for e in entries() if t in json.dumps(e).lower()]
