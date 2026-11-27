"""Installs and drives the on-device cocoon-sync watcher (device/cocoon-sync)."""
import shlex
import time
from pathlib import Path

from cocoonlib import device

SOURCE = Path(__file__).resolve().parent.parent / "device" / "cocoon-sync"
# Your own modes.conf (not committed); used instead of the example in SOURCE when present.
LOCAL_MODES = Path(__file__).resolve().parent.parent / "local" / "cocoon-sync" / "modes.conf"
HOME = "/data/adb/cocoon-sync"
BOOT_SCRIPT = "/data/adb/service.d/cocoon-sync.sh"
# Kept across reinstalls: the user's edits, the log and the watcher's pid.
KEEP = ("modes.conf", "sync.log", "sync.log.1", "watch.pid")


def run(*args):
    cmd = " ".join(shlex.quote(a) for a in args)
    return device.root(f"sh {HOME}/cocoon-sync.sh {cmd}")


def install(start=True):
    device.ensure_sqlite()
    stage = f"/data/local/tmp/cocoon-sync-{time.strftime('%Y%m%d%H%M%S')}"
    device.adb("push", str(SOURCE), stage)
    if LOCAL_MODES.is_file():
        device.adb("push", str(LOCAL_MODES), f"{stage}/modes.conf")
    keep = " ".join(KEEP)
    device.root(
        f"if [ -d {HOME} ]; then sh {HOME}/cocoon-sync.sh stop; fi; "
        f"mkdir -p {HOME}/bin && "
        f"for f in lib tests cocoon-sync.sh service.sh; do rm -r {HOME}/$f 2>/dev/null; cp -r {stage}/$f {HOME}/; done && "
        f"for f in {keep}; do [ -e {HOME}/$f ] || [ ! -e {stage}/$f ] || cp {stage}/$f {HOME}/; done && "
        f"cp {device.SQLITE} {HOME}/bin/sqlite3 && chmod 755 {HOME}/bin/sqlite3 && "
        f"cp {HOME}/service.sh {BOOT_SCRIPT} && chmod 755 {BOOT_SCRIPT} && "
        f"rm -r {stage}")
    if start:
        device.root(f"sh {BOOT_SCRIPT}")


def status():
    pid = device.root(f"cat {HOME}/watch.pid 2>/dev/null || true").strip()
    alive = bool(pid) and device.root(f"[ -d /proc/{pid} ] && echo yes || true").strip() == "yes"
    log = device.root(f"tail -n 20 {HOME}/sync.log 2>/dev/null || true")
    return pid if alive else None, log
