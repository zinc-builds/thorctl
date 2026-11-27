#!/usr/bin/env python3
"""Build Cocoon's settings catalog from a jadx decompile of its APK.

  build_catalog.py JADX_SOURCES_DIR VERSION > catalog/cocoon-VERSION.json

Cocoon is closed source and R8-obfuscated, so this reads only things that
survive obfuscation and stay stable between releases:

- every SharedPreferences key used as a string literal (or a String
  constant), with its type and the default Cocoon falls back to;
- which prefs file a key lives in, when the code that touches it names one;
- the allowed values and ranges Cocoon itself enforces when it restores an
  appearance backup (rip.moth.cocoonshell.backup.AppearanceRestorePlanner);
- the Settings search index (label, section, tab and card index), which is
  what SettingsActivity's settings_initial_tab_index /
  settings_initial_content_index extras point at.

Regenerate after every Cocoon update (see README "Settings Catalog").
"""
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

PREF_CALL = re.compile(
    r'\.(get|put)(Boolean|String|Int|Float|Long|StringSet)\('
    r'(?P<key>"[^"\\]+"|[A-Za-z_][\w.]*)(?:, (?P<default>[^;]*?))?\)')
STRING_CONST = re.compile(r'static final String (\w+) = "([^"\\]+)";')
PREFS_FILE = re.compile(r'getSharedPreferences\((?P<arg>"[\w.]+"|[A-Za-z_][\w.]*), ')
SECTIONS = ("Look & feel", "Grid & layout", "Library & data", "Integrations", "System & advance")
TYPE_NAMES = {"Boolean": "bool", "String": "string", "Int": "int", "Float": "float",
              "Long": "long", "StringSet": "string_set"}


def grep_files(root, pattern):
    r = subprocess.run(["grep", "-rlE", pattern, str(root)], capture_output=True, text=True)
    if r.returncode not in (0, 1):
        raise RuntimeError(r.stderr)
    return [Path(p) for p in r.stdout.split()]


def string_constants(root):
    consts = defaultdict(set)
    for f in grep_files(root, r'static final String \w+ = "'):
        for name, value in STRING_CONST.findall(f.read_text(errors="replace")):
            consts[name].add(value)
    return {k: next(iter(v)) for k, v in consts.items() if len(v) == 1}


def resolve_string(expr, consts):
    expr = expr.strip()
    if expr.startswith('"'):
        return expr[1:-1]
    return consts.get(expr.split(".")[-1])


def parse_default(raw, kind):
    if raw is None:
        return None
    raw = raw.strip()
    if kind == "bool" and raw in ("true", "false"):
        return raw == "true"
    if kind in ("int", "long") and re.fullmatch(r"-?\d+L?", raw):
        return int(raw.rstrip("L"))
    if kind == "float" and re.fullmatch(r"-?[\d.]+f?", raw):
        return float(raw.rstrip("f"))
    if kind == "string" and re.fullmatch(r'"[^"]*"', raw):
        return raw[1:-1]
    if raw == "null":
        return None
    return {"expr": raw[:80]}


ASSIGN = re.compile(r'(?:[\w.]+ )?(?:this\.)?(\w+) = (.+);$')
FIELD_STORE = re.compile(r'this\.(\w+) = (\w+);$')


def receiver_root(expr):
    """`this.f47720b.edit()` -> `f47720b`; `editorEdit` -> `editorEdit`."""
    expr = re.sub(r"\.(edit|remove|put\w+|clear)\(.*$", "", expr.strip())
    expr = re.sub(r"^\(?\(?[\w.]*\)\s*", "", expr)  # casts
    return expr.split(".")[-1] if expr else None


def prefs_name_of(rhs, consts, aliases, fields):
    m = PREFS_FILE.search(rhs)
    if m:
        return resolve_string(m["arg"], consts)
    root = receiver_root(rhs)
    return aliases.get(root) or fields.get(root)


def prefs_fields(files, consts):
    """Obfuscated field names (f47720b) that hold one named prefs file."""
    found = defaultdict(set)
    for f in files:
        local = {}
        for line in f.read_text(errors="replace").splitlines():
            line = line.strip()
            m = ASSIGN.match(line)
            if m and "getSharedPreferences(" in m[2]:
                name = prefs_name_of(m[2], consts, {}, {})
                if name:
                    local[m[1]] = name
                    if line.startswith("this."):
                        found[m[1]].add(name)
            m = FIELD_STORE.match(line)
            if m and m[2] in local:
                found[m[1]].add(local[m[2]])
    return {k: next(iter(v)) for k, v in found.items() if len(v) == 1}


def pref_keys(root, consts):
    files = grep_files(root, r'\.(get|put)(Boolean|String|Int|Float|Long|StringSet)\(')
    fields = prefs_fields(grep_files(root, r"getSharedPreferences\("), consts)
    keys = {}
    for f in files:
        aliases = {}
        for line in f.read_text(errors="replace").splitlines():
            line = line.strip()
            m = ASSIGN.match(line)
            if m:
                name = prefs_name_of(m[2], consts, aliases, fields)
                if name:
                    aliases[m[1]] = name
                else:
                    aliases.pop(m[1], None)
            for m in PREF_CALL.finditer(line):
                key = resolve_string(m["key"], consts)
                if not key or not re.fullmatch(r"[a-z][a-z0-9_:.]*", key):
                    continue
                kind = TYPE_NAMES[m.group(2)]
                e = keys.setdefault(key, {"types": set(), "defaults": [], "files": set(), "sources": set()})
                e["types"].add(kind)
                e["sources"].add(str(f.relative_to(root)))
                if m.group(1) == "get":
                    d = parse_default(m["default"], kind)
                    if d is not None and d not in e["defaults"]:
                        e["defaults"].append(d)
                before = line[:m.start()]
                recv = re.search(r"([\w.]+(?:\(\))?)$", before)
                name = None
                if recv:
                    r = receiver_root(recv[1])
                    name = aliases.get(r) or fields.get(r)
                if name:
                    e["files"].add(name)
    return keys


def split_args(s):
    """Split a Java argument list at top-level commas."""
    out, depth, cur, quote = [], 0, "", False
    for i, ch in enumerate(s):
        if ch == '"' and (i == 0 or s[i - 1] != "\\"):
            quote = not quote
        if not quote:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                if depth == 0:
                    out.append(cur.strip())
                    return out, i
                depth -= 1
            elif ch == "," and depth == 0:
                out.append(cur.strip())
                cur = ""
                continue
        cur += ch
    raise ValueError("unbalanced argument list")


def enum_constants(root, cls_ref, imports, pkg):
    """Ordered constant names of an obfuscated enum class, e.g. `w2`."""
    fq = imports.get(cls_ref, f"{pkg}.{cls_ref}")
    path = root / (fq.replace(".", "/") + ".java")
    text = path.read_text(errors="replace")
    names = re.findall(r'= new \w+\("(\w+)", (\d+)[,)]', text)
    if names:
        return [n for n, _ in sorted(names, key=lambda t: int(t[1]))]
    body = re.search(r'enum \w+ [^{]*\{\s*([^;]*);', text)
    return [c.split("(")[0].strip() for c in body.group(1).split(",")] if body else []


def eval_int(expr, local_ints, root, imports, pkg):
    expr = expr.strip()
    if re.fullmatch(r"-?\d+", expr):
        return int(expr)
    if expr in local_ints:
        return local_ints[expr]
    m = re.fullmatch(r"(\w+)\.(\w+)\.ordinal\(\)", expr)
    if m:
        return enum_constants(root, m[1], imports, pkg).index(m[2])
    if "+" in expr:
        return sum(eval_int(p, local_ints, root, imports, pkg) for p in expr.split("+"))
    return None


def search_index(root):
    files = grep_files(root, r'new \w+\("[^"]+", "Look & feel"')
    best = max(files, key=lambda f: f.read_text(errors="replace").count('", "Look & feel"'))
    text = best.read_text(errors="replace")
    pkg = re.search(r"^package ([\w.]+);", text, re.M)[1]
    imports = {i.split(".")[-1]: i for i in re.findall(r"^import ([\w.]+);", text, re.M)}
    local_ints = {}
    entries = []
    for line in text.splitlines():
        m = re.search(r"int (\w+) = ([\w .+()]+);", line)
        if m and '"' not in line:
            v = eval_int(m[2], local_ints, root, imports, pkg)
            if v is not None:
                local_ints[m[1]] = v
        m = re.search(r'= new \w+\((".*)$', line)
        if not m or not any(f'"{s}"' in line for s in SECTIONS):
            continue
        args, _ = split_args(m[1])
        label, section, sub = (resolve_string(a, {}) if a != "null" else None for a in args[:3])
        tab = eval_int(args[4], local_ints, root, imports, pkg)
        card = eval_int(args[5], local_ints, root, imports, pkg)
        action = args[6][1:-1] if args[6].startswith('"') else None
        words = re.findall(r'"([^"]+)"', args[7]) if len(args) > 7 else []
        entries.append({"label": label, "section": section, "subsection": sub or None,
                        "tab": tab, "card": card, "action": action, "keywords": words})
    return {"source": str(best.relative_to(root)), "entries": entries}


def restore_contract(root, consts):
    path = root / "rip/moth/cocoonshell/backup/AppearanceRestorePlanner.java"
    text = path.read_text(errors="replace")
    out = {"enums": {}, "float_ranges": {}, "int_ranges": {}, "int_values": {}}
    for key, vals in re.findall(r'new \w+\.\w+\("(\w+)", \w+\.\w+\.\w+\(new String\[\]\{([^}]*)\}\)\)', text):
        out["enums"][key] = re.findall(r'"(\w+)"', vals)
    for key, lo, hi in re.findall(r'new \w+\.\w+\("(\w+)", new \w+\.\w+\((-?[\d.]+)f, (-?[\d.]+)f\)\)', text):
        out["float_ranges"][key] = [float(lo), float(hi)]
    for key, lo, hi in re.findall(r'new \w+\.\w+\(("\w+"|[\w.]+), new \w+\.\w+\((-?\d+), (-?\d+), 1\)\)', text):
        out["int_ranges"][resolve_string(key, consts)] = [int(lo), int(hi)]
    for key, vals in re.findall(r'new \w+\.\w+\("(\w+)", \w+\.\w+\.\w+\(new Integer\[\]\{([^}]*)\}\)\)', text):
        out["int_values"][key] = [int(v) for v in re.findall(r"-?\d+", vals)]
    return out


def key_families(root, consts):
    """Prefixes of keys built at runtime, e.g. folder_zoom_<folderId>."""
    out = set()
    for f in grep_files(root, r'"[a-z][a-z0-9_]*_" \+'):
        text = f.read_text(errors="replace")
        if "SharedPreferences" not in text and "getSharedPreferences" not in text:
            continue
        out |= set(re.findall(r'"([a-z][a-z0-9_]*_)" \+', text))
    return sorted(out)


def activities(root):
    d = root / "rip/moth/cocoonshell/ui/activity"
    return sorted(p.stem for p in d.glob("*Activity.java"))


def main():
    root, version = Path(sys.argv[1]), sys.argv[2]
    consts = string_constants(root)
    keys = pref_keys(root, consts)
    contract = restore_contract(root, consts)
    catalog = {
        "cocoon_version": version,
        "keys": {k: {"types": sorted(v["types"]), "defaults": v["defaults"],
                     "files": sorted(v["files"]), "sources": sorted(v["sources"])[:5]}
                 for k, v in sorted(keys.items())},
        "families": key_families(root, consts),
        "contract": contract,
        "search_index": search_index(root),
        "activities": activities(root),
    }
    json.dump(catalog, sys.stdout, indent=1, default=str)
    print()


if __name__ == "__main__":
    main()
