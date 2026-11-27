"""Android SharedPreferences XML files: parse, edit, serialize."""
import json
import xml.etree.ElementTree as ET

HEADER = "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n"
TAGS = {"boolean": "bool", "string": "string", "int": "int", "long": "long",
        "float": "float", "set": "string_set"}
TAG_FOR = {v: k for k, v in TAGS.items()}
SECRET_WORDS = ("api_key", "apikey", "password", "token", "secret", "cookie", "credential")


def parse(text):
    """Return {key: (type, value)} in file order."""
    out = {}
    if not text.strip():
        return out
    for el in ET.fromstring(text):
        kind = TAGS[el.tag]
        name = el.get("name")
        if kind == "string":
            out[name] = (kind, el.text or "")
        elif kind == "string_set":
            out[name] = (kind, [c.text or "" for c in el])
        elif kind == "bool":
            out[name] = (kind, el.get("value") == "true")
        elif kind in ("int", "long"):
            out[name] = (kind, int(el.get("value")))
        else:
            out[name] = (kind, float(el.get("value")))
    return out


def serialize(entries):
    root = ET.Element("map")
    for name, (kind, value) in entries.items():
        el = ET.SubElement(root, TAG_FOR[kind], name=name)
        if kind == "string":
            el.text = value
        elif kind == "string_set":
            for v in value:
                ET.SubElement(el, "string").text = v
        elif kind == "bool":
            el.set("value", "true" if value else "false")
        else:
            el.set("value", repr(value) if kind == "float" else str(value))
    ET.indent(root, space="    ")
    return HEADER + ET.tostring(root, encoding="unicode") + "\n"


def coerce(kind, raw):
    """Turn command-line text into a typed value."""
    if kind == "bool":
        low = raw.lower()
        if low not in ("true", "false", "1", "0", "on", "off"):
            raise ValueError(f"expected true/false, got {raw!r}")
        return low in ("true", "1", "on")
    if kind in ("int", "long"):
        return int(raw)
    if kind == "float":
        return float(raw)
    if kind == "string_set":
        value = json.loads(raw)
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError("string_set values are JSON arrays of strings")
        return value
    return raw


def is_secret(key):
    return any(w in key.lower() for w in SECRET_WORDS)


def show(key, value, reveal=False):
    if is_secret(key) and not reveal and value not in ("", None):
        return "<redacted>"
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return str(value).lower() if isinstance(value, bool) else str(value)
