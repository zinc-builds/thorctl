"""Cocoon settings: the generated catalog plus live reads and safe writes.

Cocoon keeps every setting in SharedPreferences XML files under
/data/data/rip.moth.cocoonshell/shared_prefs and reads them at start-up, so a
change takes effect once Cocoon restarts. Writing is a race against Cocoon,
which rewrites a whole file from memory whenever it saves anything and is
respawned by Android within ~200 ms of being killed. `apply()` therefore:

1. freezes Cocoon's process (SIGSTOP) so it cannot save mid-edit;
2. checks each file still has the checksum it had when it was read, and
   backs off (SIGCONT) if not;
3. overwrites the files in place (keeping owner and SELinux label), removes
   any `.bak` (SharedPreferences would restore it over the new file);
4. force-stops Cocoon, brings it back on display 0, and re-reads the files to
   prove the values survived the restart.
"""
import difflib
import hashlib
import io
import json
import re
import shlex
import tarfile
import time
from pathlib import Path

from . import device, prefs

CATALOG_DIR = Path(__file__).resolve().parent.parent / "catalog"
STAGE = "/data/local/tmp/cocoonctl-prefs"
SETTINGS = f"{device.PACKAGE}/.ui.activity.SettingsActivity"


# ---------------------------------------------------------------- catalog

def installed_version():
    out = device.adb("shell", f"dumpsys package {device.PACKAGE} | grep versionName").decode()
    m = re.search(r"versionName=(\S+)", out)
    if not m:
        raise RuntimeError("Cocoon is not installed")
    return m[1]


def load_catalog(strict=True):
    version = installed_version()
    path = CATALOG_DIR / f"cocoon-{version}.json"
    if not path.exists():
        have = sorted(p.stem for p in CATALOG_DIR.glob("cocoon-*.json"))
        msg = (f"no catalog for Cocoon {version} (have: {', '.join(have) or 'none'}). "
               "Rebuild it: see README 'Settings Catalog'.")
        if strict:
            raise SystemExit(msg)
        print(f"warning: {msg} Using {have[-1]}.")
        path = CATALOG_DIR / f"{have[-1]}.json"
    return json.loads(path.read_text())


def family_of(key, catalog):
    fams = [f for f in catalog["families"] if key.startswith(f)]
    return max(fams, key=len) if fams else None


def contract_for(key, catalog):
    c = catalog["contract"]
    if key in c["enums"]:
        return {"options": c["enums"][key]}
    if key in c["float_ranges"]:
        return {"range": c["float_ranges"][key]}
    if key in c["int_ranges"]:
        return {"range": c["int_ranges"][key]}
    if key in c["int_values"]:
        return {"options": c["int_values"][key]}
    return {}


# ---------------------------------------------------------------- device I/O

def read_files():
    """{file stem: raw bytes} for every prefs file, read in one root call."""
    raw = device.adb("exec-out", f"su -c 'cd {device.PREFS_DIR} && tar -cf - *.xml'")
    out = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        for m in tar.getmembers():
            if m.isfile() and m.name.endswith(".xml"):
                out[Path(m.name).stem] = tar.extractfile(m).read()
    if not out:
        raise RuntimeError("read no prefs files from the device")
    return out


def live_values(files):
    """{key: [(file, type, value), ...]} across every file."""
    out = {}
    for stem, raw in files.items():
        for key, (kind, value) in prefs.parse(raw.decode()).items():
            out.setdefault(key, []).append((stem, kind, value))
    return out


def wait_for_home(old_pid, timeout_s=20.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        pid = device.cocoon_pid()
        if pid and pid != old_pid:
            top = device.adb("shell", "dumpsys activity activities | grep topResumedActivity").decode()
            if f"{device.PACKAGE}/.MainActivity" in top:
                return pid
            device.adb("shell", "am start --display 0 -a android.intent.action.MAIN "
                                "-c android.intent.category.HOME")
        time.sleep(0.5)
    raise RuntimeError("Cocoon did not come back on display 0 after the restart")


def apply(new_texts, originals):
    """Write {stem: new xml text}; `originals` maps stem -> bytes as read."""
    device.adb("shell", "input keyevent KEYCODE_WAKEUP")
    device.adb("shell", f"rm -rf {STAGE} && mkdir -p {STAGE}")
    lines = ["set -e", f"D={device.PREFS_DIR}", f"S={STAGE}",
             f"P=$(pidof {device.PACKAGE} || true)",
             'fail() { [ -n "$P" ] && kill -CONT $P; echo "$1" >&2; exit 3; }',
             '[ -n "$P" ] && kill -STOP $P']
    ref = next(iter(originals))
    for stem, text in new_texts.items():
        device.adb("shell", f"cat > {STAGE}/{stem}.xml", input_bytes=text.encode())
        want = hashlib.md5(originals[stem]).hexdigest() if stem in originals else "absent"
        f = f"$D/{stem}.xml"
        lines.append(f'cur=$([ -f {f} ] && md5sum {f} | cut -d" " -f1 || echo absent)')
        lines.append(f'[ "$cur" = "{want}" ] || fail "{stem}.xml changed since it was read; nothing written"')
    for stem in new_texts:
        f = f"$D/{stem}.xml"
        lines.append(f"if [ -f {f} ]; then cat $S/{stem}.xml > {f}; else "
                     f"cp $S/{stem}.xml {f}; chown $(stat -c %u:%g $D) {f}; chmod 660 {f}; "
                     f"chcon $(stat -c %C $D/{ref}.xml) {f}; fi")
        lines.append(f"rm -f {f}.bak")
    lines.append(f"am force-stop {device.PACKAGE}")
    lines.append('echo "${P:-none}"')
    script = "\n".join(lines) + "\n"
    device.adb("shell", f"cat > {STAGE}/apply.sh", input_bytes=script.encode())
    old = device.root(f"sh {STAGE}/apply.sh").strip()
    pid = wait_for_home(old)
    device.adb("shell", f"rm -rf {STAGE}")
    return pid


# ---------------------------------------------------------------- planning

def parse_assignment(spec, stems):
    """`[file:]key[.json.path]=value` -> (file|None, key, path list, raw)."""
    if "=" not in spec:
        raise SystemExit(f"expected KEY=VALUE, got {spec!r}")
    lhs, raw = spec.split("=", 1)
    stem = None
    head, sep, rest = lhs.partition(":")
    if sep and (head in stems or head.endswith("_prefs") or head.startswith("cocoon_")):
        stem, lhs = head, rest
    key, *path = lhs.split(".")
    return stem, key, path, raw


def locate(key, stem, live, catalog):
    """Pick the prefs file and type for `key`; raise if ambiguous or unknown."""
    here = live.get(key, [])
    if stem:
        match = [h for h in here if h[0] == stem]
        if match:
            return stem, match[0][1]
    elif len(here) == 1:
        return here[0][0], here[0][1]
    elif len(here) > 1:
        raise SystemExit(f"{key} is in several files ({', '.join(h[0] for h in here)}); "
                         "prefix it with FILE:")
    entry = catalog["keys"].get(key)
    if entry is None and family_of(key, catalog) is None and not stem:
        raise SystemExit(f"{key} is not a key Cocoon uses (not in the catalog or on the device); "
                         "check `settings find`")
    files = [stem] if stem else (entry or {}).get("files", [])
    if len(files) != 1:
        raise SystemExit(f"{key} is not set yet and the catalog cannot tell which file it lives in "
                         f"(candidates: {files or 'none'}); prefix it with FILE:")
    types = (entry or {}).get("types", [])
    if len(types) != 1:
        raise SystemExit(f"{key}: type unknown (catalog says {types or 'nothing'})")
    return files[0], types[0]


def validate(key, kind, value, catalog):
    c = contract_for(key, catalog)
    if "options" in c and value not in c["options"]:
        raise SystemExit(f"{key}: {value!r} is not one of {c['options']}")
    if "range" in c and not (c["range"][0] <= value <= c["range"][1]):
        raise SystemExit(f"{key}: {value} is outside Cocoon's range {c['range']}")


def set_json_path(doc, path, raw):
    node = doc
    for p in path[:-1]:
        node = node[p]
    leaf = path[-1]
    if leaf not in node:
        raise SystemExit(f"{'.'.join(path)} is not a field of this JSON value "
                         f"(fields: {', '.join(node)})")
    old = node[leaf]
    try:
        node[leaf] = json.loads(raw)
    except json.JSONDecodeError:
        node[leaf] = raw
    if type(node[leaf]) is not type(old) and old is not None:
        raise SystemExit(f"{'.'.join(path)} was {type(old).__name__}, got {raw!r}")


def plan(specs, unset, files, catalog):
    """Return ({stem: new text}, [(file, key, old, new)])."""
    live = live_values(files)
    parsed = {stem: prefs.parse(raw.decode()) for stem, raw in files.items()}
    changes = []
    for spec in specs:
        stem, key, path, raw = parse_assignment(spec, files)
        stem, kind = locate(key, stem, live, catalog)
        entries = parsed.setdefault(stem, {})
        old = entries.get(key, (kind, None))[1]
        if path:
            if old is None:
                raise SystemExit(f"{key} has no value yet, so {'.'.join(path)} cannot be set inside it")
            doc = json.loads(old)
            set_json_path(doc, path, raw)
            new = json.dumps(doc, separators=(",", ":"))
        else:
            try:
                new = prefs.coerce(kind, raw)
            except ValueError as e:
                raise SystemExit(f"{key}: {e}")
            validate(key, kind, new, catalog)
        entries[key] = (kind, new)
        if path:
            shown = (f"{key}.{'.'.join(path)}", _field(old, path), _field(new, path))
        else:
            shown = (key, old, new)
        changes.append((stem, key, old, new, shown))
    for spec in unset:
        stem, _, key = spec.rpartition(":")
        hits = [h for h in live.get(key, []) if not stem or h[0] == stem]
        if len(hits) != 1:
            raise SystemExit(f"--unset {spec}: found in {len(hits)} files")
        del parsed[hits[0][0]][key]
        changes.append((hits[0][0], key, hits[0][2], None, (key, hits[0][2], None)))
    touched = {c[0] for c in changes}
    texts = {stem: prefs.serialize(parsed[stem]) for stem in touched}
    return texts, changes


def _field(text, path):
    node = json.loads(text)
    for p in path:
        node = node[p]
    return node


def verify(changes):
    live = live_values(read_files())
    bad = []
    for stem, key, _, new, _ in changes:
        got = [v for f, _, v in live.get(key, []) if f == stem]
        now = got[0] if got else None
        if now != new:
            bad.append(f"{stem}:{key} is {now!r} after restart, expected {new!r}")
    return bad


# ---------------------------------------------------------------- search

def words(text):
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if w}


def find(query, catalog, live):
    """Rank keys and Settings pages against free text."""
    q = words(query)
    results = []
    for e in catalog["search_index"]["entries"]:
        hay = words(" ".join([e["label"], e["section"], e["subsection"] or "", *e["keywords"]]))
        score = len(q & hay) * 2 + (query.lower() in e["label"].lower()) * 5
        if score:
            results.append((score, "page", e))
    keys = set(catalog["keys"]) | set(live)
    for k in keys:
        hay = words(k.replace("_", " "))
        score = len(q & hay) * 2 + (query.lower().replace(" ", "_") in k) * 5
        if score:
            results.append((score, "key", k))
    results.sort(key=lambda r: -r[0])
    return results


def describe_key(key, catalog, live, reveal=False):
    entry = catalog["keys"].get(key, {})
    here = live.get(key, [])
    fam = family_of(key, catalog) if not entry else None
    where = ",".join(h[0] for h in here) or ",".join(entry.get("files", [])) or "?"
    kind = here[0][1] if here else "/".join(entry.get("types", [])) or "?"
    value = prefs.show(key, here[0][2], reveal) if here else "(unset)"
    bits = [f"{where}:{key}", kind, value]
    d = entry.get("defaults")
    if d and not here:
        bits.append(f"default={json.dumps(d[0]) if not isinstance(d[0], dict) else d[0]['expr']}")
    c = contract_for(key, catalog)
    if c:
        bits.append(f"options={c['options']}" if "options" in c else f"range={c['range']}")
    if fam:
        bits.append(f"family={fam}*")
    return "  ".join(bits)


# ---------------------------------------------------------------- pages

def resolve_page(target, catalog):
    """A Settings search-index label, `TAB[:CARD]`, or an activity name."""
    if re.fullmatch(r"\d+(:\d+)?", target):
        tab, _, card = target.partition(":")
        return {"tab": int(tab), "card": int(card or 0)}
    for a in catalog["activities"]:
        if a.lower() == target.lower() or a.lower() == target.lower() + "activity":
            return {"activity": a}
    hits = find(target, catalog, {})
    pages = [h[2] for h in hits if h[1] == "page"]
    if not pages:
        raise SystemExit(f"no Settings page matches {target!r}; see `settings pages`")
    return pages[0]


def open_page(page):
    device.adb("shell", "input keyevent KEYCODE_WAKEUP")
    if "activity" in page:
        cmd = f"am start -n {device.PACKAGE}/.ui.activity.{page['activity']}"
    else:
        # A few cards move at runtime (Cocoon computes their index from a
        # feature flag); for those open the tab and let the caller scroll.
        cmd = (f"am start -n {SETTINGS} --ei settings_initial_tab_index {page['tab']} "
               f"--ei settings_initial_content_index {page['card'] or 0} "
               "--ez settings_focus_content_on_launch true")
    return device.root(cmd)


def diff_text(before, after):
    out = []
    for stem in sorted(set(before) | set(after)):
        a = prefs.parse(before.get(stem, b"").decode())
        b = prefs.parse(after.get(stem, b"").decode())
        for key in sorted(set(a) | set(b)):
            va, vb = a.get(key, (None, None))[1], b.get(key, (None, None))[1]
            if va == vb:
                continue
            if isinstance(va, str) and isinstance(vb, str) and va.startswith("{") and vb.startswith("{"):
                try:
                    ja, jb = json.loads(va), json.loads(vb)
                    for line in difflib.unified_diff(
                            json.dumps(ja, indent=1).splitlines(), json.dumps(jb, indent=1).splitlines(),
                            lineterm="", n=0):
                        if line[:1] in "+-" and not line.startswith(("+++", "---")):
                            out.append(f"{stem}:{key} {line}")
                    continue
                except json.JSONDecodeError:
                    pass
            out.append(f"{stem}:{key}: {prefs.show(key, va)} -> {prefs.show(key, vb)}")
    return out


def quote(s):
    return shlex.quote(s)
