"""Client for the on-device cocoon-ui agent (device/cocoon-ui).

The agent is an app_process server running as the adb shell user (no root)
on the abstract socket `cocoon-ui`.
`connect()` forwards it to a local TCP port, starts it (pushing the jar when
the local build differs from the device copy), and returns a Client.
"""
import hashlib
import json
import socket
import time
from pathlib import Path

from . import device

JAR = Path(__file__).resolve().parent.parent / "device" / "cocoon-ui" / "cocoon-ui.jar"
DEVICE_JAR = "/data/local/tmp/cocoon-ui.jar"
LOG = "/data/local/tmp/cocoon-ui.log"
PORT = 17120
DISPLAYS = {"top": 0, "bottom": 4}
KEYS = {"back": 4, "home": 3, "wakeup": 224, "sleep": 223, "enter": 66, "recents": 187,
        "up": 19, "down": 20, "left": 21, "right": 22, "center": 23}


def display_id(name):
    if name is None:
        return None
    return DISPLAYS.get(str(name).lower(), None) if not str(name).lstrip("-").isdigit() else int(name)


class Client:
    def __init__(self, sock):
        self.sock = sock
        self.f = sock.makefile("rw", encoding="utf-8")

    def call(self, cmd, **kw):
        kw = {k: v for k, v in kw.items() if v is not None}
        self.f.write(json.dumps({"cmd": cmd, **kw}) + "\n")
        self.f.flush()
        line = self.f.readline()
        if not line:
            raise RuntimeError(f"cocoon-ui closed the connection during {cmd}; see {LOG} on the device")
        reply = json.loads(line)
        if not reply.pop("ok"):
            raise RuntimeError(f"{cmd}: {reply['error']}")
        return reply

    def tree(self, display=None):
        return self.call("tree", display=display)["nodes"]

    def wait_for(self, text, display=None, timeout=10.0, gone=False):
        deadline = time.monotonic() + timeout
        while True:
            nodes = self.tree(display)
            hit = [n for n in nodes if text.lower() in (n.get("text") or n.get("desc") or "").lower()]
            if bool(hit) != gone:
                return hit
            if time.monotonic() > deadline:
                raise TimeoutError(f"{text!r} {'still on' if gone else 'not on'} screen after {timeout}s")
            time.sleep(0.2)


def _local_md5():
    return hashlib.md5(JAR.read_bytes()).hexdigest()


def _try(port):
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=5)
        c = Client(s)
        c.call("ping")
        return c
    except (OSError, RuntimeError, json.JSONDecodeError):
        return None


def start():
    if not JAR.exists():
        raise SystemExit(f"{JAR} missing; run device/cocoon-ui/build.sh")
    remote = device.adb("shell", f"md5sum {DEVICE_JAR} 2>/dev/null || true").decode().split(" ")[0].strip()
    if remote != _local_md5():
        device.adb("push", str(JAR), DEVICE_JAR)
    # An older copy may run as root (first versions did); stop either kind.
    device.root("pkill -f 'cocoonui[.]Server' || true")
    device.adb("shell", f"CLASSPATH={DEVICE_JAR} setsid app_process /system/bin cocoonui.Server "
                        f"> {LOG} 2>&1 < /dev/null &")


def connect():
    """Return a Client for an agent running the local build, starting it if needed."""
    device.adb("forward", f"tcp:{PORT}", "localabstract:cocoon-ui")
    c = _try(PORT)
    if c and c.call("ping").get("jar_md5") == _local_md5():
        return c
    start()
    deadline = time.monotonic() + 10
    while (c := _try(PORT)) is None:
        if time.monotonic() > deadline:
            raise RuntimeError("cocoon-ui did not start:\n" + device.adb("shell", f"cat {LOG}").decode())
        time.sleep(0.3)
    return c


def label(n):
    return n.get("text") or n.get("desc") or ""


def fmt(n):
    b = n["b"]
    flags = [f for f in ("click", "focused", "selected", "editable", "scroll", "disabled") if n.get(f)]
    if "checked" in n:
        flags.append("on" if n["checked"] else "off")
    name = {0: "top", 4: "bottom"}.get(n["d"], f"d{n['d']}")
    cx, cy = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
    return f"{name:6} {label(n)!r:50} at {cx},{cy} [{b[0]},{b[1]},{b[2]},{b[3]}] {' '.join(flags)}"
