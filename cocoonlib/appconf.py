"""Line-preserving readers and editors for app config formats.

Every format exposes:
  read(text) -> {path: raw value string}
  write(text, path, raw) -> new text   (only the touched line changes)
  unset(text, path) -> new text        (back to the app's default / global)

Paths: "Section/key" for ini-like formats, the plain key for cfg and prefs,
a slash path for yaml and json. Raw values are strings exactly as stored
(prefs and json values are JSON-encoded scalars, e.g. true, 3, "text").
"""
import json
import re

from . import prefs as xmlprefs


# ------------------------------------------------------------------ ini

SECTION = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")
ENTRY = re.compile(r"^(?P<lead>\s*)(?P<key>[^=;#\[][^=]*?)(?P<sep>\s*=\s*)(?P<value>.*?)\s*$")


BOM = "\ufeff"


def _split_text(text):
    """(bom, newline, body): keep a leading byte-order mark and CRLF endings."""
    bom = BOM if text.startswith(BOM) else ""
    body = text[len(bom):]
    nl = "\r\n" if "\r\n" in body else "\n"
    return bom, nl, body.replace("\r\n", "\n")


def _join(bom, nl, lines):
    return bom + nl.join(lines) + nl


def ini_read(text):
    text = _split_text(text)[2]
    out, section = {}, ""
    for line in text.splitlines():
        m = SECTION.match(line)
        if m:
            section = m["name"]
            continue
        m = ENTRY.match(line)
        if m and not line.lstrip().startswith(("#", ";")):
            out[f"{section}/{m['key'].strip()}"] = m["value"]
    return out


def _split(path):
    if "/" not in path:
        raise SystemExit(f"{path!r}: ini keys are Section/key")
    section, key = path.split("/", 1)
    return section, key


def ini_write(text, path, raw, sep_default=" = "):
    section, key = _split(path)
    bom, nl, text = _split_text(text)
    lines = text.splitlines()
    cur, sec_start, sec_end, seps = "", None, None, []
    for i, line in enumerate(lines):
        m = SECTION.match(line)
        if m:
            if cur == section and sec_start is not None and sec_end is None:
                sec_end = i
            cur = m["name"]
            if cur == section:
                sec_start = i
            continue
        m = ENTRY.match(line)
        if m and not line.lstrip().startswith(("#", ";")):
            seps.append(m["sep"])
            if cur == section and m["key"].strip() == key:
                lines[i] = f"{m['lead']}{m['key']}{m['sep']}{raw}"
                return _join(bom, nl, lines)
    sep = max(set(seps), key=seps.count) if seps else sep_default
    if sec_start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"[{section}]", f"{key}{sep}{raw}"]
        return _join(bom, nl, lines)
    end = sec_end if sec_end is not None else len(lines)
    insert = end
    while insert > sec_start + 1 and not lines[insert - 1].strip():
        insert -= 1
    lines.insert(insert, f"{key}{sep}{raw}")
    return _join(bom, nl, lines)


def ini_unset(text, path):
    section, key = _split(path)
    bom, nl, text = _split_text(text)
    out, cur, removed = [], "", False
    for line in text.splitlines():
        m = SECTION.match(line)
        if m:
            cur = m["name"]
        else:
            e = ENTRY.match(line)
            if e and cur == section and e["key"].strip() == key:
                removed = True
                continue
        out.append(line)
    if not removed:
        raise SystemExit(f"{path} is not set")
    return _join(bom, nl, out)


# ------------------------------------------------------------------ Qt INI (yuzu/Eden)
# Global: `key\default=true` means "ignore the stored value, use the default".
# Per-game: `key\use_global=true` means "use the global value".

def qt_read(text, flag):
    raw = ini_read(text)
    out = {}
    for path, value in raw.items():
        if path.endswith("\\" + flag):
            continue
        state = raw.get(f"{path}\\{flag}")
        if flag == "default" and state == "true":
            out[path] = f"{value}  (default)"
        elif flag == "use_global" and state == "true":
            out[path] = "(global)"
        else:
            out[path] = value
    for path, value in raw.items():
        base = path[: -len(flag) - 1]
        if path.endswith("\\" + flag) and base not in raw:
            out[base] = "(default)" if flag == "default" else "(global)"
    return out


def qt_write(text, path, raw, flag):
    text = ini_write(text, f"{path}\\{flag}", "false", sep_default="=")
    if flag == "use_global":
        # Eden also reads `\default` in per-game files; a missing line counts as
        # true and the stored value is ignored. Its own per-game files carry all three.
        text = ini_write(text, f"{path}\\default", "false", sep_default="=")
    return ini_write(text, path, raw, sep_default="=")


def qt_unset(text, path, flag):
    return ini_write(text, f"{path}\\{flag}", "true", sep_default="=")


# ------------------------------------------------------------------ RetroArch cfg

CFG = re.compile(r'^(?P<key>[A-Za-z0-9_]+)\s*=\s*"?(?P<value>.*?)"?\s*$')


def cfg_read(text):
    out = {}
    for line in text.splitlines():
        m = CFG.match(line)
        if m and not line.lstrip().startswith("#"):
            out[m["key"]] = m["value"]
    return out


def cfg_write(text, key, raw):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = CFG.match(line)
        if m and m["key"] == key:
            lines[i] = f'{key} = "{raw}"'
            return "\n".join(lines) + "\n"
    lines.append(f'{key} = "{raw}"')
    return "\n".join(lines) + "\n"


def cfg_unset(text, key):
    lines = [l for l in text.splitlines() if not ((m := CFG.match(l)) and m["key"] == key)]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ YAML (maps of scalars)

YAML = re.compile(r"^(?P<indent> *)(?P<key>[^:#\-][^:]*?):(?:\s+(?P<value>[^#]*?))?\s*(?:#.*)?$")


def _yaml_walk(text):
    stack = []
    for i, line in enumerate(text.splitlines()):
        m = YAML.match(line)
        if not m:
            continue
        indent = len(m["indent"])
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, m["key"].strip().strip("'\"")))
        yield i, "/".join(k for _, k in stack), m


def yaml_read(text):
    return {path: m["value"] for _, path, m in _yaml_walk(text) if m["value"] not in (None, "")}


def yaml_write(text, path, raw):
    lines = text.splitlines()
    for i, p, m in _yaml_walk(text):
        if p == path:
            lines[i] = f"{m['indent']}{m['key']}: {raw}"
            return "\n".join(lines) + "\n"
    raise SystemExit(f"{path} is not in this YAML file; only existing keys can be set")


# ------------------------------------------------------------------ JSON

def _flatten(node, prefix, out):
    if isinstance(node, dict):
        for k, v in node.items():
            _flatten(v, f"{prefix}/{k}" if prefix else str(k), out)
    else:
        out[prefix] = json.dumps(node)
    return out


def json_read(text):
    return _flatten(json.loads(text or "{}"), "", {})


SELECT = re.compile(r"^\[(?P<field>[^=\]]+)=(?P<value>.*)\]$")


def _step(node, part, create, path):
    """One path segment: a dict key, or [field=value] picking a list element."""
    m = SELECT.match(part)
    if m:
        if not isinstance(node, list):
            raise SystemExit(f"{path}: {part} selects from a list, found {type(node).__name__}")
        hits = [e for e in node if isinstance(e, dict) and str(e.get(m["field"])) == m["value"]]
        if len(hits) != 1:
            raise SystemExit(f"{path}: {len(hits)} list entries have {m['field']} = {m['value']!r}")
        return hits[0]
    if part not in node:
        if not create:
            raise SystemExit(f"{path}: {part!r} missing")
        node[part] = {}
    return node[part]


def _parts(path):
    return [p for p in re.split(r"/(?![^\[]*\])", path) if p]


def json_lookup(text, path):
    node = json.loads(text or "{}")
    for part in _parts(path):
        try:
            node = _step(node, part, False, path)
        except SystemExit:
            return None
    return json.dumps(node)


def json_write(text, path, raw, create=False):
    """Set a slash path; with create, missing objects and keys are added."""
    doc = json.loads(text or "{}")
    compact = bool(text) and "\n" not in text.strip()
    node, parts = doc, _parts(path)
    for p in parts[:-1]:
        node = _step(node, p, create, path)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    if parts[-1] not in node and not create:
        raise SystemExit(f"{path} does not exist (fields here: {', '.join(node)})")
    node[parts[-1]] = value
    if compact:  # one-line files (Gson) stay one line
        return json.dumps(doc, separators=(",", ":"))
    return json.dumps(doc, indent=2) + "\n"


def json_unset(text, path):
    doc = json.loads(text or "{}")
    compact = bool(text) and "\n" not in text.strip()
    node, parts = doc, _parts(path)
    for p in parts[:-1]:
        node = _step(node, p, False, path)
    del node[parts[-1]]
    if compact:
        return json.dumps(doc, separators=(",", ":"))
    return json.dumps(doc, indent=2) + "\n"


# ------------------------------------------------------------------ Android prefs
# A key may carry a JSON path after '#', for prefs that store JSON strings.

def prefs_read(text):
    out = {}
    for key, (kind, value) in xmlprefs.parse(text).items():
        out[key] = json.dumps(value)
        if kind == "string" and value[:1] in "{[":
            try:
                for sub, v in _flatten(json.loads(value), "", {}).items():
                    out[f"{key}#{sub}"] = v
            except json.JSONDecodeError:
                pass
    return out


def prefs_write(text, path, raw, kind=None):
    entries = xmlprefs.parse(text)
    key, _, sub = path.partition("#")
    if sub:
        kind0, value = entries.get(key, ("string", "{}"))  # a missing JSON pref starts empty
        doc = json.loads(json_write(value, sub, raw, create=True))
        entries[key] = (kind0, json.dumps(doc, separators=(",", ":")))
        return xmlprefs.serialize(entries)
    if key in entries:
        kind = entries[key][0]
    if kind is None:
        raise SystemExit(f"{key} is not set yet and its type is unknown; pass --type")
    if kind == "string":
        value = json.loads(raw) if raw.startswith('"') else raw
    else:
        try:
            value = xmlprefs.coerce(kind, raw)
        except ValueError as e:
            raise SystemExit(f"{key}: {e}")
    entries[key] = (kind, value)
    return xmlprefs.serialize(entries)


def prefs_unset(text, path):
    entries = xmlprefs.parse(text)
    del entries[path]
    return xmlprefs.serialize(entries)


# ------------------------------------------------------------------ XML elements
# Path = element names from the root ("content/Graphic/VSync" = that element's text);
# "config/gpu@resolution-multiplier" = an attribute. Not Android prefs (that is "prefs").

import xml.etree.ElementTree as _ET


def _xml_parse(text):
    decl = text.split("?>", 1)[0] + "?>" if text.lstrip().startswith("<?xml") else ""
    return decl, _ET.fromstring(text[len(decl):].strip() if decl else text.strip())


def xml_read(text):
    out = {}

    def walk(el, path):
        for k, v in el.attrib.items():
            out[f"{path}@{k}"] = v
        kids = list(el)
        if not kids and (el.text or "").strip() != "" or (not kids and not el.attrib):
            out[path] = (el.text or "").strip()
        counts = {}
        for c in kids:
            counts[c.tag] = counts.get(c.tag, 0) + 1
        seen = {}
        for c in kids:
            seen[c.tag] = seen.get(c.tag, 0) + 1
            name = c.tag if counts[c.tag] == 1 else f"{c.tag}[{seen[c.tag]}]"
            walk(c, f"{path}/{name}")
    _, root = _xml_parse(text)
    walk(root, root.tag)
    return out


def xml_write(text, path, raw):
    decl, root = _xml_parse(text)
    elem_path, _, attr = path.partition("@")
    parts = elem_path.split("/")
    if parts[0] != root.tag:
        raise SystemExit(f"{path}: the root element is <{root.tag}>")
    el = root
    for part in parts[1:]:
        nxt = el.find(part.split("[")[0])
        if nxt is None:
            nxt = _ET.SubElement(el, part)
        el = nxt
    if attr:
        el.set(attr, raw)
    else:
        el.text = raw
    indent = "\t" if "\n\t<" in text else "    "
    _ET.indent(root, space=indent)
    body = _ET.tostring(root, encoding="unicode")
    return (decl + "\n" if decl else "") + body + "\n"


# ------------------------------------------------------------------ plain "key = value" (no sections)

KV = re.compile(r"^(?P<lead>\s*)(?P<key>[^=#;\s][^=]*?)(?P<sep>\s*=\s*)(?P<value>.*?)\s*$")


def kv_read(text):
    out = {}
    for line in _split_text(text)[2].splitlines():
        m = KV.match(line)
        if m and not line.lstrip().startswith(("#", ";", "[")):
            out[m["key"].strip()] = m["value"]
    return out


def kv_write(text, key, raw):
    bom, nl, body = _split_text(text)
    lines = body.splitlines()
    for i, line in enumerate(lines):
        m = KV.match(line)
        if m and m["key"].strip() == key and not line.lstrip().startswith(("#", ";")):
            lines[i] = f"{m['lead']}{m['key']}{m['sep']}{raw}"
            return _join(bom, nl, lines)
    seps = [m["sep"] for l in lines if (m := KV.match(l))]
    lines.append(f"{key}{seps[0] if seps else ' = '}{raw}")
    return _join(bom, nl, lines)


def kv_unset(text, key):
    bom, nl, body = _split_text(text)
    lines = [l for l in body.splitlines() if not ((m := KV.match(l)) and m["key"].strip() == key)]
    return _join(bom, nl, lines)


# ------------------------------------------------------------------ "key value // comment" (PICO-8)

SPACED = re.compile(r"^(?P<key>[A-Za-z0-9_]+)(?P<sep>[ \t]+)(?P<value>.*?)(?P<tail>\s*//.*)?$")


def spaced_read(text):
    out = {}
    for line in text.splitlines():
        m = SPACED.match(line)
        if m and not line.startswith("//"):
            out[m["key"]] = m["value"].strip()
    return out


def spaced_write(text, key, raw):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = SPACED.match(line)
        if m and m["key"] == key:
            lines[i] = f"{key}{m['sep']}{raw}{m['tail'] or ''}"
            return "\n".join(lines) + "\n"
    lines.append(f"{key} {raw}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ dispatch

FORMATS = {
    "ini": (ini_read, ini_write, ini_unset),
    # TOML tables and `key = value` lines; values stay in TOML syntax ("text", 1, true).
    "toml": (ini_read, ini_write, ini_unset),
    "qtini": (lambda t: qt_read(t, "default"),
              lambda t, p, r: qt_write(t, p, r, "default"),
              lambda t, p: qt_unset(t, p, "default")),
    "qtini-game": (lambda t: qt_read(t, "use_global"),
                   lambda t, p, r: qt_write(t, p, r, "use_global"),
                   lambda t, p: qt_unset(t, p, "use_global")),
    "cfg": (cfg_read, cfg_write, cfg_unset),
    "yaml": (yaml_read, yaml_write, None),
    "xml": (xml_read, xml_write, None),
    "spaced": (spaced_read, spaced_write, None),
    "kv": (kv_read, kv_write, kv_unset),
    "json": (json_read, json_write, json_unset),
    "prefs": (prefs_read, prefs_write, prefs_unset),
}


def guess_format(path):
    p = path.lower()
    if p.endswith(".xml"):
        return "prefs"
    if p.endswith((".yml", ".yaml")):
        return "yaml"
    if p.endswith(".json"):
        return "json"
    if p.endswith((".cfg", ".opt")):
        return "cfg"
    if p.endswith(".ini"):
        return "ini"
    if p.endswith(".toml"):
        return "toml"
    return None


def read(fmt, text):
    return FORMATS[fmt][0](text)


def lookup(fmt, text, key):
    """One key's raw value (json paths may use [field=value] list selectors)."""
    if fmt == "json" and "[" in key:
        return json_lookup(text, key)
    return read(fmt, text).get(key)


def write(fmt, text, path, raw, **kw):
    return FORMATS[fmt][1](text, path, raw, **kw)


def unset(fmt, text, path):
    fn = FORMATS[fmt][2]
    if fn is None:
        raise SystemExit(f"{fmt} keys cannot be unset; set the default value instead")
    return fn(text, path)
