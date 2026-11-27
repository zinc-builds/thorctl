"""Settings for any Android app: adapters (apps/*.json), safe writes, watch.

An adapter names an app's config files, their formats, its per-game file
pattern and a glossary of friendly setting names. Apps without an adapter
still work through explicit `/device/path:key` names and `watch`.

Writes: the app must not be running (most emulators rewrite their config
from memory when they exit, undoing the edit). With --stop the app is
force-stopped first, which ends any game in progress. Each file is checked
against the checksum it was read with, written in place (owner and SELinux
label kept), and read back.
"""
import difflib
import fnmatch
import hashlib
import json
import re
import shlex
import time
from pathlib import Path

from . import appconf, device

ADAPTER_DIR = Path(__file__).resolve().parent.parent / "apps"
# Drafts from `app discover` hold this device's raw values, so they stay in the
# git-ignored local/apps/ until researched and moved to apps/.
DRAFT_DIR = Path(__file__).resolve().parent.parent / "local" / "apps"
BACKUPS = Path(__file__).resolve().parent.parent / "snapshots" / "apps"
STAGE = "/data/local/tmp/thorctl-app"
TEXT_EXT = ("*.ini", "*.cfg", "*.opt", "*.xml", "*.json", "*.yml", "*.yaml", "*.toml", "*.txt", "*.conf")
SKIP_DIRS = ("cache", "code_cache", "app_webview", "app_textures", "linuxfs", "shader", "shaders",
             "Cache", "ShaderCache", "lib", "oat")


# ------------------------------------------------------------------ adapters

def adapters(drafts=True):
    raw = {}
    for p in [*sorted(ADAPTER_DIR.glob("*.json")), *(sorted(DRAFT_DIR.glob("*.json")) if drafts else [])]:
        if p.name.startswith("."):
            continue
        a = json.loads(p.read_text())
        raw.setdefault(a["name"], a)  # a public adapter wins over a leftover draft
    out = {}
    for name, a in raw.items():
        out[name] = _inherit(a, raw) if "extends" in a else a
    return out


def _inherit(a, raw):
    """{"extends": "eden", "package": "...nightly"}: the base adapter with the
    base package name replaced by this one in every file path."""
    base = raw.get(a["extends"])
    if base is None:
        raise SystemExit(f"adapter {a['name']} extends unknown adapter {a['extends']!r}")
    text = json.dumps(base).replace(base["package"], a["package"])
    merged = json.loads(text)
    merged.update({k: v for k, v in a.items() if k != "extends"})
    merged["extends"] = a["extends"]
    return merged


def resolve(name):
    """An adapter by name, alias or package; or a bare adapter for any package."""
    for a in adapters().values():
        if name.lower() in [a["name"], a["package"], *map(str.lower, a.get("aliases", []))]:
            return a
    if "." in name:
        return {"name": name, "package": name, "aliases": [], "files": {}, "keys": {},
                "per_game": None, "stop_before_write": True, "bare": True}
    known = ", ".join(sorted(adapters()))
    raise SystemExit(f"no adapter called {name!r} (known: {known}); a package name also works")


def installed_version(pkg):
    out = device.adb("shell", f"dumpsys package {shlex.quote(pkg)} | grep -m1 versionName").decode()
    return out.split("=", 1)[1].strip() if "=" in out else None


# ------------------------------------------------------------------ device files

def read_file(path):
    """Text of a device file, or None when it does not exist."""
    q = shlex.quote(path)
    out = device.root(f"if [ -f {q} ]; then echo EXISTS; cat {q}; else echo MISSING; fi")
    head, _, body = out.partition("\n")
    return body if head == "EXISTS" else None


def running(pkg):
    out = device.adb("shell", "ps -A -o NAME").decode().split()
    return sorted({n for n in out if n == pkg or n.startswith(pkg + ":")})


def ensure_stopped(pkg, stop):
    procs = running(pkg)
    if not procs:
        return
    if not stop:
        raise SystemExit(f"{pkg} is running ({', '.join(procs)}). It may rewrite its config when it "
                         "exits, undoing this edit. Close it, or pass --stop to force-stop it "
                         "(this ends any game in progress).")
    device.adb("shell", f"am force-stop {shlex.quote(pkg)}")
    time.sleep(0.5)
    if running(pkg):
        raise SystemExit(f"{pkg} is still running after force-stop")


def write_files(pkg, new_texts, originals):
    """new_texts/originals: {device path: text}; originals[path] None = new file."""
    device.adb("shell", f"rm -rf {STAGE} && mkdir -p {STAGE}")
    lines = ["set -e", 'fail() { echo "$1" >&2; exit 3; }']
    for i, (path, text) in enumerate(new_texts.items()):
        device.adb("shell", f"cat > {STAGE}/{i}", input_bytes=text.encode())
        q = shlex.quote(path)
        old = originals.get(path)
        want = hashlib.md5(old.encode()).hexdigest() if old is not None else "absent"
        lines.append(f'cur=$([ -f {q} ] && md5sum {q} | cut -d" " -f1 || echo absent)')
        lines.append(f'[ "$cur" = "{want}" ] || fail "{path} changed since it was read; nothing written"')
    for i, path in enumerate(new_texts):
        q = shlex.quote(path)
        parent = shlex.quote(str(Path(path).parent))
        if path.endswith(".xml") and "/shared_prefs/" in path:
            # SharedPreferences restores a leftover .bak over the file on next load.
            lines.append(f"rm -f {shlex.quote(path + '.bak')}")
        if originals.get(path) is not None:
            lines.append(f"cat {STAGE}/{i} > {q}")
        elif path.startswith("/data/data/") or path.startswith("/data/user/"):
            lines.append(f"mkdir -p {parent}; cp {STAGE}/{i} {q}; chown $(stat -c %u:%g {parent}) {q}; "
                         f"chmod 660 {q}; chcon $(stat -c %C {parent}) {q}")
        else:
            lines.append(f"mkdir -p {parent}; cp {STAGE}/{i} {q}")
    device.adb("shell", f"cat > {STAGE}/apply.sh", input_bytes=("\n".join(lines) + "\n").encode())
    device.root(f"sh {STAGE}/apply.sh")
    device.adb("shell", f"rm -rf {STAGE}")


def backup(app, originals):
    dest = BACKUPS / f"{app['name']}-{time.strftime('%Y%m%d-%H%M%S')}"
    dest.mkdir(parents=True, exist_ok=True)
    for path, text in originals.items():
        if text is not None:
            (dest / path.strip("/").replace("/", "__")).write_text(text)
    (dest / "paths.json").write_text(json.dumps(sorted(originals), indent=1))
    return dest


def restore(app, folder, stop):
    """Put back every file saved in a backup folder made by a write."""
    folder = Path(folder)
    paths = json.loads((folder / "paths.json").read_text())
    texts, originals = {}, {}
    for path in paths:
        saved = folder / path.strip("/").replace("/", "__")
        if not saved.exists():
            continue  # the write created this file; leave it
        texts[path] = saved.read_text()
        originals[path] = read_file(path)
    if app.get("stop_before_write", True):
        ensure_stopped(app["package"], stop)
    backup(app, originals)
    write_files(app["package"], texts, originals)
    bad = [p for p, t in texts.items() if read_file(p) != t]
    if bad:
        raise SystemExit("restore did not stick for: " + ", ".join(bad))
    return sorted(texts)


# ------------------------------------------------------------------ keys

def expand(path):
    """Fill {sdcard} (the SD card's volume id) in an adapter path; asks the device only when needed."""
    return path.replace("{sdcard}", device.sdcard()) if "{sdcard}" in path else path


def file_spec(app, file_id, game=None):
    if file_id == "game":
        pg = app.get("per_game")
        if not pg:
            raise SystemExit(f"{app['name']} has no per-game settings in its adapter")
        if not game:
            raise SystemExit("per-game key: pass --game ID")
        return {"path": expand(pg["path"].replace("{game}", game)), "format": pg["format"], "create": pg.get("create", False)}
    if file_id.startswith("/"):
        fmt = appconf.guess_format(file_id)
        if not fmt:
            raise SystemExit(f"cannot tell the format of {file_id}")
        return {"path": file_id, "format": fmt, "create": False}
    if file_id not in app["files"]:
        raise SystemExit(f"{app['name']} has no file {file_id!r} (files: {', '.join(app['files'])})")
    spec = dict(app["files"][file_id])
    if game and "{game}" in spec["path"]:
        pg = app.get("per_game") or {}
        if spec["path"] == pg.get("path"):
            spec.setdefault("create", pg.get("create", False))
        spec["path"] = spec["path"].replace("{game}", game)
    spec["path"] = expand(spec["path"])
    return spec


def resolve_key(app, name, game=None):
    """Friendly name or FILE:path -> (spec, path, glossary entry or None).

    With --game, a glossary key that supports per-game goes to the per-game file."""
    entry = app["keys"].get(name)
    if entry:
        key = entry["key"].replace("{game}", game or "{game}")
        if game and entry.get("per_game_key"):
            # Per-game file names the setting differently (Vita3K: yaml key -> XML attribute).
            return file_spec(app, "game", game), entry["per_game_key"].replace("{game}", game), entry
        if "{game}" in key:
            raise SystemExit(f"{name} is per-game: pass --game ID")
        pg = app.get("per_game")
        if game and not entry.get("per_game"):
            raise SystemExit(f"{name} cannot be set per game in {app['name']}")
        if game and pg and "{game}" not in entry["key"] and "{game}" not in app["files"][entry["file"]]["path"]:
            km = pg.get("key_map")
            if km:
                # Same file, different key (e.g. ARMSX2: config.global#X -> config.game.<serial>#X).
                if not key.startswith(km["from"]):
                    raise SystemExit(f"{name}: key {key} does not start with {km['from']}")
                key = km["to"].replace("{game}", game) + key[len(km["from"]):]
                return file_spec(app, entry["file"]), key, entry
            smap = pg.get("section_map", {}).get(entry["file"], {})
            if smap and "/" in key:
                section, rest = key.split("/", 1)
                key = f"{smap.get(section, section)}/{rest}"
            return file_spec(app, "game", game), key, entry
        return file_spec(app, entry["file"], game), key, entry
    if ":" in name:
        file_id, _, key = name.rpartition(":") if name.startswith("/") else name.partition(":")
        return file_spec(app, file_id, game), key, None
    close = [k for k in app["keys"] if name.lower() in k.lower() or name.lower() in (app["keys"][k].get("label") or "").lower()]
    raise SystemExit(f"{app['name']} has no setting {name!r}" + (f"; did you mean: {', '.join(close[:8])}" if close else
                     "; use FILE:Section/key, `app keys NAME`, or `app watch NAME`"))


def encode_value(entry, raw):
    """Accept a raw value or a value's meaning (e.g. 'Vulkan' for '1')."""
    if not entry or not entry.get("values"):
        return raw
    values = entry["values"]
    if raw in values:
        return raw
    if json.dumps(raw) in values:  # values stored as JSON strings: accept 1 for "1"
        return json.dumps(raw)
    for k, meaning in values.items():
        if str(meaning).lower() == raw.lower() or str(meaning).lower().startswith(raw.lower() + " "):
            return k
    if entry.get("type") == "enum":
        opts = ", ".join(f"{k}={v}" for k, v in values.items())
        raise SystemExit(f"{raw!r} is not a valid value; options: {opts}")
    return raw


def describe(entry, raw):
    if raw is None:
        if entry and entry.get("default") not in (None, ""):
            d = str(entry["default"])
            meaning = (entry.get("values") or {}).get(d)
            return f"default: {d}" + (f" ({meaning})" if meaning else "") + " (not in file)"
        return "(unset)"
    if raw.endswith("  (default)") and entry and entry.get("default") not in (None, ""):
        d = str(entry["default"])
        meaning = (entry.get("values") or {}).get(d)
        return f"default: {d}" + (f" ({meaning})" if meaning else "")
    if entry and entry.get("values"):
        base = raw.split("  (")[0]
        meaning = entry["values"].get(base)
        if meaning is not None:
            return f"{raw} ({meaning})" if "(" not in raw else f"{raw}  [{meaning}]"
    return raw


# ------------------------------------------------------------------ operations

def new_file_text(app, spec, game):
    """Starting content for a per-game file that does not exist yet.

    seed_from: copy another file (Cemu: the shipped default profile; a user
    profile replaces it entirely). template: {name} placeholders are filled
    with the app's current global values (Vita3K: a per-game XML must list
    every attribute)."""
    pg = app.get("per_game") or {}
    is_game_file = game and spec["path"] == expand((pg.get("path") or "").replace("{game}", game))
    if is_game_file and pg.get("seed_from"):
        seed_path = expand(pg["seed_from"].replace("{game}", game))
        folder, name = str(Path(seed_path).parent), Path(seed_path).name
        listing = device.root(f"ls {shlex.quote(folder)} 2>/dev/null; true").split()
        match = [f for f in listing if f.lower() == name.lower()]
        return (read_file(f"{folder}/{match[0]}") or "") if match else ""
    template = (pg.get("template") if is_game_file else spec.get("template")) or ""
    # {name} or {name:type}; the value comes from the app's global files.
    names = set(re.findall(r"\{([A-Za-z0-9_.-]+)(?::[a-z]+)?\}", template)) - {"game"}
    if names:
        values = {}
        for fid, f in app["files"].items():
            if "{" in f["path"].replace("{sdcard}", ""):
                continue
            text = read_file(expand(f["path"]))
            if text:
                for k, v in appconf.read(f["format"], text).items():
                    values.setdefault(k.split("/")[-1], v)
        missing = sorted(n for n in names if n not in values)
        if missing:
            raise SystemExit(f"cannot build the per-game file: no global value for {', '.join(missing)}")
        for n in names:
            template = re.sub(r"\{" + re.escape(n) + r"(?::[a-z]+)?\}", values[n].strip('"'), template)
    return template


def plan_set(app, assignments, unsets, game):
    texts, originals, changes = {}, {}, []
    for spec_text in assignments + [(u, None) for u in unsets]:
        name, raw = spec_text
        spec, key, entry = resolve_key(app, name, game)
        path = spec["path"]
        if path not in texts:
            cur = read_file(path)
            if cur is None and not (spec.get("create") or spec.get("template")):
                raise SystemExit(f"{path} does not exist on the device"
                                 + (" (the app creates it when you open per-game settings once)" if game else ""))
            originals[path] = cur
            texts[path] = cur if cur is not None else new_file_text(app, spec, game)
        before = appconf.lookup(spec["format"], texts[path], key)
        if raw is None:
            texts[path] = appconf.unset(spec["format"], texts[path], key)
            if spec["format"] == "qtini" and entry and entry.get("default") not in (None, ""):
                # Keep the stored line equal to the default so reads are not misleading.
                texts[path] = appconf.ini_write(texts[path], key, str(entry["default"]), sep_default="=")
        else:
            value = encode_value(entry, raw)
            if game and entry and entry.get("per_game_values"):
                # Per-game store spells values differently (WatermelonDS: "vulkan" -> "VULKAN").
                if value not in entry["per_game_values"]:
                    raise SystemExit(f"{name}: no per-game form of {value}")
                value = entry["per_game_values"][value]
                mapped = True
            else:
                mapped = False
            if entry and spec["format"] in ("ini", "qtini", "qtini-game", "toml", "cfg") \
                    and app["files"].get(entry["file"], {}).get("format") in ("prefs", "json") \
                    and value.startswith('"'):
                # Global value is JSON ("Vulkan"); this per-game ini stores it bare (DuckStation).
                value = json.loads(value)
            # JSON (and JSON inside prefs) keeps each value's type: quote only when the
            # stored value is a string, or nothing is stored and the glossary's values are strings.
            if before is not None:
                try:
                    textual = isinstance(json.loads(before), str)
                except json.JSONDecodeError:
                    textual = False
            else:
                vals = list((entry or {}).get("values") or {})
                textual = bool(entry) and (entry.get("type") == "string" or (vals and vals[0].startswith('"')))
            if not mapped and (spec.get("string_values") or (textual and (spec["format"] == "json" or "#" in key))):
                # JSON settings typed as text must be stored as JSON strings ("60", not 60).
                try:
                    is_str = isinstance(json.loads(value), str)
                except json.JSONDecodeError:
                    is_str = False
                if not is_str:
                    value = json.dumps(value)
            kw = {}
            if spec["format"] == "json":
                kw["create"] = True
            if spec["format"] == "prefs" and entry and entry.get("type") in ("bool", "int", "float", "string"):
                kw["kind"] = {"bool": "bool", "int": "int", "float": "float", "string": "string"}[entry["type"]]
            texts[path] = appconf.write(spec["format"], texts[path], key, value, **kw)
        after = appconf.lookup(spec["format"], texts[path], key)
        changes.append(dict(name=name, path=path, key=key, fmt=spec["format"], entry=entry,
                            before=before, after=after))
        mirror = (app.get("per_game") or {}).get("mirror") if game else None
        if mirror and key.startswith(mirror["from"].replace("{game}", game)):
            # Keep a second copy in step (WatermelonDS rom_metadata_mirror.json).
            mpath = expand(mirror["path"])
            mkey = mirror["to"].replace("{game}", game) + key[len(mirror["from"].replace("{game}", game)):]
            if mpath not in texts:
                originals[mpath] = read_file(mpath)
                if originals[mpath] is None:
                    raise SystemExit(f"{mpath} (mirror) does not exist")
                texts[mpath] = originals[mpath]
            mfmt = mirror.get("format", "json")
            texts[mpath] = (appconf.unset(mfmt, texts[mpath], mkey) if raw is None
                            else appconf.write(mfmt, texts[mpath], mkey, value, create=True))
            changes.append(dict(name=name + " (mirror)", path=mpath, key=mkey, fmt=mfmt, entry=entry,
                                before=None, after=appconf.lookup(mfmt, texts[mpath], mkey)))
    return texts, originals, changes


def verify(changes):
    bad = []
    cache = {}
    for c in changes:
        if c["path"] not in cache:
            cache[c["path"]] = read_file(c["path"]) or ""
        now = appconf.lookup(c["fmt"], cache[c["path"]], c["key"])
        if now != c["after"]:
            bad.append(f"{c['path']} {c['key']}: {now!r}, expected {c['after']!r}")
    return bad


def watch_roots(app):
    pkg = app["package"]
    roots = [f"/data/data/{pkg}", f"/sdcard/Android/data/{pkg}"]
    for spec in app["files"].values():
        parent = str(Path(expand(spec["path"])).parent)
        if "{" not in parent and not any(parent.startswith(r) for r in roots):
            roots.append(parent)
    roots += [expand(r) for r in app.get("watch_roots", [])]
    return roots


def snapshot_hashes(app):
    names = " -o ".join(f"-name {shlex.quote(e)}" for e in TEXT_EXT)
    prune = " -o ".join(f"-name {shlex.quote(d)}" for d in SKIP_DIRS + tuple(app.get("watch_exclude", [])))
    roots = " ".join(shlex.quote(r) for r in watch_roots(app))
    cmd = (f"find {roots} \\( -type d \\( {prune} \\) -prune \\) -o "
           f"\\( -type f -size -2048k \\( {names} \\) -print0 \\) 2>/dev/null | xargs -0 md5sum 2>/dev/null; true")
    out = {}
    for line in device.root(cmd).splitlines():
        digest, _, path = line.partition("  ")
        if path:
            out[path] = digest
    return out


def read_many(paths):
    """{path: text} for many device files in one root tar call."""
    if not paths:
        return {}
    import io
    import tarfile
    listing = "\n".join(paths) + "\n"
    device.adb("shell", f"cat > {STAGE}.list", input_bytes=listing.encode())
    raw = device.adb("exec-out", f"su -c 'tr \"\\n\" \"\\0\" < {STAGE}.list | xargs -0 tar -cf - 2>/dev/null; true'")
    out = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        for m in tar.getmembers():
            if m.isfile():
                out["/" + m.name.lstrip("/")] = tar.extractfile(m).read().decode(errors="replace")
    return out


def diff_lines(path, old, new):
    fmt = appconf.guess_format(path)
    if fmt:
        try:
            a, b = appconf.read(fmt, old or ""), appconf.read(fmt, new or "")
            out = []
            for k in sorted(set(a) | set(b)):
                if a.get(k) != b.get(k):
                    out.append(f"{path}  {k}: {a.get(k)} -> {b.get(k)}")
            return out
        except Exception as e:  # a format we only guessed may not parse; show the raw diff
            return [f"{path}: could not parse as {fmt} ({e}); raw diff:"] + raw_diff(old, new)
    return [f"{path}:"] + raw_diff(old, new)


def raw_diff(old, new):
    d = difflib.unified_diff((old or "").splitlines(), (new or "").splitlines(), lineterm="", n=0)
    return ["   " + l for l in list(d)[2:22]]


def glob_keys(app, patterns):
    keys = list(app["keys"])
    if not patterns:
        return keys
    return [k for k in keys if any(fnmatch.fnmatch(k, p) or p.lower() in k.lower()
                                   or p.lower() in (app["keys"][k].get("label") or "").lower() for p in patterns)]
