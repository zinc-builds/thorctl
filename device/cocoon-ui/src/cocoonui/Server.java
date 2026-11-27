package cocoonui;

import android.accessibilityservice.AccessibilityServiceInfo;
import android.app.UiAutomation;
import android.graphics.Rect;
import android.hardware.input.InputManager;
import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.os.Bundle;
import android.os.HandlerThread;
import android.os.Looper;
import android.os.SystemClock;
import android.util.SparseArray;
import android.view.InputDevice;
import android.view.InputEvent;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

/**
 * Helper for driving Cocoon (and any app) on the AYN Thor.
 *
 * Run as the adb shell user (like scrcpy; no root needed):
 *   CLASSPATH=cocoon-ui.jar app_process /system/bin cocoonui.Server
 * Listens on the abstract socket "cocoon-ui"; one JSON request per line, one
 * JSON reply per line. Only uid 0 and 2000 (adbd's forwards) may connect.
 *
 * - tree / find / click / settext read the accessibility tree of every
 *   display through UiAutomation. The connection is dropped after a few idle
 *   seconds so `uiautomator dump` (used by cocoon-sync) can still connect.
 * - tap / swipe / key inject through InputManager with a display id.
 * - clip sets the clipboard (as com.android.shell), for Cocoon's keyboard
 *   Paste button: Cocoon's text boxes are drawn labels, not text fields.
 * - pad writes evdev events straight into the built-in controller's
 *   /dev/input node, so apps see a real controller press. Cocoon ignores
 *   `input keyevent` gamepad keys but accepts these.
 */
public final class Server {
    static final String VERSION = "1";
    static final String SOCKET = "cocoon-ui";
    static final long IDLE_DISCONNECT_MS = 4000;

    static final Map<String, Integer> PAD = new HashMap<>();
    static {
        PAD.put("A", 304); PAD.put("B", 305); PAD.put("X", 307); PAD.put("Y", 308);
        PAD.put("L1", 310); PAD.put("R1", 311); PAD.put("L2", 312); PAD.put("R2", 313);
        PAD.put("SELECT", 314); PAD.put("START", 315); PAD.put("MODE", 316);
        PAD.put("L3", 317); PAD.put("R3", 318);
        PAD.put("UP", 544); PAD.put("DOWN", 545); PAD.put("LEFT", 546); PAD.put("RIGHT", 547);
    }

    final HandlerThread looperThread = new HandlerThread("cocoon-ui-a11y");
    final ScheduledExecutorService timer = Executors.newSingleThreadScheduledExecutor();
    UiAutomation ui;
    ScheduledFuture<?> idle;
    final Object uiLock = new Object();
    InputManager input;
    Method injectMethod;
    Method setDisplayId;
    String padPath;
    String jarMd5;

    public static void main(String[] args) throws Exception {
        new Server().run();
    }

    void run() throws Exception {
        looperThread.start();
        java.security.MessageDigest md = java.security.MessageDigest.getInstance("MD5");
        StringBuilder hex = new StringBuilder();
        for (byte b : md.digest(Files.readAllBytes(Paths.get(System.getenv("CLASSPATH"))))) {
            hex.append(String.format("%02x", b));
        }
        jarMd5 = hex.toString();
        input = (InputManager) InputManager.class.getMethod("getInstance").invoke(null);
        injectMethod = InputManager.class.getMethod("injectInputEvent", InputEvent.class, int.class);
        setDisplayId = InputEvent.class.getMethod("setDisplayId", int.class);
        try {
            padPath = findPad();
        } catch (IllegalStateException e) {
            System.out.println("warning: " + e.getMessage() + "; pad commands will fail");
        }
        LocalServerSocket server = new LocalServerSocket(SOCKET);
        System.out.println("cocoon-ui " + VERSION + " listening; pad=" + padPath);
        System.out.flush();
        while (true) {
            LocalSocket s = server.accept();
            int uid = s.getPeerCredentials().getUid();
            if (uid != 0 && uid != 2000) {
                s.close();
                continue;
            }
            new Thread(() -> serve(s)).start();
        }
    }

    void serve(LocalSocket s) {
        try (LocalSocket sock = s) {
            BufferedReader in = new BufferedReader(new InputStreamReader(sock.getInputStream(), StandardCharsets.UTF_8));
            OutputStream out = sock.getOutputStream();
            String line;
            while ((line = in.readLine()) != null) {
                JSONObject reply;
                try {
                    reply = handle(new JSONObject(line));
                    reply.put("ok", true);
                } catch (Throwable t) {
                    reply = new JSONObject();
                    reply.put("ok", false);
                    reply.put("error", t.getClass().getSimpleName() + ": " + t.getMessage());
                }
                out.write((reply.toString() + "\n").getBytes(StandardCharsets.UTF_8));
                out.flush();
            }
        } catch (Throwable t) {
            System.err.println("connection error: " + t);
        }
    }

    JSONObject handle(JSONObject req) throws Exception {
        String cmd = req.getString("cmd");
        switch (cmd) {
            case "ping": return new JSONObject().put("version", VERSION).put("pad", padPath)
                    .put("pid", android.os.Process.myPid()).put("jar_md5", jarMd5);
            case "tree": return new JSONObject().put("nodes", tree(req.optInt("display", -1)));
            case "click": return click(req);
            case "settext": return setText(req);
            case "tap": tap(req.getInt("x"), req.getInt("y"), req.optInt("display", 0)); return new JSONObject();
            case "swipe":
                swipe(req.getInt("x1"), req.getInt("y1"), req.getInt("x2"), req.getInt("y2"),
                        req.optInt("ms", 300), req.optInt("display", 0));
                return new JSONObject();
            case "key": key(req.getInt("code"), req.optInt("display", 0)); return new JSONObject();
            case "pad": return pad(req.getJSONArray("buttons"), req.optInt("hold_ms", 60), req.optInt("gap_ms", 120));
            case "clip": setClip(req.getString("value")); return new JSONObject();
            case "quit": timer.schedule(() -> System.exit(0), 100, TimeUnit.MILLISECONDS); return new JSONObject();
            default: throw new IllegalArgumentException("unknown cmd " + cmd);
        }
    }

    // ------------------------------------------------------------ accessibility

    UiAutomation automation() throws Exception {
        synchronized (uiLock) {
            if (idle != null) idle.cancel(false);
            if (ui == null) {
                Class<?> connCls = Class.forName("android.app.UiAutomationConnection");
                Object conn = connCls.getConstructor().newInstance();
                Class<?> iconn = Class.forName("android.app.IUiAutomationConnection");
                Constructor<UiAutomation> c = UiAutomation.class.getDeclaredConstructor(Looper.class, iconn);
                c.setAccessible(true);
                UiAutomation u = c.newInstance(looperThread.getLooper(), conn);
                Method connect = UiAutomation.class.getDeclaredMethod("connect", int.class);
                connect.setAccessible(true);
                // FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES: leave the user's services running.
                connect.invoke(u, 1);
                AccessibilityServiceInfo info = u.getServiceInfo();
                info.flags |= AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
                        | AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS
                        | AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS;
                u.setServiceInfo(info);
                ui = u;
            }
            idle = timer.schedule(this::disconnect, IDLE_DISCONNECT_MS, TimeUnit.MILLISECONDS);
            return ui;
        }
    }

    void disconnect() {
        synchronized (uiLock) {
            if (ui == null) return;
            try {
                Method m = UiAutomation.class.getDeclaredMethod("disconnect");
                m.setAccessible(true);
                m.invoke(ui);
            } catch (Throwable t) {
                System.err.println("disconnect: " + t);
            }
            ui = null;
        }
    }

    List<AccessibilityNodeInfo> roots(int display) throws Exception {
        UiAutomation u = automation();
        List<AccessibilityNodeInfo> out = new ArrayList<>();
        // The window list fills in asynchronously after connecting.
        for (int attempt = 0; attempt < 20 && out.isEmpty(); attempt++) {
            SparseArray<List<AccessibilityWindowInfo>> all = u.getWindowsOnAllDisplays();
            for (int i = 0; i < all.size(); i++) {
                int d = all.keyAt(i);
                if (display >= 0 && d != display) continue;
                for (AccessibilityWindowInfo w : all.valueAt(i)) {
                    AccessibilityNodeInfo r = w.getRoot();
                    if (r != null) out.add(r);
                }
            }
            if (out.isEmpty()) SystemClock.sleep(50);
        }
        return out;
    }

    JSONArray tree(int display) throws Exception {
        JSONArray nodes = new JSONArray();
        for (AccessibilityNodeInfo r : roots(display)) walk(r, 0, nodes);
        return nodes;
    }

    void walk(AccessibilityNodeInfo n, int depth, JSONArray out) throws Exception {
        if (n == null) return;
        Rect b = new Rect();
        n.getBoundsInScreen(b);
        JSONObject o = new JSONObject();
        o.put("d", n.getWindow() != null ? displayOf(n) : -1);
        o.put("depth", depth);
        if (n.getText() != null) o.put("text", n.getText().toString());
        if (n.getContentDescription() != null) o.put("desc", n.getContentDescription().toString());
        if (n.getViewIdResourceName() != null) o.put("id", n.getViewIdResourceName());
        if (n.getPackageName() != null) o.put("pkg", n.getPackageName().toString());
        o.put("cls", n.getClassName() != null ? n.getClassName().toString() : "");
        o.put("b", new JSONArray().put(b.left).put(b.top).put(b.right).put(b.bottom));
        if (n.isClickable()) o.put("click", true);
        if (n.isFocused()) o.put("focused", true);
        if (n.isAccessibilityFocused()) o.put("a11yfocus", true);
        if (n.isCheckable()) o.put("checked", n.isChecked());
        if (n.isSelected()) o.put("selected", true);
        if (n.isEditable()) o.put("editable", true);
        if (n.isScrollable()) o.put("scroll", true);
        if (!n.isEnabled()) o.put("disabled", true);
        out.put(o);
        for (int i = 0; i < n.getChildCount(); i++) walk(n.getChild(i), depth + 1, out);
    }

    static int displayOf(AccessibilityNodeInfo n) {
        AccessibilityWindowInfo w = n.getWindow();
        return w == null ? -1 : w.getDisplayId();
    }

    AccessibilityNodeInfo findNode(JSONObject req) throws Exception {
        String text = req.optString("text", null);
        String desc = req.optString("desc", null);
        String id = req.optString("id", null);
        boolean exact = req.optBoolean("exact", false);
        int index = req.optInt("index", 0);
        List<AccessibilityNodeInfo> hits = new ArrayList<>();
        for (AccessibilityNodeInfo r : roots(req.optInt("display", -1))) collect(r, text, desc, id, exact, hits);
        if (hits.size() <= index) {
            throw new IllegalStateException("no node matches " + req.toString() + " (" + hits.size() + " found)");
        }
        return hits.get(index);
    }

    static boolean matches(CharSequence v, String want, boolean exact) {
        if (want == null) return true;
        if (v == null) return false;
        String s = v.toString();
        return exact ? s.equals(want) : s.toLowerCase().contains(want.toLowerCase());
    }

    void collect(AccessibilityNodeInfo n, String text, String desc, String id, boolean exact,
                 List<AccessibilityNodeInfo> out) {
        if (n == null) return;
        // A plain label search matches visible text or, for icon buttons, the content description.
        boolean labelOk = desc == null && text != null
                ? matches(n.getText(), text, exact) || matches(n.getContentDescription(), text, exact)
                : matches(n.getText(), text, exact) && matches(n.getContentDescription(), desc, exact);
        if (labelOk && (id == null || id.equals(n.getViewIdResourceName()))) {
            out.add(n);
        }
        for (int i = 0; i < n.getChildCount(); i++) collect(n.getChild(i), text, desc, id, exact, out);
    }

    JSONObject describe(AccessibilityNodeInfo n) {
        Rect b = new Rect();
        n.getBoundsInScreen(b);
        JSONObject o = new JSONObject();
        try {
            CharSequence label = n.getText() != null ? n.getText() : n.getContentDescription();
            o.put("text", label == null ? null : label.toString());
            o.put("d", displayOf(n));
            o.put("b", new JSONArray().put(b.left).put(b.top).put(b.right).put(b.bottom));
        } catch (Exception ignored) {
            // JSONObject.put only throws for non-finite numbers.
        }
        return o;
    }

    /** Click the matched node: ACTION_CLICK on it or its nearest clickable ancestor. */
    JSONObject click(JSONObject req) throws Exception {
        AccessibilityNodeInfo n = findNode(req);
        AccessibilityNodeInfo target = n;
        while (target != null && !target.isClickable()) target = target.getParent();
        JSONObject out = new JSONObject().put("node", describe(n));
        if (target == null || req.optBoolean("tap", false)) {
            Rect b = new Rect();
            n.getBoundsInScreen(b);
            tap(b.centerX(), b.centerY(), displayOf(n));
            return out.put("via", "tap");
        }
        if (!target.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
            throw new IllegalStateException("ACTION_CLICK refused by " + describe(target));
        }
        return out.put("via", "action");
    }

    JSONObject setText(JSONObject req) throws Exception {
        // Among the nodes the selector matches (every node when there is none), use the first
        // that is editable or sits inside an editable one. A label can match both a list row
        // and a search field holding the same text, so the first hit is not enough.
        List<AccessibilityNodeInfo> hits = new ArrayList<>();
        for (AccessibilityNodeInfo r : roots(req.optInt("display", -1))) {
            collect(r, req.optString("text", null), req.optString("desc", null), req.optString("id", null),
                    req.optBoolean("exact", false), hits);
        }
        AccessibilityNodeInfo target = null;
        for (AccessibilityNodeInfo h : hits) {
            AccessibilityNodeInfo t = h;
            while (t != null && !t.isEditable()) t = t.getParent();
            if (t != null) { target = t; break; }
        }
        if (target == null) {
            throw new IllegalStateException("no editable node matches " + req.toString() + " (" + hits.size() + " nodes matched)");
        }
        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, req.getString("value"));
        if (!target.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) {
            throw new IllegalStateException("ACTION_SET_TEXT refused");
        }
        return new JSONObject().put("node", describe(target));
    }

    // ------------------------------------------------------------ clipboard

    void setClip(String text) throws Exception {
        Class<?> sm = Class.forName("android.os.ServiceManager");
        Object binder = sm.getMethod("getService", String.class).invoke(null, "clipboard");
        Class<?> stub = Class.forName("android.content.IClipboard$Stub");
        Object clipboard = stub.getMethod("asInterface", android.os.IBinder.class).invoke(null, binder);
        android.content.ClipData clip = android.content.ClipData.newPlainText("cocoon-ui", text);
        for (Method m : clipboard.getClass().getMethods()) {
            if (!m.getName().equals("setPrimaryClip")) continue;
            Class<?>[] p = m.getParameterTypes();
            // API 33: (ClipData, String pkg, String attributionTag, int userId)
            // API 34+: (..., int userId, int deviceId)
            if (p.length == 4) { m.invoke(clipboard, clip, "com.android.shell", null, 0); return; }
            if (p.length == 5) { m.invoke(clipboard, clip, "com.android.shell", null, 0, 0); return; }
        }
        throw new IllegalStateException("no known IClipboard.setPrimaryClip signature");
    }

    // ------------------------------------------------------------ input

    void inject(InputEvent e, int display) throws Exception {
        setDisplayId.invoke(e, display);
        // 2 = INJECT_INPUT_EVENT_MODE_WAIT_FOR_FINISH
        if (!(Boolean) injectMethod.invoke(input, e, 2)) throw new IllegalStateException("injection refused");
    }

    void touch(int action, long down, int x, int y, int display) throws Exception {
        MotionEvent e = MotionEvent.obtain(down, SystemClock.uptimeMillis(), action, x, y, 0);
        e.setSource(InputDevice.SOURCE_TOUCHSCREEN);
        inject(e, display);
        e.recycle();
    }

    void tap(int x, int y, int display) throws Exception {
        long down = SystemClock.uptimeMillis();
        touch(MotionEvent.ACTION_DOWN, down, x, y, display);
        SystemClock.sleep(40);
        touch(MotionEvent.ACTION_UP, down, x, y, display);
    }

    void swipe(int x1, int y1, int x2, int y2, int ms, int display) throws Exception {
        long down = SystemClock.uptimeMillis();
        touch(MotionEvent.ACTION_DOWN, down, x1, y1, display);
        int steps = Math.max(5, ms / 16);
        for (int i = 1; i <= steps; i++) {
            SystemClock.sleep(ms / steps);
            touch(MotionEvent.ACTION_MOVE, down, x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps, display);
        }
        touch(MotionEvent.ACTION_UP, down, x2, y2, display);
    }

    void key(int code, int display) throws Exception {
        long now = SystemClock.uptimeMillis();
        inject(new KeyEvent(now, now, KeyEvent.ACTION_DOWN, code, 0), display);
        inject(new KeyEvent(now, SystemClock.uptimeMillis(), KeyEvent.ACTION_UP, code, 0), display);
    }

    /**
     * The built-in controller: the first input device whose key bitmap has
     * BTN_GAMEPAD (304). On the Thor that is AYN's virtual "Xbox Wireless
     * Controller", which the physical buttons feed. COCOON_UI_PAD overrides.
     */
    static String findPad() throws Exception {
        String forced = System.getenv("COCOON_UI_PAD");
        if (forced != null && !forced.isEmpty()) return forced;
        String devices = new String(Files.readAllBytes(Paths.get("/proc/bus/input/devices")), StandardCharsets.UTF_8);
        for (String block : devices.split("\n\n")) {
            String handlers = null, keys = null;
            for (String l : block.split("\n")) {
                if (l.startsWith("H: Handlers=")) handlers = l;
                if (l.startsWith("B: KEY=")) keys = l.substring(7).trim();
            }
            if (handlers == null || keys == null || !hasBit(keys, 304)) continue;
            java.util.regex.Matcher m = java.util.regex.Pattern.compile("\\b(event\\d+)\\b").matcher(handlers);
            if (m.find()) return "/dev/input/" + m.group(1);
        }
        throw new IllegalStateException("no input device with BTN_GAMEPAD in /proc/bus/input/devices");
    }

    /** Bitmaps in /proc/bus/input/devices are 64-bit hex words, most significant first. */
    static boolean hasBit(String bitmap, int bit) {
        String[] words = bitmap.split(" ");
        int index = words.length - 1 - bit / 64;
        if (index < 0) return false;
        return ((Long.parseUnsignedLong(words[index], 16) >>> (bit % 64)) & 1L) == 1L;
    }

    static byte[] ev(int type, int code, int value) {
        ByteBuffer b = ByteBuffer.allocate(24).order(ByteOrder.LITTLE_ENDIAN);
        b.putLong(0).putLong(0).putShort((short) type).putShort((short) code).putInt(value);
        return b.array();
    }

    JSONObject pad(JSONArray buttons, int holdMs, int gapMs) throws Exception {
        if (padPath == null) padPath = findPad();
        try (FileOutputStream out = new FileOutputStream(padPath)) {
            for (int i = 0; i < buttons.length(); i++) {
                String name = buttons.getString(i).toUpperCase();
                Integer code = PAD.get(name);
                if (code == null) throw new IllegalArgumentException("unknown button " + name + "; known: " + PAD.keySet());
                out.write(ev(1, code, 1)); out.write(ev(0, 0, 0)); out.flush();
                SystemClock.sleep(holdMs);
                out.write(ev(1, code, 0)); out.write(ev(0, 0, 0)); out.flush();
                if (i < buttons.length() - 1) SystemClock.sleep(gapMs);
            }
        }
        return new JSONObject().put("pad", padPath);
    }
}
