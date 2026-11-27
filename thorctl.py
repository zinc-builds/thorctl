#!/usr/bin/env python3
"""thorctl: drive the AYN Thor over adb - Cocoon, any app's settings, the screen.
(`cocoonctl.py` is an alias of this file; `thorctl` is on PATH.)

Cocoon library (rip.moth.cocoonshell):

  thorctl snapshot                      copy DB + prefs to snapshots/<time>
  thorctl games [-m TEXT] [-p PLATFORM]  list games
  thorctl sgdb-search TERM              SteamGridDB games matching TERM
  thorctl set-art GAME=SGDB [...]       replace icon/logo/hero with the
                                             first-ranked SteamGridDB assets
                [--asset boxArt=ID ...]      or with chosen asset ids
  thorctl set-art-file GAME --asset boxArt=PATH [...]
                                             use local image files instead
  thorctl rename GAME_ID "Name"         set the name shown in lists
  thorctl art-dupes                     games sharing identical icon files
  thorctl sql "SELECT ..."              read-only SQL against the live DB
  thorctl sql --write "UPDATE ..."      run SQL in one transaction, then
                                             restart Cocoon so it reloads
  thorctl sync-install                  install/update the on-device
                                             auto-import watcher and start it
  thorctl sync-status                   watcher pid and recent log
  thorctl sync ARGS...                  run device cocoon-sync.sh, e.g.
                                             sync normalize psx --dry-run

Settings (every menu option is a SharedPreferences key; see README):
  thorctl settings find TEXT            keys and Settings pages matching TEXT
  thorctl settings get [KEY|GLOB ...]   live values (secrets redacted)
  thorctl settings set KEY=VALUE [...]  write, restart Cocoon, verify;
                [FILE:]KEY.json.field=VALUE  edits one field of a JSON setting
                --unset [FILE:]KEY           remove (back to Cocoon's default)
  thorctl settings watch [--seconds N]  print every prefs change as it
                                             happens (learn an unknown toggle)
  thorctl settings pages                Settings search index (open targets)
  thorctl settings open TARGET          open Settings at a page: a label
                                             ("Dock settings"), TAB:CARD, or an
                                             activity (GridSettingsActivity)
  thorctl restart                       restart Cocoon on both screens

Screen (on-device agent, no root; -d top|bottom; reads default to both screens):
  thorctl ui tree [-d D] [--all]        labelled elements with centre coords
  thorctl ui click TEXT [-d D]          click the element whose label matches
  thorctl ui type TEXT                  type into Cocoon's keyboard (via Paste)
  thorctl ui settext VALUE [--field T]  fill a real Android text field
  thorctl ui pad A DOWN DOWN A          real controller presses (A B X Y UP
                                             DOWN LEFT RIGHT L1 R1 L2 R2 START
                                             SELECT MODE L3 R3)
  thorctl ui home NAME [--open]         D-pad to a home tile or a game in a manual
                                             folder, verify its name, optionally open
  thorctl ui home --list                home grid as rows/cols with names
  thorctl ui focused                    which grid item has focus (Y menu)
  thorctl ui pick PATH [--folder]       drive Android's file picker to a file/folder
  thorctl ui tap X Y [-d D]             also: swipe, key back|home|..., wait
  thorctl ui stop                       stop the agent

App settings (emulators and any app; adapters in apps/*.json):
  thorctl app list                      adapters, installed versions
  thorctl app coverage [--mark-seen]    installed emulators/recomps: covered, draft,
                                             missing; NEW = not seen before
  thorctl app discover PACKAGE          draft an adapter + research brief from the
                                             app's config files and APK
  thorctl app autodiscover [--dry-run]  discover every NEW uncovered app (daily job)
  thorctl app keys NAME [WORDS]         glossary: setting, label, values
  thorctl app get NAME [WORDS] [--game ID] [--all]
  thorctl app set NAME KEY=VALUE [...] [--game ID] [--stop] [--dry-run]
                KEY is a glossary name or FILE:Section/key; VALUE may be a
                value's meaning ("Vulkan") or its raw form ("1")
  thorctl app unset NAME KEY [--game ID]   back to default / global
  thorctl app restore NAME BACKUP_DIR   put back files saved by an earlier set
  thorctl app games NAME                per-game files that exist
  thorctl app watch NAME [--seconds N]  print every config change as you
                                             change settings in the app
Recomps:
  thorctl recomps [list|show WORDS|build]    catalog of installed recomps/ports
                                             (recomps/CATALOG.md); build merges
                                             recomps/entries/*.json
  NAME: adapter name, alias (ps2, switch, gc, steam) or any package name
  thorctl shot [DIR]                    screenshot both screens

Writes back up the live database to /data/local/tmp first. set-art --dry-run
prints the plan without touching the device. ANDROID_SERIAL picks a device.
"""
import argparse
import json
import re
import sys
import tempfile
import time
from pathlib import Path

import fnmatch
import shlex
import subprocess

from cocoonlib import appconf, apps, db, discover, recomps, device, media, prefs, settings, sgdb, sync, ui

SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"


def new_snapshot():
    return device.pull_snapshot(SNAPSHOTS / time.strftime("%Y%m%d-%H%M%S"))


def cmd_snapshot(_):
    print(new_snapshot())


def sgdb_client():
    return sgdb.Client(sgdb.key_from_prefs(device.read_pref("ui_prefs.xml")))


def cmd_games(args):
    sys.stdout.write(device.query(db.find_games_sql(args.match, args.platform)))


def cmd_sgdb_search(args):
    client = sgdb_client()
    for g in client.search(args.term):
        print(f"{g['id']}\t{g['name']}")


def parse_specs(specs):
    out = []
    for s in specs:
        game_id, sgdb_id = s.split("=", 1)
        out.append((int(game_id), int(sgdb_id)))
    return out


def art_target(con, row, kind, folder):
    """The SAF URI next to which new art is written. Android apps Cocoon has
    not scraped point at its private android_app_icons/ folder (a plain path),
    so their art goes into downloaded_media/<platform>/<folder>/ instead."""
    current = row[f"{kind}Local"]
    if current and "/document/" in current:
        return current
    return media.platform_media_uri(db.media_root_uri(con), row["platformId"], folder, row["fileName"])


def plan_art(con, client, specs, workdir, picks=None):
    """Download assets and work out new file names; returns a list of edits.

    picks maps a media kind (boxArt, logo, hero) to a SteamGridDB asset id to
    use instead of the first-ranked one."""
    picks = picks or {}
    edits = []
    for game_id, sgdb_id in specs:
        row = db.game(con, game_id)
        for kind, folder in media.KINDS.items():
            current = art_target(con, row, kind, folder)
            asset =(client.asset_by_id(kind, sgdb_id, picks[kind]) if kind in picks
                     else client.first_asset(kind, sgdb_id))
            local, ext = sgdb.download(asset, workdir)
            name = media.edit_filename(row["fileName"], game_id, ext)
            uri, path = media.sibling(current, name)
            if f"/{folder}/" not in path:
                raise RuntimeError(f"{kind} for game {game_id} is not in a /{folder}/ folder: {path}")
            edits.append(dict(game_id=game_id, sgdb_id=sgdb_id, kind=kind,
                              asset_id=asset["id"], local=local, uri=uri, path=path,
                              title=row["fileName"]))
    return edits


def cmd_set_art(args):
    specs = parse_specs(args.specs)
    with tempfile.TemporaryDirectory() as tmp:
        con = db.open_snapshot(device.pull_snapshot(Path(tmp) / "snapshot"))
        picks = dict((k, int(v)) for k, v in (a.split("=", 1) for a in args.asset))
        if picks and len(specs) != 1:
            raise SystemExit("--asset needs exactly one GAME=SGDB spec")
        unknown = set(picks) - set(media.KINDS)
        if unknown:
            raise SystemExit(f"--asset kinds must be {', '.join(media.KINDS)}; got {', '.join(unknown)}")
        edits = plan_art(con, sgdb_client(), specs, Path(tmp), picks)
        for e in edits:
            print(f"{e['title']}: {e['kind']} <- sgdb asset {e['asset_id']} -> {e['path']}")
        if args.dry_run:
            return
        for e in edits:
            device.push_media(e["local"], e["path"])
    statements = [db.set_media_sql(e["game_id"], e["kind"], e["uri"]) for e in edits]
    statements += sorted({db.set_steamgriddb_id_sql(g, s) for g, s in specs})
    apply_sql("\n".join(statements))


def cmd_set_art_file(args):
    """Use local image files, for games SteamGridDB does not have."""
    files = dict(a.split("=", 1) for a in args.asset)
    unknown = set(files) - set(media.KINDS)
    if unknown or not files:
        raise SystemExit(f"--asset kinds must be {', '.join(media.KINDS)}; got {', '.join(unknown) or 'none'}")
    with tempfile.TemporaryDirectory() as tmp:
        con = db.open_snapshot(device.pull_snapshot(Path(tmp) / "snapshot"))
        row = db.game(con, args.game_id)
        statements = []
        for kind, local in files.items():
            folder = media.KINDS[kind]
            current = art_target(con, row, kind, folder)
            name =media.edit_filename(row["fileName"], args.game_id, Path(local).suffix.lstrip(".").lower())
            uri, path = media.sibling(current, name)
            print(f"{row['fileName']}: {kind} <- {local} -> {path}")
            device.push_media(Path(local), path)
            statements.append(db.set_media_sql(args.game_id, kind, uri))
    apply_sql("\n".join(statements))


def apply_sql(sql):
    backup = device.execute(sql, time.strftime("%Y%m%d-%H%M%S"))
    print(f"device backup: {backup}")
    print(f"Cocoon restarted (pid {device.restart_cocoon()})")


def cmd_sql(args):
    if args.write:
        apply_sql(args.statement)
    else:
        sys.stdout.write(device.query(args.statement))


def cmd_rename(args):
    apply_sql(db.rename_sql(args.game_id, args.name))


def cmd_sync_install(_):
    sync.install()
    pid, _ = sync.status()
    if not pid:
        raise RuntimeError("watcher did not start; see sync-status")
    print(f"installed to {sync.HOME}; watcher running (pid {pid})")


def cmd_sync_status(_):
    pid, log = sync.status()
    print(f"watcher: {'running (pid ' + pid + ')' if pid else 'NOT running'}")
    sys.stdout.write(log)


def cmd_sync(args):
    sys.stdout.write(sync.run(*args.args))


def cmd_art_dupes(_):
    out = device.adb("shell", "cd /sdcard/Cocoon/downloaded_media && "
                              "md5sum */icon/* 2>/dev/null").decode()
    groups = {}
    for line in out.splitlines():
        digest, path = line.split(None, 1)
        groups.setdefault(digest, []).append(path)
    for paths in sorted(groups.values(), key=len, reverse=True):
        if len(paths) > 1:
            print(" | ".join(paths))


def cmd_settings_find(args):
    catalog = settings.load_catalog(strict=False)
    live = settings.live_values(settings.read_files())
    hits = settings.find(" ".join(args.text), catalog, live)[:args.limit]
    if not hits:
        raise SystemExit("nothing matches; try `settings watch` while changing it by hand")
    for _, kind, item in hits:
        if kind == "page":
            sub = f" > {item['subsection']}" if item["subsection"] else ""
            where = f"{item['tab']}:{item['card']}" if item["card"] is not None else f"tab {item['tab']}, scroll"
            print(f"page  {item['section']}{sub} > {item['label']}  ({where})")
        else:
            print("key   " + settings.describe_key(item, catalog, live, args.reveal))


def cmd_settings_get(args):
    catalog = settings.load_catalog(strict=False)
    live = settings.live_values(settings.read_files())
    pats = args.keys or ["*"]
    keys = sorted(k for k in set(live) | (set(catalog["keys"]) if args.all else set())
                  if any(fnmatch.fnmatch(k, p) for p in pats))
    if args.file:
        keys = [k for k in keys if any(h[0] == args.file for h in live.get(k, []))]
    for k in keys:
        print(settings.describe_key(k, catalog, live, args.reveal))


def cmd_settings_set(args):
    catalog = settings.load_catalog()
    files = settings.read_files()
    texts, changes = settings.plan(args.assignments, args.unset, files, catalog)
    for stem, _, _, _, (label, old, new) in changes:
        print(f"{stem}:{label}: {prefs.show(label, old)} -> {prefs.show(label, new)}")
    if args.dry_run:
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = SNAPSHOTS / f"prefs-{stamp}"
    backup.mkdir(parents=True)
    for stem in texts:
        if stem in files:
            (backup / f"{stem}.xml").write_bytes(files[stem])
    pid = settings.apply(texts, files)
    bad = settings.verify(changes)
    if bad:
        raise SystemExit("NOT applied:\n" + "\n".join(bad) + f"\nold files: {backup}")
    print(f"applied; Cocoon restarted (pid {pid}); old files in {backup}")


def cmd_settings_watch(args):
    before = settings.read_files()
    print(f"watching Cocoon prefs for {args.seconds}s; change settings on the device now")
    end = time.monotonic() + args.seconds
    while time.monotonic() < end:
        time.sleep(1.5)
        now = settings.read_files()
        for line in settings.diff_text(before, now):
            print(line, flush=True)
        before = now


def cmd_settings_pages(_):
    catalog = settings.load_catalog(strict=False)
    for e in catalog["search_index"]["entries"]:
        sub = f" > {e['subsection']}" if e["subsection"] else ""
        print(f"{e['tab']}:{e['card']}\t{e['section']}{sub} > {e['label']}")
    print("activities: " + ", ".join(catalog["activities"]))


def cmd_settings_open(args):
    catalog = settings.load_catalog(strict=False)
    page = settings.resolve_page(" ".join(args.target), catalog)
    settings.open_page(page)
    print(f"opened {page.get('label') or page.get('activity') or page}")
    if page.get("tab") is not None and page.get("card") is None:
        print("this card's position is decided at runtime: opened its tab; scroll to it")


def cmd_restart(_):
    print(f"Cocoon restarted (pid {device.restart_cocoon()})")


def cmd_shot(args):
    out = Path(args.dir)
    out.mkdir(parents=True, exist_ok=True)
    ids = re.findall(r"Display (\d+) ", device.adb("shell", "dumpsys SurfaceFlinger --display-id").decode())
    names = ["top", "bottom"]
    for name, pid in zip(names, ids):
        path = out / f"{time.strftime('%H%M%S')}-{name}.png"
        path.write_bytes(device.adb("exec-out", f"screencap -p -d {pid}"))
        print(path)


def ui_client():
    device.adb("shell", "input keyevent KEYCODE_WAKEUP")
    return ui.connect()


def cmd_ui_tree(args):
    nodes = ui_client().tree(ui.display_id(args.display))
    seen = set()
    for n in nodes:
        sig = (n["d"], ui.label(n), tuple(n["b"]))
        if sig in seen and not args.all:
            continue
        seen.add(sig)
        if args.all or ui.label(n) or n.get("editable") or "checked" in n:
            print("  " * min(n["depth"], 12) * args.indent + ui.fmt(n))


def cmd_ui_click(args):
    """A whole-label match wins over a substring one, so 'UPDATE' does not hit
    'Do you want to update this app?'."""
    c, d = ui_client(), ui.display_id(args.display)
    exact = args.exact or any(ui.label(n) == args.text for n in c.tree(display=d))
    r = c.call("click", text=args.text, display=d, index=args.index, exact=exact or None, tap=args.tap or None)
    print(f"clicked {r['node']['text']!r} via {r['via']}")


def cmd_ui_type(args):
    """Type into an app's own drawn keyboard.

    Cocoon's keyboard has a Paste button: set the clipboard and press it.
    Others (ARMSX2) expose each key as a labelled button: press them in turn."""
    c = ui_client()
    nodes = c.tree()
    if any(ui.label(n) == "Paste" for n in nodes):
        c.call("clip", value=args.text)
        c.call("click", text="Paste", exact=True)
        print(f"pasted {args.text!r}")
        return
    keys = {ui.label(n) for n in nodes if len(ui.label(n)) == 1}
    missing = sorted({ch for ch in args.text if ch not in keys and ch.lower() not in keys and ch != " "})
    if missing or len(keys) < 20:
        raise SystemExit("no on-screen keyboard with these keys is showing "
                         f"(missing {missing or 'a keyboard'}); open the text box first, or use `ui settext` "
                         "for a standard Android text field")
    for ch in args.text:
        label = "Space" if ch == " " else (ch if ch in keys else ch.lower())
        c.call("click", text=label, exact=True)
        time.sleep(0.05)
    print(f"typed {args.text!r} on the on-screen keyboard")


def cmd_ui_clip(args):
    ui_client().call("clip", value=args.text)
    print("clipboard set")


def cmd_ui_settext(args):
    r = ui_client().call("settext", value=args.value, text=args.field,
                         display=ui.display_id(args.display))
    print(f"set text in {r['node']}")


def cmd_ui_pad(args):
    r = ui_client().call("pad", buttons=args.buttons, hold_ms=args.hold, gap_ms=args.gap)
    print(f"pressed {' '.join(args.buttons)} on {r['pad']}")


def cmd_ui_tap(args):
    ui_client().call("tap", x=args.x, y=args.y, display=ui.display_id(args.display) or 0)


def cmd_ui_swipe(args):
    ui_client().call("swipe", x1=args.x1, y1=args.y1, x2=args.x2, y2=args.y2, ms=args.ms,
                     display=ui.display_id(args.display) or 0)


def cmd_ui_key(args):
    code = ui.KEYS.get(args.name.lower()) or int(args.name)
    ui_client().call("key", code=code, display=ui.display_id(args.display) or 0)


def cmd_ui_wait(args):
    hits = ui_client().wait_for(args.text, ui.display_id(args.display), args.timeout, args.gone)
    for n in hits:
        print(ui.fmt(n))


# Item menus: folders/games show Open + Edit, Android apps Launch + Edit + more.
MENU_WORDS = {"open", "launch", "edit", "app info", "hide", "unhide", "favorite", "unfavorite",
              "remove", "y", "x", "a", "b", "rb", "lb", "select", "r1", "l1"}


def focused_name(c):
    """Press Y (item menu), read the item's name from it, press B to close."""
    before = {ui.label(n) for n in c.tree(4)}
    c.call("pad", buttons=["Y"])
    try:
        c.wait_for("Edit", display=4, timeout=3)
    except TimeoutError:
        raise SystemExit("Y opened no item menu: nothing on the grid has focus")
    names = [ui.label(n) for n in c.tree(4)
             if ui.label(n) and ui.label(n).lower() not in MENU_WORDS and ui.label(n) not in before
             and not re.fullmatch(r"\d{1,2}:\d{2}( [AP]M)?", ui.label(n))]
    c.call("pad", buttons=["B"])
    c.wait_for("Edit", display=4, timeout=3, gone=True)
    return names[0] if names else None


def cmd_ui_focused(_):
    print(focused_name(ui_client()) or "(item has no name)")


def grid_items(screen, zoom):
    rows = device.query(
        "SELECT p.itemType, p.itemId, p.col, p.row, p.colSpan, p.rowSpan, "
        "COALESCE(f.name, NULLIF(g.title, ''), g.displayName, '') FROM grid_placement p "
        "LEFT JOIN folders f ON p.itemType='FOLDER' AND f.id=p.itemId "
        "LEFT JOIN games g ON p.itemType='GAME' AND g.id=p.itemId "
        f"WHERE p.screenType={db.literal(screen)} AND p.zoomLevel={int(zoom)};").splitlines()
    items = []
    for line in rows[1:]:
        kind, iid, col, row, cs, rs, name = line.split("\t")
        items.append(dict(kind=kind, id=int(iid), col=int(col), row=int(row),
                          span=(int(cs), int(rs)), name=name, screen=screen))
    return items


def grid_screens():
    """{screen: items} for home and every manual folder whose stored layout
    matches the zoom level it is shown at (other layouts are stale)."""
    live = settings.live_values(settings.read_files())
    zoom = lambda key, default: live.get(key, [(None, None, default)])[0][2]
    out = {"home": grid_items("home", zoom("home_zoom_level", 4))}
    for line in device.query("SELECT DISTINCT screenType FROM grid_placement "
                             "WHERE screenType LIKE 'folder_%';").splitlines()[1:]:
        fid = line.split("_", 1)[1]
        items = grid_items(line, zoom(f"folder_zoom_{fid}", -1))
        if items:
            out[line] = items
    return out


def walk_to(c, items, it, gap):
    if any(i["span"] != (1, 1) for i in items):
        raise SystemExit(f"{it['screen']} has multi-cell tiles; D-pad counting would be wrong")
    maxcol = max(i["col"] for i in items)
    maxrow = max(i["row"] for i in items)
    # Anchor: left and up out of the grid (dock or folder header), far left, down = row 0, col 0.
    path = ["LEFT"] * (maxcol + 2) + ["UP"] * (maxrow + 2) + ["LEFT"] * 10 + ["DOWN"]
    path += ["RIGHT"] * it["col"] + ["DOWN"] * it["row"]
    c.call("pad", buttons=path, hold_ms=40, gap_ms=gap)
    got = focused_name(c)
    if (got or "").lower() != it["name"].lower():
        raise SystemExit(f"focus landed on {got!r}, expected {it['name']!r}; nothing opened")
    print(f"focused {got!r} ({it['screen']} row {it['row']}, col {it['col']})")


def cmd_ui_home(args):
    screens = grid_screens()
    if args.list:
        for screen, items in screens.items():
            for it in sorted(items, key=lambda i: (i["row"], i["col"])):
                print(f"{screen}\trow {it['row']} col {it['col']}\t{it['kind']} {it['id']}\t{it['name']}")
        return
    want = args.name.lower()
    every = [i for items in screens.values() for i in items]
    hits = [i for i in every if i["name"].lower() == want] or [i for i in every if want in i["name"].lower()]
    if len(hits) != 1:
        raise SystemExit(f"{len(hits)} grid items match {args.name!r}: {[h['name'] for h in hits]} "
                         "(games inside smart/platform folders are not placed; open the folder and use pad + focused)")
    it = hits[0]
    c = ui_client()
    c.call("pad", buttons=["B", "B", "B"], gap_ms=200)  # close menus and open folders
    if it["screen"] != "home":
        fid = int(it["screen"].split("_", 1)[1])
        folder = [i for i in screens["home"] if i["kind"] == "FOLDER" and i["id"] == fid]
        if not folder:
            raise SystemExit(f"{it['name']} is in folder {fid}, which is not on the home grid")
        walk_to(c, screens["home"], folder[0], args.gap)
        c.call("pad", buttons=["A"])
        time.sleep(0.8)
    walk_to(c, screens[it["screen"]], it, args.gap)
    if args.open:
        c.call("pad", buttons=["A"])
        print("opened")


def _find(c, text, display=None):
    return [n for n in c.tree(display) if ui.label(n) == text]


def _click_scrolling(c, text, display, tries=12):
    """Click an exact label in a scrolling list, swiping up until it shows."""
    for _ in range(tries):
        if _find(c, text, display):
            c.call("click", text=text, exact=True, display=display)
            return
        c.call("swipe", x1=960, y1=900, x2=960, y2=450, ms=250, display=display)
        time.sleep(0.6)
    raise SystemExit(f"{text!r} not found in the picker")


def cmd_ui_pick(args):
    """Drive Android's file picker (DocumentsUI) to a device path."""
    c = ui_client()
    d = ui.display_id(args.display) if args.display else 0
    path = args.path.rstrip("/")
    if path.startswith(("/sdcard/", "/storage/emulated/0/")):
        rel = path.split("/sdcard/", 1)[-1] if path.startswith("/sdcard/") else path.split("/emulated/0/", 1)[1]
        model = device.adb("shell", "getprop ro.product.model").decode().strip()
        root = model
    elif path.startswith("/storage/"):
        rel = path.split("/", 3)[3]
        root = None
    else:
        raise SystemExit("path must be under /sdcard or /storage/<volume>")
    c.wait_for("Show roots", display=d, timeout=10)
    c.call("click", text="Show roots", exact=True, display=d)
    # The drawer fills in after its animation; the root may sit below the fold.
    target = "Eject" if root is None else root
    for attempt in range(4):
        try:
            c.wait_for(target, display=d, timeout=3 if attempt else 5)
            break
        except TimeoutError:
            c.call("swipe", x1=300, y1=950, x2=300, y2=350, ms=300, display=d)
    else:
        raise SystemExit(f"{target!r} is not in the picker's drawer")
    time.sleep(0.4)
    if root is None:  # the SD card is the root listed with an Eject button
        nodes = c.tree(d)
        eject = [n for n in nodes if ui.label(n) == "Eject"]
        if not eject:
            raise SystemExit("no removable volume in the picker")
        ey = (eject[0]["b"][1] + eject[0]["b"][3]) // 2
        row = [n for n in nodes if ui.label(n) and ui.label(n) != "Eject" and abs((n["b"][1] + n["b"][3]) // 2 - ey) < 30]
        root = ui.label(row[0])
    c.call("click", text=root, exact=True, display=d)
    time.sleep(1.5)
    parts = rel.split("/")
    for i, part in enumerate(parts):
        _click_scrolling(c, part, d)
        time.sleep(1.5)
    if args.folder:
        for label in ("USE THIS FOLDER", "Use this folder"):
            if _find(c, label, d):
                c.call("click", text=label, exact=True, display=d)
                break
        time.sleep(1.2)
        for label in ("ALLOW", "Allow"):
            if _find(c, label, d):
                c.call("click", text=label, exact=True, display=d)
                break
    print(f"picked {args.path}")


def cmd_ui_stop(_):
    device.adb("forward", f"tcp:{ui.PORT}", "localabstract:cocoon-ui")
    c = ui._try(ui.PORT)
    if c:
        c.call("quit")
    print("cocoon-ui stopped" if c else "cocoon-ui was not running")


def cmd_app_list(_):
    for name, a in apps.adapters().items():
        v = apps.installed_version(a["package"])
        status = f"installed {v}" if v else "NOT installed"
        checked = a.get("version_checked", "?")
        warn = "" if not v or v == checked else f"  (adapter checked against {checked})"
        print(f"{name:10} {a['package']:34} {status}{warn}  aliases: {', '.join(a.get('aliases', []))}")


def cmd_app_coverage(args):
    rows = discover.coverage()
    for r in rows:
        flag = "NEW " if r["new"] else "    "
        cat = " catalog" if r["catalog"] else ""
        print(f"{flag}{r['state']:8} {r['package']:48} {r['adapter'] or '-':16} {r['why']}{cat}")
    gaps = [r for r in rows if r["state"] not in ("covered", "no-settings")]
    print(f"{len(rows)} apps; {len(rows) - len(gaps)} covered (or catalogued with no settings file), "
          f"{len(gaps)} missing or draft")
    for r in gaps:
        if r["state"] == "missing":
            print(f"  next: thorctl app discover {r['package']}")
    if args.mark_seen:
        discover.mark_seen(r["package"] for r in rows)


def cmd_recomps(args):
    if args.action == "build":
        n = recomps.build()
        print(f"built {recomps.ROOT / 'CATALOG.md'} ({n} recomps)"
              + (f" and {recomps.LOCAL / 'CATALOG.md'} (with local/recomps)" if recomps.has_local() else ""))
        return
    es = recomps.find(" ".join(args.words)) if args.words else recomps.entries()
    if args.action == "show":
        for e in es:
            print(json.dumps({k: v for k, v in e.items() if k != "_file"}, indent=1))
        return
    for e in es:
        o = e.get("original") or {}
        adapter = (e.get("settings") or {}).get("adapter") or "-"
        print(f"{(e.get('name') or e['package'])[:34]:34} {(o.get('title') or '?')[:30]:30} {o.get('platform') or '?':10} "
              f"{e.get('version_installed') or e.get('version_checked') or '?':12} settings: {adapter}")


def cmd_app_autodiscover(args):
    report = discover.autodiscover(args.dry_run)
    print("\n".join(report) or "no new emulators or recomps")
    drafted = [l for l in report if l.startswith("drafted")]
    if drafted and args.notify and not args.dry_run:
        msg = f"{len(drafted)} new app(s) on the Thor drafted; ask an agent to finish them (see local/apps/*.md)"
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "thorctl"'], check=False)


def cmd_app_discover(args):
    out, brief, adapter, skipped = discover.discover(args.package, args.name)
    print(f"drafted {out} ({len(adapter['files'])} files, {len(adapter['keys'])} keys); skipped {len(skipped)} files")
    for f in adapter["files"].values():
        print(f"  {f['format']:6} {f['path']}  ({f['notes']})")
    if adapter["source_hints"]:
        print("source hints: " + ", ".join(adapter["source_hints"][:5]))
    print(f"research brief: {brief}  (hand it to an agent to fill labels, values and defaults)")
    discover.mark_seen([args.package])


def cmd_app_keys(args):
    app = apps.resolve(args.app)
    for k in apps.glob_keys(app, args.words):
        e = app["keys"][k]
        vals = ", ".join(f"{r}={m}" for r, m in (e.get("values") or {}).items())
        game = " per-game" if e.get("per_game") else ""
        label = e.get("label") or "(not researched)"
        extra = f"default={e.get('default')}" if e.get("default") is not None else f"current={e.get('current')}"
        print(f"{k:28} {label!r:42} {e['file']}:{e['key']}  {extra}{game}")
        if vals:
            print(f"{'':28} values: {vals[:300]}")


def cmd_app_get(args):
    app = apps.resolve(args.app)
    cache = {}

    def value(spec, key):
        if spec["path"] not in cache:
            text = apps.read_file(spec["path"])
            cache[spec["path"]] = None if text is None else appconf.read(spec["format"], text)
        vals = cache[spec["path"]]
        return "(file missing)" if vals is None else vals.get(key)

    if args.all or app.get("bare"):
        specs = ([apps.file_spec(app, "game", args.game)] if args.game and app.get("per_game")
                 else [apps.file_spec(app, f) for f in app["files"]] + [apps.file_spec(app, f) for f in args.file])
        for spec in specs:
            text = apps.read_file(spec["path"])
            print(f"== {spec['path']}" + ("  (missing)" if text is None else ""))
            for k, v in (appconf.read(spec["format"], text) if text else {}).items():
                if not args.words or any(w.lower() in k.lower() for w in args.words):
                    print(f"  {k} = {prefs.show(k, v)}")
        return
    for k in apps.glob_keys(app, args.words):
        e = app["keys"][k]
        try:
            spec, key, _ = apps.resolve_key(app, k, args.game)
        except SystemExit as err:
            print(f"{k:28} -- {err}")
            continue
        raw = value(spec, key)
        shown = apps.describe(e, raw)
        if args.game and (raw is None or raw == "(global)" or raw == "(file missing)"):
            gspec, gkey, _ = apps.resolve_key(app, k)
            shown = f"global: {apps.describe(e, value(gspec, gkey))}"
        print(f"{k:28} {shown:34} {e.get('label') or ''}")


def cmd_app_set(args):
    app = apps.resolve(args.app)
    pairs = []
    for a in args.assignments:
        if "=" not in a:
            raise SystemExit(f"expected KEY=VALUE, got {a!r}")
        pairs.append(tuple(a.split("=", 1)))
    texts, originals, changes = apps.plan_set(app, pairs, args.unset, args.game)
    for c in changes:
        print(f"{c['name']}: {apps.describe(c['entry'], c['before'])} -> {apps.describe(c['entry'], c['after'])}"
              f"   [{c['path']} {c['key']}]")
    if args.dry_run:
        return
    if app.get("stop_before_write", True):
        apps.ensure_stopped(app["package"], args.stop)
    saved = apps.backup(app, originals)
    apps.write_files(app["package"], texts, originals)
    bad = apps.verify(changes)
    if bad:
        raise SystemExit("NOT applied:\n" + "\n".join(bad) + f"\nold files: {saved}")
    print(f"applied and read back; old files in {saved}")


def cmd_app_restore(args):
    app = apps.resolve(args.app)
    for path in apps.restore(app, args.backup, args.stop):
        print(f"restored {path}")


def cmd_app_unset(args):
    args.unset, args.assignments = args.keys, []
    cmd_app_set(args)


def cmd_app_games(args):
    app = apps.resolve(args.app)
    pg = app.get("per_game")
    if not pg:
        raise SystemExit(f"{app['name']} has no per-game settings in its adapter")
    pattern = apps.expand(pg["path"])
    if "{game}" not in Path(pattern).name:
        print(f"per-game settings live inside {pattern}; see `app keys {app['name']}` ({pg.get('game_id', '')})")
        return
    folder = str(Path(pattern).parent)
    glob = Path(pattern).name.replace("{game}", "*")
    print(device.root(f"cd {shlex.quote(folder)} 2>/dev/null && ls -1 {glob} 2>/dev/null; true").strip()
          or "(none yet)")
    print(f"id: {pg.get('game_id', '')}")


def cmd_app_watch(args):
    app = apps.resolve(args.app)
    roots = apps.watch_roots(app)
    hashes = apps.snapshot_hashes(app)
    contents = apps.read_many(sorted(hashes))
    print(f"watching {len(hashes)} config files under {', '.join(roots)} for {args.seconds}s; "
          "change settings in the app now", flush=True)
    end = time.monotonic() + args.seconds
    while time.monotonic() < end:
        time.sleep(1.0)
        now = apps.snapshot_hashes(app)
        changed = sorted(p for p in set(hashes) | set(now) if hashes.get(p) != now.get(p))
        fresh = apps.read_many([p for p in changed if p in now])
        for path in changed:
            if path not in now:
                print(f"deleted {path}", flush=True)
                contents.pop(path, None)
                continue
            if path not in hashes:
                print(f"new file {path}", flush=True)
            for line in apps.diff_lines(path, contents.get(path, ""), fresh.get(path, "")):
                print(line, flush=True)
            contents[path] = fresh.get(path, "")
        hashes = now


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot").set_defaults(fn=cmd_snapshot)
    g = sub.add_parser("games")
    g.add_argument("-m", "--match")
    g.add_argument("-p", "--platform")
    g.set_defaults(fn=cmd_games)
    s = sub.add_parser("sgdb-search")
    s.add_argument("term")
    s.set_defaults(fn=cmd_sgdb_search)
    a = sub.add_parser("set-art")
    a.add_argument("specs", nargs="+", metavar="GAME_ID=SGDB_ID")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--asset", action="append", default=[], metavar="KIND=ID",
                   help="use this SteamGridDB asset for boxArt, logo or hero")
    a.set_defaults(fn=cmd_set_art)
    f = sub.add_parser("set-art-file")
    f.add_argument("game_id", type=int)
    f.add_argument("--asset", action="append", default=[], metavar="KIND=PATH",
                   help="local image for boxArt, logo or hero")
    f.set_defaults(fn=cmd_set_art_file)
    sub.add_parser("art-dupes").set_defaults(fn=cmd_art_dupes)
    r = sub.add_parser("rename")
    r.add_argument("game_id", type=int)
    r.add_argument("name")
    r.set_defaults(fn=cmd_rename)
    sub.add_parser("sync-install").set_defaults(fn=cmd_sync_install)
    sub.add_parser("sync-status").set_defaults(fn=cmd_sync_status)
    y = sub.add_parser("sync")
    y.add_argument("args", nargs=argparse.REMAINDER)
    y.set_defaults(fn=cmd_sync)
    q = sub.add_parser("sql")
    q.add_argument("statement")
    q.add_argument("--write", action="store_true")
    q.set_defaults(fn=cmd_sql)
    st = sub.add_parser("settings").add_subparsers(dest="settings_cmd", required=True)
    x = st.add_parser("find")
    x.add_argument("text", nargs="+")
    x.add_argument("--limit", type=int, default=15)
    x.add_argument("--reveal", action="store_true", help="show secret values")
    x.set_defaults(fn=cmd_settings_find)
    x = st.add_parser("get")
    x.add_argument("keys", nargs="*", metavar="KEY_OR_GLOB")
    x.add_argument("--file", help="only keys in this prefs file, e.g. cocoon_settings")
    x.add_argument("--all", action="store_true", help="include catalog keys not set on the device")
    x.add_argument("--reveal", action="store_true", help="show secret values")
    x.set_defaults(fn=cmd_settings_get)
    x = st.add_parser("set")
    x.add_argument("assignments", nargs="*", metavar="[FILE:]KEY=VALUE")
    x.add_argument("--unset", action="append", default=[], metavar="[FILE:]KEY")
    x.add_argument("--dry-run", action="store_true")
    x.set_defaults(fn=cmd_settings_set)
    x = st.add_parser("watch")
    x.add_argument("--seconds", type=int, default=90)
    x.set_defaults(fn=cmd_settings_watch)
    st.add_parser("pages").set_defaults(fn=cmd_settings_pages)
    x = st.add_parser("open")
    x.add_argument("target", nargs="+")
    x.set_defaults(fn=cmd_settings_open)
    sub.add_parser("restart").set_defaults(fn=cmd_restart)
    u = sub.add_parser("ui").add_subparsers(dest="ui_cmd", required=True)
    x = u.add_parser("tree")
    x.add_argument("-d", "--display")
    x.add_argument("--all", action="store_true", help="include unlabelled nodes")
    x.add_argument("--indent", type=int, default=0, choices=(0, 1))
    x.set_defaults(fn=cmd_ui_tree)
    x = u.add_parser("click")
    x.add_argument("text")
    x.add_argument("-d", "--display")
    x.add_argument("--index", type=int, default=0, help="which match, when several")
    x.add_argument("--exact", action="store_true")
    x.add_argument("--tap", action="store_true", help="tap its centre instead of ACTION_CLICK")
    x.set_defaults(fn=cmd_ui_click)
    x = u.add_parser("settext")
    x.add_argument("value")
    x.add_argument("--field", help="label of the field (default: first editable)")
    x.add_argument("-d", "--display")
    x.set_defaults(fn=cmd_ui_settext)
    x = u.add_parser("type", help="type into Cocoon's own keyboard (clipboard + Paste)")
    x.add_argument("text")
    x.set_defaults(fn=cmd_ui_type)
    x = u.add_parser("clip", help="set the device clipboard")
    x.add_argument("text")
    x.set_defaults(fn=cmd_ui_clip)
    x = u.add_parser("pad")
    x.add_argument("buttons", nargs="+")
    x.add_argument("--hold", type=int, default=60, help="ms each press is held")
    x.add_argument("--gap", type=int, default=150, help="ms between presses")
    x.set_defaults(fn=cmd_ui_pad)
    x = u.add_parser("tap")
    x.add_argument("x", type=int)
    x.add_argument("y", type=int)
    x.add_argument("-d", "--display")
    x.set_defaults(fn=cmd_ui_tap)
    x = u.add_parser("swipe")
    for a in ("x1", "y1", "x2", "y2"):
        x.add_argument(a, type=int)
    x.add_argument("--ms", type=int, default=300)
    x.add_argument("-d", "--display")
    x.set_defaults(fn=cmd_ui_swipe)
    x = u.add_parser("key")
    x.add_argument("name", help=", ".join(ui.KEYS) + " or a keycode")
    x.add_argument("-d", "--display")
    x.set_defaults(fn=cmd_ui_key)
    x = u.add_parser("wait")
    x.add_argument("text")
    x.add_argument("-d", "--display")
    x.add_argument("--timeout", type=float, default=10)
    x.add_argument("--gone", action="store_true", help="wait until it disappears")
    x.set_defaults(fn=cmd_ui_wait)
    u.add_parser("stop").set_defaults(fn=cmd_ui_stop)
    x = u.add_parser("pick", help="choose a file or folder in Android's file picker")
    x.add_argument("path", help="/sdcard/... or /storage/<volume>/...")
    x.add_argument("--folder", action="store_true", help="folder picker: press Use this folder + Allow")
    x.add_argument("-d", "--display")
    x.set_defaults(fn=cmd_ui_pick)
    u.add_parser("focused", help="name of the focused grid item (via its Y menu)").set_defaults(fn=cmd_ui_focused)
    x = u.add_parser("home", help="move focus to a home-grid item by name, verify it, optionally open")
    x.add_argument("name", nargs="?")
    x.add_argument("--open", action="store_true")
    x.add_argument("--list", action="store_true", help="list home grid items and positions")
    x.add_argument("--gap", type=int, default=50)
    x.set_defaults(fn=cmd_ui_home)
    x = sub.add_parser("shot")
    x.add_argument("dir", nargs="?", default="/tmp/cocoon-shots")
    x.set_defaults(fn=cmd_shot)
    x = sub.add_parser("recomps", help="the recomp catalog (recomps/CATALOG.md)")
    x.add_argument("action", choices=("list", "show", "build"), nargs="?", default="list")
    x.add_argument("words", nargs="*")
    x.set_defaults(fn=cmd_recomps)
    ap = sub.add_parser("app", help="settings of emulators and any app").add_subparsers(dest="app_cmd", required=True)
    ap.add_parser("list").set_defaults(fn=cmd_app_list)
    x = ap.add_parser("coverage", help="installed emulators/recomps with and without adapters")
    x.add_argument("--mark-seen", action="store_true", help="stop flagging the listed apps as NEW")
    x.set_defaults(fn=cmd_app_coverage)
    x = ap.add_parser("autodiscover", help="discover every NEW uncovered app (run daily by launchd)")
    x.add_argument("--dry-run", action="store_true")
    x.add_argument("--notify", action="store_true", help="macOS notification when something was drafted")
    x.set_defaults(fn=cmd_app_autodiscover)
    x = ap.add_parser("discover", help="draft an adapter for an app from its files on the device")
    x.add_argument("package")
    x.add_argument("--name")
    x.set_defaults(fn=cmd_app_discover)
    for name, fn in (("keys", cmd_app_keys), ("get", cmd_app_get)):
        x = ap.add_parser(name)
        x.add_argument("app")
        x.add_argument("words", nargs="*")
        if name == "get":
            x.add_argument("--game")
            x.add_argument("--all", action="store_true", help="every key in the app's files, not just the glossary")
            x.add_argument("--file", action="append", default=[], help="also read this device file (with --all)")
        x.set_defaults(fn=fn)
    x = ap.add_parser("set")
    x.add_argument("app")
    x.add_argument("assignments", nargs="*", metavar="KEY=VALUE")
    x.add_argument("--unset", action="append", default=[], metavar="KEY")
    x.add_argument("--game")
    x.add_argument("--stop", action="store_true", help="force-stop the app first if running")
    x.add_argument("--dry-run", action="store_true")
    x.set_defaults(fn=cmd_app_set)
    x = ap.add_parser("unset")
    x.add_argument("app")
    x.add_argument("keys", nargs="+")
    x.add_argument("--game")
    x.add_argument("--stop", action="store_true")
    x.add_argument("--dry-run", action="store_true")
    x.set_defaults(fn=cmd_app_unset)
    x = ap.add_parser("restore", help="put back the files saved by an earlier write")
    x.add_argument("app")
    x.add_argument("backup", help="snapshots/apps/<app>-<time> folder printed by set")
    x.add_argument("--stop", action="store_true")
    x.set_defaults(fn=cmd_app_restore)
    x = ap.add_parser("games")
    x.add_argument("app")
    x.set_defaults(fn=cmd_app_games)
    x = ap.add_parser("watch")
    x.add_argument("app")
    x.add_argument("--seconds", type=int, default=90)
    x.set_defaults(fn=cmd_app_watch)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
