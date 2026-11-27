"""Cocoon's Room database: reads from a local snapshot, SQL for live edits."""
import sqlite3
from pathlib import Path

GAME_COLUMNS = ("id", "platformId", "fileName", "displayName", "title",
                "hashMd5", "steamGridDbId", "boxArtSource", "boxArtLocal",
                "logoLocal", "heroLocal", "isHidden")
MEDIA_KINDS = ("boxArt", "logo", "hero")


def open_snapshot(snapshot: Path):
    # A local copy, opened read-write: a WAL-mode file cannot be opened
    # read-only before SQLite has created its -shm index.
    con = sqlite3.connect(snapshot / "cocoon_db")
    con.row_factory = sqlite3.Row
    return con


def find_games_sql(text=None, platform=None):
    sql = f"SELECT {', '.join(GAME_COLUMNS[:8])} FROM games WHERE 1=1"
    if text:
        pattern = literal(f"%{text}%")
        sql += f" AND (fileName LIKE {pattern} OR displayName LIKE {pattern} OR title LIKE {pattern})"
    if platform:
        sql += f" AND platformId = {literal(platform)}"
    return sql + " ORDER BY platformId, fileName;"


def game(con, game_id):
    row = con.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if row is None:
        raise KeyError(f"no game with id {game_id}")
    return row


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def set_media_sql(game_id, kind, uri):
    """Point one media slot at `uri`, marked user-set so rescrapes keep it."""
    if kind not in MEDIA_KINDS:
        raise ValueError(kind)
    return (f"UPDATE games SET {kind}Local = {literal(uri)}, {kind}Source = 'user' "
            f"WHERE id = {int(game_id)};")


def set_steamgriddb_id_sql(game_id, sgdb_id):
    return f"UPDATE games SET steamGridDbId = {int(sgdb_id)} WHERE id = {int(game_id)};"


def rename_sql(game_id, name):
    """Lists show displayName (from the file name); scrapes fill title. Set both."""
    return (f"UPDATE games SET displayName = {literal(name)}, title = {literal(name)} "
            f"WHERE id = {int(game_id)};")


def media_root_uri(con):
    """Document URI of Cocoon's downloaded_media folder, taken from existing art."""
    row = con.execute("SELECT boxArtLocal FROM games WHERE boxArtLocal LIKE "
                      "'content://%/document/%downloaded_media%' LIMIT 1").fetchone()
    if row is None:
        raise RuntimeError("no existing art to locate Cocoon's downloaded_media folder")
    uri = row[0]
    marker = "downloaded_media"
    return uri[:uri.index(marker) + len(marker)]
