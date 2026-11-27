"""Find emulators and recomps without an adapter, and draft adapters for them.

coverage(): every installed app Cocoon launches games with (its `players`
table) or lists as a game in the Recomps folder or as an Android app, marked
covered / draft / missing. Apps not seen before are flagged NEW; the seen list
lives in apps/.coverage_seen.json.

discover(pkg): the mechanical half of writing an adapter. It finds the app's
config files on the device, reads every key with its current value and type,
looks for the app's source repository in the APK, and writes
local/apps/<name>.json (marked "draft") plus local/apps/<name>.md, a brief listing what an
agent still has to fill in from the app's source (labels, allowed values,
defaults, per-game rules, when the app reads and writes its files).
"""
import json
import re
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

from . import appconf, apps, db, device

SEEN = apps.ADAPTER_DIR.parent / "local" / "coverage_seen.json"
EMU_NAME = re.compile(r"emu|emulator|retroarch|sx2|sx3|rpcs|dolphin|citra|lime3ds|azahar|yuzu|eden|ryujinx|"
                      r"sudachi|citron|melon|drastic|ppsspp|duckstation|vita3k|cemu|xenia|xendroid|recomp|decomp|"
                      r"mupen|flycast|redream|winlator|gamehub|gamenative|mobox|droiddeck|pico8|scummvm|dosbox", re.I)
RECOMP_DIR = Path(__file__).resolve().parent.parent / "recomps"
NOISE = re.compile(r"(/log|logs?/|crash|cache|analytics|firebase|com\.google|webview|WebView|"
                   r"profileinstaller|/shaders?/|/Sys/|gamelist|metadata|achievement|cheats?/|"
                   r"\.lock$|downloads?/|telemetry|sentry|appcenter|bugsnag|datastore|"
                   r"WebViewChromiumPrefs|AwOriginVisitLoggerPrefs)", re.I)


# ------------------------------------------------------------------ coverage

def candidates():
    """{package: reason} for installed apps that run games."""
    installed = set(device.adb("shell", "pm list packages -3").decode().replace("package:", "").split())
    out = {}
    for line in device.query("SELECT DISTINCT intentPackage FROM players;").splitlines()[1:]:
        if line in installed:
            out[line] = "Cocoon player"
    rows = device.query("SELECT g.fileName, COALESCE(f.name, '') FROM games g "
                        "LEFT JOIN grid_placement p ON p.itemType='GAME' AND p.itemId=g.id AND p.screenType LIKE 'folder_%' "
                        "LEFT JOIN folders f ON f.id = CAST(substr(p.screenType, 8) AS INTEGER) "
                        "WHERE g.platformId='android_app';").splitlines()[1:]
    for line in rows:
        pkg, _, folder = line.partition("\t")
        if pkg in installed and folder.lower().startswith("recomp"):
            out.setdefault(pkg, "Recomps folder")
    for pkg in installed:
        if EMU_NAME.search(pkg):
            out.setdefault(pkg, "name looks like an emulator/port")
    for entry in RECOMP_DIR.glob("entries/*.json"):
        pkg = json.loads(entry.read_text()).get("package")
        if pkg in installed:
            out.setdefault(pkg, "recomp catalog")
    return out


def coverage():
    by_pkg = {}
    for a in apps.adapters().values():  # public adapters come first and win
        by_pkg.setdefault(a["package"], a)
    entries = [json.loads(p.read_text()) for p in RECOMP_DIR.glob("entries/*.json")]
    catalog = {e.get("package") for e in entries}
    # Catalogued apps whose entry says they have no editable settings file.
    no_settings = {e.get("package") for e in entries if not (e.get("settings") or {}).get("adapter")}
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    rows = []
    for pkg, why in sorted(candidates().items()):
        a = by_pkg.get(pkg)
        state = "draft" if a and a.get("draft") else ("covered" if a else
                 ("no-settings" if pkg in no_settings else "missing"))
        rows.append(dict(package=pkg, why=why, adapter=a["name"] if a else None, state=state,
                         catalog=pkg in catalog, new=pkg not in seen))
    return rows


def autodiscover(dry_run=False):
    """Draft adapters for apps never seen before that have none; return a report."""
    rows = coverage()
    report = []
    for r in rows:
        if not r["new"]:
            continue
        if r["state"] == "missing":
            if dry_run:
                report.append(f"would discover {r['package']} ({r['why']})")
                continue
            try:
                out, brief, adapter, _ = discover(r["package"])
                report.append(f"drafted {out.name} for {r['package']} ({len(adapter['keys'])} keys); brief {brief}")
            except SystemExit as e:
                report.append(f"{r['package']}: {e}")
        else:
            report.append(f"{r['package']}: already {r['state']} ({r['adapter']})")
    if not dry_run:
        mark_seen(r["package"] for r in rows)
    return report


def mark_seen(pkgs):
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(sorted(seen | set(pkgs)), indent=1) + "\n")


# ------------------------------------------------------------------ discover

def _type_of(fmt, raw):
    v = raw.strip()
    if fmt in ("json", "prefs"):
        try:
            x = json.loads(v)
        except json.JSONDecodeError:
            return "string"
        return {bool: "bool", int: "int", float: "float", str: "string"}.get(type(x), "string")
    low = v.strip('"').lower()
    if low in ("true", "false", "on", "off", "yes", "no"):
        return "bool"
    if re.fullmatch(r"-?\d+", v.strip('"')):
        return "int"
    if re.fullmatch(r"-?\d+\.\d+f?", v.strip('"')):
        return "float"
    return "string"


def _friendly(key):
    k = key.split("#")[-1].split("/")[-1]
    k = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", k).lower()
    return re.sub(r"[^a-z0-9]+", "_", k).strip("_")[:40] or "key"


def source_hints(pkg):
    """GitHub/GitLab URLs and an app label found in the APK."""
    path = device.adb("shell", f"pm path {shlex.quote(pkg)}").decode().split("\n")[0].replace("package:", "").strip()
    hints, label = [], None
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "base.apk"
        device.adb("pull", path, str(local))
        aapt = sorted(Path.home().glob("Library/Android/sdk/build-tools/*/aapt2"))
        if aapt:
            badging = subprocess.run([str(aapt[-1]), "dump", "badging", str(local)],
                                     capture_output=True, text=True).stdout
            m = re.search(r"application-label:'([^']*)'", badging)
            label = m[1] if m else None
        strings = subprocess.run(f"unzip -p {shlex.quote(str(local))} 'classes*.dex' 'assets/*' 'res/*' 2>/dev/null | "
                                 "LC_ALL=C strings -n 12", shell=True, capture_output=True, text=True).stdout
        for url in re.findall(r"https?://(?:github\.com|gitlab\.com|codeberg\.org|git\.[a-z0-9.-]+)/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", strings):
            url = url.rstrip(".")
            if url not in hints and not re.search(r"/(square|google|JetBrains|Kotlin|ReactiveX|airbnb|facebook|bumptech|"
                                                  r"material-components|androidx|grpc|protocolbuffers|apache)/", url):
                hints.append(url)
    return label, hints[:15]


def discover(pkg, name=None, max_keys=400):
    if name is not None and not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        raise SystemExit(f"adapter name {name!r}: use lowercase letters, digits, - and _ only")
    version = apps.installed_version(pkg)
    if version is None:
        raise SystemExit(f"{pkg} is not installed")
    probe = {"name": pkg, "package": pkg, "files": {}, "keys": {}}
    hashes = apps.snapshot_hashes(probe)
    files = {p: t for p, t in apps.read_many(sorted(hashes)).items()}
    found, skipped = [], []
    for path, text in sorted(files.items()):
        fmt = appconf.guess_format(path)
        if not fmt or NOISE.search(path):
            skipped.append(path)
            continue
        try:
            values = appconf.read(fmt, text)
        except Exception as e:  # unknown dialect: list it for the researcher, don't guess
            skipped.append(f"{path} (did not parse as {fmt}: {e})")
            continue
        if fmt == "json" and len(values) > 2000:
            skipped.append(f"{path} ({len(values)} values: data, not settings)")
            continue
        if values:
            found.append((path, fmt, values))
    label, hints = source_hints(pkg)
    if name is None:
        name = re.sub(r"[^a-z0-9]+", "-", (label or pkg.split(".")[-1]).lower()).strip("-")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise SystemExit(f"cannot make an adapter name from {label or pkg!r}; pass --name")
    adapter = {"name": name, "package": pkg, "aliases": [], "category": "emulator",
               "draft": True, "version_checked": version, "stop_before_write": True,
               "discovered": time.strftime("%Y-%m-%d"), "source_hints": hints,
               "files": {}, "per_game": None, "keys": {}}
    used = set()
    for i, (path, fmt, values) in enumerate(sorted(found, key=lambda f: -len(f[2]))):
        fid = re.sub(r"[^a-z0-9]+", "_", Path(path).stem.lower()).strip("_") or f"file{i}"
        while fid in adapter["files"]:
            fid += "_"
        adapter["files"][fid] = {"path": path, "format": fmt, "notes": f"{len(values)} keys found by discover"}
        for key, raw in values.items():
            if len(adapter["keys"]) >= max_keys:
                break
            if "#" in key and fmt == "prefs":
                pass
            elif fmt == "prefs" and raw.startswith('"{'):
                continue  # the JSON pref itself; its fields are listed with #
            friendly = _friendly(key)
            while friendly in used:
                friendly += "_"
            used.add(friendly)
            adapter["keys"][friendly] = {"file": fid, "key": key, "label": None, "type": _type_of(fmt, raw),
                                         "values": None, "default": None, "current": raw,
                                         "per_game": False, "verified_on_device": True,
                                         "notes": "auto-discovered; meaning not researched"}
    if (apps.ADAPTER_DIR / f"{name}.json").exists():
        raise SystemExit(f"{apps.ADAPTER_DIR / f'{name}.json'} already exists; not overwriting")
    apps.DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    out = apps.DRAFT_DIR / f"{name}.json"
    out.write_text(json.dumps(adapter, indent=1) + "\n")
    brief = apps.DRAFT_DIR / f"{name}.md"
    brief.write_text(_brief(adapter, label, skipped))
    return out, brief, adapter, skipped


def _brief(a, label, skipped):
    files = "\n".join(f"- `{f['path']}` ({f['format']}, {f['notes']})" for f in a["files"].values()) or "- none found"
    hints = "\n".join(f"- {h}" for h in a["source_hints"]) or "- none found in the APK"
    skip = "\n".join(f"- `{s}`" for s in skipped[:40]) or "- none"
    return f"""# {label or a['name']} ({a['package']}) - DRAFT

Drafted by `thorctl app discover` on {a['discovered']} from version {a['version_checked']}. Every key below
is real and its current value is recorded, but nothing about meaning is known yet. Until the
research below is done, `thorctl app set` works with raw values only.

## Config Files Found

{files}

## Skipped (logs, caches, data, unparsed)

{skip}

## Source Hints From the APK

{hints}

## Research To Finish This Adapter

Read `apps/SCHEMA.md`, then use the app's source (hints above, or web search; for closed source,
`jadx --no-res` on the APK) and the device (read-only) to:

1. Replace `label` (the app's UI wording), `values` (every allowed raw value and its meaning),
   `default` and `per_game` for the 20-40 settings people tune; delete keys that are internal state.
   Rename friendly names where useful.
2. Decide `stop_before_write` and note when the app reads its files (start-up, game launch).
3. Fill `per_game` (path pattern, id format, whether files can be created) if the app has per-game settings.
4. Add `aliases`, fix `category` (emulator / recomp / tool), remove `"draft": true` and the `current` fields,
   then move the adapter to `apps/{a['name']}.json` and the generic findings to `apps/{a['name']}.md`.
5. Test one write through the app's own UI with `thorctl ui` (or `thorctl app watch {a['name']}` while
   changing an option by hand), then record what was verified here.
6. Keep `apps/` free of anything personal (games, accounts, SD-card volume ids, install dates,
   chosen values): those stay in `local/apps/{a['name']}.md`, which git ignores.
"""
