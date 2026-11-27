"""adb access to Cocoon's private data on a rooted device.

Every root command goes through `root()` as one quoted string, so `su -c`
never splits arguments.

Cocoon is the home app, so Android respawns it within ~200 ms of a
force-stop and the database can never be edited while it is down. Edits
therefore go through a static sqlite3 binary on the device, which shares
SQLite's file locks with Cocoon's own connection. Cocoon is restarted
afterwards so Room drops anything it cached.
"""
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

PACKAGE = "rip.moth.cocoonshell"
DATA_DIR = f"/data/data/{PACKAGE}"
DB_PATH = f"{DATA_DIR}/databases/cocoon_db"
PREFS_DIR = f"{DATA_DIR}/shared_prefs"
STAGING = "/data/local/tmp/cocoonctl"
SQLITE = "/data/local/tmp/cocoonctl-sqlite3"
LOCAL_SQLITE = Path(__file__).resolve().parent.parent / "device-bin" / "sqlite3"


def adb(*args, input_bytes=None):
    return subprocess.run(["adb", *args], check=True, capture_output=True,
                          input=input_bytes).stdout


_SDCARD = []


def sdcard():
    """The SD card's volume id (the 1234-ABCD in /storage/1234-ABCD):
    $THOR_SDCARD, else the first such entry in the device's /storage."""
    if not _SDCARD:
        vol = os.environ.get("THOR_SDCARD")
        if not vol:
            names = adb("shell", "ls /storage").decode().split()
            vols = [n for n in names if re.fullmatch(r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}", n)]
            if not vols:
                raise RuntimeError(f"no SD card in /storage (found {names}); insert one or set THOR_SDCARD")
            vol = vols[0]
        _SDCARD.append(vol)
    return _SDCARD[0]


def root(cmd):
    r = subprocess.run(["adb", "shell", f"su -c {shlex.quote(cmd)}"],
                       capture_output=True)
    if r.returncode:
        raise RuntimeError(f"device command failed ({r.returncode}): {cmd}\n"
                           f"{(r.stdout + r.stderr).decode().strip()}")
    return r.stdout.decode()


def cocoon_pid():
    out = adb("shell", f"pidof {PACKAGE} || true").decode().strip()
    return out or None


def restart_cocoon(timeout_s=20.0):
    """Force-stop Cocoon and wait until its home is back on display 0.

    Android respawns only the secondary-display home by itself; without the
    explicit start, display 0 shows whatever app was behind Cocoon."""
    old = cocoon_pid()
    adb("shell", "input keyevent KEYCODE_WAKEUP")
    adb("shell", f"am force-stop {PACKAGE}")
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        pid = cocoon_pid()
        if pid and pid != old:
            top = adb("shell", "dumpsys activity activities | grep topResumedActivity").decode()
            if f"{PACKAGE}/.MainActivity" in top:
                return pid
        adb("shell", "am start --display 0 -a android.intent.action.MAIN "
                     "-c android.intent.category.HOME")
        time.sleep(0.5)
    raise RuntimeError("Cocoon did not come back on display 0 after a restart")


def pull_snapshot(dest: Path):
    """Copy a consistent database backup and the shared prefs into `dest`."""
    dest.mkdir(parents=True, exist_ok=True)
    ensure_sqlite()
    root(f"rm -rf {STAGING} && mkdir -p {STAGING} && "
         f"{SQLITE} {DB_PATH} '.timeout 5000' '.backup {STAGING}/cocoon_db' && "
         f"cp {PREFS_DIR}/*.xml {STAGING}/ && chmod 644 {STAGING}/*")
    for name in root(f"ls {STAGING}").split():
        adb("pull", f"{STAGING}/{name}", str(dest / name))
    root(f"rm -rf {STAGING}")
    return dest


def read_pref(name):
    return root(f"cat {PREFS_DIR}/{shlex.quote(name)}")


def push_media(local: Path, device_path: str):
    """Push a file to shared storage (FUSE assigns ownership itself)."""
    tmp = f"/data/local/tmp/{local.name}"
    adb("push", str(local), tmp)
    root(f"mkdir -p {shlex.quote(str(Path(device_path).parent))} && "
         f"cp {shlex.quote(tmp)} {shlex.quote(device_path)} && "
         f"rm {shlex.quote(tmp)}")


def ensure_sqlite():
    if root(f"[ -x {SQLITE} ] && echo ok || true").strip() == "ok":
        return
    if not LOCAL_SQLITE.exists():
        raise RuntimeError(f"{LOCAL_SQLITE} missing; run device-bin/build_sqlite3.sh")
    adb("push", str(LOCAL_SQLITE), SQLITE)
    adb("shell", f"chmod 755 {SQLITE}")


def query(sql):
    """Run read-only SQL against the live database; returns tab-separated text."""
    ensure_sqlite()
    return _run_sql_file(sql, "-readonly -header -separator '\t'")


def execute(sql, stamp):
    """Back up the live database, then run `sql` in one transaction.

    PERSIST_WAL stops sqlite3 from deleting Cocoon's -wal file (as root) if it
    happens to be the last connection to close.
    """
    ensure_sqlite()
    backup = f"/data/local/tmp/cocoon_db_backup_{stamp}"
    root(f"{SQLITE} {DB_PATH} '.timeout 5000' '.backup {backup}'")
    script = (".bail on\n.timeout 5000\n.filectrl persist_wal 1\n"
              f"BEGIN IMMEDIATE;\n{sql}\nCOMMIT;\n")
    _run_sql_file(script, "")
    return backup


def _run_sql_file(sql, flags):
    tmp = f"{STAGING}.sql"
    adb("shell", f"cat > {tmp}", input_bytes=sql.encode())
    try:
        return root(f"{SQLITE} {flags} {DB_PATH} < {tmp}")
    finally:
        adb("shell", f"rm -f {tmp}")
