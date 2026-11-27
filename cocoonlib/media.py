"""Cocoon's media URIs and file naming.

Cocoon stores artwork as Storage Access Framework document URIs such as
content://com.android.externalstorage.documents/tree/primary%3ACocoon/
document/primary%3ACocoon%2Fdownloaded_media%2Fgba%2Ficon%2FGame.png
and names user edits `<rom stem>__cocoon_edit_<game id>_<uuid hex>.<ext>`.
"""
import uuid
from pathlib import PurePosixPath
from urllib.parse import quote, unquote

KINDS = {"boxArt": "icon", "logo": "logo", "hero": "hero"}

# Android's Uri.encode leaves these unescaped.
_URI_SAFE = "_-!.~'()*"
_VOLUMES = {"primary": "/storage/emulated/0"}


def split_uri(uri):
    """Return (tree prefix up to and including '/document/', document id)."""
    marker = "/document/"
    if marker not in uri:
        raise ValueError(f"not a SAF document URI: {uri}")
    head, doc = uri.split(marker, 1)
    return head + marker, unquote(doc)


def document_to_path(doc_id):
    volume, rel = doc_id.split(":", 1)
    base = _VOLUMES.get(volume, f"/storage/{volume}")
    return f"{base}/{rel}"


def sibling(uri, filename):
    """URI and device path for `filename` in the same folder as `uri`."""
    prefix, doc = split_uri(uri)
    new_doc = str(PurePosixPath(doc).with_name(filename))
    return prefix + quote(new_doc, safe=_URI_SAFE), document_to_path(new_doc)


def edit_filename(rom_file_name, game_id, ext):
    stem = PurePosixPath(rom_file_name).stem
    return f"{stem}__cocoon_edit_{game_id}_{uuid.uuid4().hex}.{ext}"


def platform_media_uri(root_uri, platform_id, folder, rom_file_name):
    """URI for a not-yet-existing file in <root>/<platform>/<folder>/, for games
    that have no art yet. root_uri is a document URI of the downloaded_media
    folder itself (see db.media_root_uri)."""
    prefix, doc = split_uri(root_uri)
    stem = PurePosixPath(rom_file_name).stem
    return prefix + quote(f"{doc}/{platform_id}/{folder}/{stem}.png", safe=_URI_SAFE)
