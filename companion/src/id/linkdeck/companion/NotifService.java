package id.linkdeck.companion;

import android.app.Notification;
import android.app.PendingIntent;
import android.app.RemoteInput;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.net.Credentials;
import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Parcelable;
import android.os.Process;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.Charset;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Pendengar notifikasi + server soket lokal "linkdeck_companion" (namespace abstrak).
 *
 * LinkDeck di laptop menjangkaunya lewat `adb forward tcp:0 localabstract:linkdeck_companion`.
 * Protokol: satu objek JSON per baris (UTF-8).
 *   HP -> PC : hello, battery, notif {op: posted|removed}, list, result, pong
 *   PC -> HP : list, reply {key, action, text}, action {key, action}, dismiss {key}, ping
 *
 * Keamanan: soket abstrak bisa dibuka aplikasi apa pun di HP, jadi identitas penyambung dicek.
 * Hanya adb (uid shell 2000), root (0), atau aplikasi ini sendiri yang boleh membaca & membalas
 * notifikasi. Penyambung lain (mis. agen Debian di Termux/proot) hanya menerima status baterai,
 * yang memang sudah dibagikan Android ke semua aplikasi.
 */
public class NotifService extends NotificationListenerService {
    static final String TAG = "LinkDeckCompanion";
    static final String SOCKET = "linkdeck_companion";
    static final int PROTO = 1;
    static final Charset UTF8 = Charset.forName("UTF-8");

    static volatile int clientCount = 0;
    static volatile boolean connected = false;

    private final CopyOnWriteArrayList<Client> clients = new CopyOnWriteArrayList<Client>();
    private final ExecutorService sender = Executors.newSingleThreadExecutor();
    private final Map<String, String> labels = new HashMap<String, String>();
    private final Handler main = new Handler(Looper.getMainLooper());
    private LocalServerSocket server;
    private Thread acceptThread;
    private volatile boolean running;
    private volatile JSONObject battery;
    private String batterySig = "";

    // ------------------------------------------------------------------ siklus hidup

    @Override
    public void onCreate() {
        super.onCreate();
        running = true;
        registerReceiver(batteryReceiver, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        startServer();
    }

    @Override
    public void onDestroy() {
        running = false;
        try { unregisterReceiver(batteryReceiver); } catch (Exception ignored) { }
        try { if (server != null) server.close(); } catch (IOException ignored) { }
        for (Client c : clients) c.close();
        clients.clear();
        clientCount = 0;
        connected = false;
        sender.shutdownNow();
        super.onDestroy();
    }

    @Override
    public void onListenerConnected() {
        connected = true;
        broadcastFull(listMessage());
    }

    // API 24+: tanpa @Override karena android.jar yang dipakai API 23; tetap dipanggil sistem di Android 7+
    public void onListenerDisconnected() {
        connected = false;
    }

    private void startServer() {
        try {
            server = new LocalServerSocket(SOCKET);
        } catch (IOException e) {
            // nama sudah dipakai (proses lama belum mati): coba lagi sebentar lagi
            Log.w(TAG, "socket busy: " + e);
            main.postDelayed(new Runnable() {
                @Override public void run() { if (running && server == null) startServer(); }
            }, 3000);
            return;
        }
        acceptThread = new Thread(new Runnable() {
            @Override public void run() { acceptLoop(); }
        }, "linkdeck-accept");
        acceptThread.setDaemon(true);
        acceptThread.start();
    }

    private void acceptLoop() {
        while (running) {
            LocalSocket s;
            try {
                s = server.accept();
            } catch (IOException e) {
                if (running) Log.w(TAG, "accept: " + e);
                return;
            }
            int uid = -1;
            try {
                Credentials cred = s.getPeerCredentials();
                uid = cred.getUid();
            } catch (IOException ignored) { }
            boolean full = uid == 0 || uid == 2000 || uid == Process.myUid();
            final Client c = new Client(s, full);
            clients.add(c);
            clientCount = clients.size();
            Thread t = new Thread(new Runnable() {
                @Override public void run() { c.readLoop(); }
            }, "linkdeck-client");
            t.setDaemon(true);
            t.start();
        }
    }

    // ------------------------------------------------------------------ klien

    private final class Client {
        final LocalSocket sock;
        final boolean full;
        final OutputStream out;
        volatile boolean open = true;

        Client(LocalSocket sock, boolean full) {
            this.sock = sock;
            this.full = full;
            OutputStream o = null;
            try { o = sock.getOutputStream(); } catch (IOException e) { open = false; }
            this.out = o;
        }

        void send(final JSONObject msg) {
            if (!open || out == null) return;
            final byte[] data = (msg.toString() + "\n").getBytes(UTF8);
            try {
                sender.execute(new Runnable() {
                    @Override public void run() {
                        try {
                            out.write(data);
                            out.flush();
                        } catch (IOException e) {
                            close();
                        }
                    }
                });
            } catch (Exception ignored) { }   // executor sudah dimatikan
        }

        void close() {
            open = false;
            try { sock.shutdownInput(); } catch (Exception ignored) { }
            try { sock.close(); } catch (Exception ignored) { }
            clients.remove(this);
            clientCount = clients.size();
        }

        void readLoop() {
            try {
                send(hello(full));
                JSONObject b = battery;
                if (b != null) send(b);
                if (full) send(listMessage());
                BufferedReader in = new BufferedReader(new InputStreamReader(sock.getInputStream(), UTF8));
                String line;
                while (open && (line = in.readLine()) != null) {
                    if (line.length() == 0) continue;
                    if (line.length() > 65536) break;
                    try {
                        handle(this, new JSONObject(line));
                    } catch (JSONException e) {
                        Log.w(TAG, "bad message: " + e);
                    }
                }
            } catch (IOException ignored) {
            } finally {
                close();
            }
        }
    }

    private void handle(final Client c, final JSONObject m) {
        String type = m.optString("type");
        final Object id = m.opt("id");
        if ("ping".equals(type)) {
            c.send(obj("type", "pong"));
            return;
        }
        if ("battery".equals(type)) {
            JSONObject b = battery;
            if (b != null) c.send(b);
            return;
        }
        if (!c.full) {
            c.send(result(id, false, "denied"));
            return;
        }
        if ("list".equals(type)) {
            c.send(listMessage());
            return;
        }
        if ("reply".equals(type) || "action".equals(type) || "dismiss".equals(type)) {
            final String kind = type;
            // RemoteInput/PendingIntent dan cancelNotification aman dipanggil dari thread utama
            main.post(new Runnable() {
                @Override public void run() {
                    String err;
                    try {
                        err = act(kind, m.optString("key"), m.optInt("action", -1), m.optString("text"));
                    } catch (Exception e) {
                        err = e.getClass().getSimpleName() + ": " + e.getMessage();
                    }
                    c.send(result(id, err == null, err));
                }
            });
            return;
        }
        c.send(result(id, false, "unknown type"));
    }

    /** Menjalankan balasan / tombol / tutup. Mengembalikan null bila berhasil, atau pesan galat. */
    private String act(String kind, String key, int index, String text) throws PendingIntent.CanceledException {
        StatusBarNotification sbn = find(key);
        if (sbn == null) return "gone";
        if ("dismiss".equals(kind)) {
            cancelNotification(key);
            return null;
        }
        Notification.Action[] actions = sbn.getNotification().actions;
        if (actions == null || index < 0 || index >= actions.length) return "no action";
        Notification.Action a = actions[index];
        if (a.actionIntent == null) return "no intent";
        if ("reply".equals(kind)) {
            RemoteInput[] inputs = a.getRemoteInputs();
            if (inputs == null || inputs.length == 0) return "not a reply action";
            if (text == null || text.trim().length() == 0) return "empty";
            Intent intent = new Intent();
            Bundle results = new Bundle();
            for (RemoteInput ri : inputs) results.putCharSequence(ri.getResultKey(), text);
            RemoteInput.addResultsToIntent(inputs, intent, results);
            a.actionIntent.send(this, 0, intent);
        } else {
            a.actionIntent.send();
        }
        return null;
    }

    private StatusBarNotification find(String key) {
        StatusBarNotification[] all;
        try {
            all = getActiveNotifications();
        } catch (Exception e) {
            return null;
        }
        if (all == null) return null;
        for (StatusBarNotification s : all) if (s.getKey().equals(key)) return s;
        return null;
    }

    // ------------------------------------------------------------------ notifikasi

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        JSONObject n = describe(sbn);
        if (n == null) return;
        JSONObject m = obj("type", "notif");
        put(m, "op", "posted");
        put(m, "n", n);
        broadcastFull(m);
    }

    @Override
    public void onNotificationRemoved(StatusBarNotification sbn) {
        JSONObject m = obj("type", "notif");
        put(m, "op", "removed");
        put(m, "key", sbn.getKey());
        broadcastFull(m);
    }

    private JSONObject listMessage() {
        JSONArray arr = new JSONArray();
        StatusBarNotification[] all = null;
        try {
            all = getActiveNotifications();
        } catch (Exception ignored) { }     // pendengar belum tersambung
        if (all != null) {
            for (StatusBarNotification s : all) {
                JSONObject n = describe(s);
                if (n != null) arr.put(n);
            }
        }
        JSONObject m = obj("type", "list");
        put(m, "items", arr);
        put(m, "listening", connected);
        return m;
    }

    private JSONObject describe(StatusBarNotification sbn) {
        Notification n = sbn.getNotification();
        if (n == null) return null;
        Bundle ex = n.extras;
        String pkg = sbn.getPackageName();
        JSONObject o = new JSONObject();
        put(o, "key", sbn.getKey());
        put(o, "pkg", pkg);
        put(o, "app", label(pkg));
        put(o, "time", sbn.getPostTime());
        put(o, "ongoing", sbn.isOngoing());
        put(o, "clearable", sbn.isClearable());
        put(o, "summary", (n.flags & 0x200) != 0);                     // FLAG_GROUP_SUMMARY
        put(o, "foreground", (n.flags & Notification.FLAG_FOREGROUND_SERVICE) != 0);
        put(o, "category", n.category == null ? "" : n.category);
        String title = "", text = "";
        if (ex != null) {
            title = str(ex.getCharSequence(Notification.EXTRA_TITLE));
            String conv = str(ex.getCharSequence("android.conversationTitle"));
            text = str(ex.getCharSequence(Notification.EXTRA_BIG_TEXT));
            if (text.length() == 0) text = str(ex.getCharSequence(Notification.EXTRA_TEXT));
            // gaya percakapan (WhatsApp, Telegram, SMS): ambil beberapa pesan terakhir
            Parcelable[] msgs = ex.getParcelableArray("android.messages");
            if (msgs != null && msgs.length > 0) {
                JSONArray lines = new JSONArray();
                for (int i = Math.max(0, msgs.length - 5); i < msgs.length; i++) {
                    if (!(msgs[i] instanceof Bundle)) continue;
                    Bundle b = (Bundle) msgs[i];
                    String body = str(b.getCharSequence("text"));
                    if (body.length() == 0) continue;
                    String sender = str(b.getCharSequence("sender"));
                    Object person = b.get("sender_person");
                    if (sender.length() == 0 && person != null) sender = personName(person);
                    JSONObject line = new JSONObject();
                    put(line, "from", sender);
                    put(line, "text", clip(body, 500));
                    lines.put(line);
                }
                if (lines.length() > 0) put(o, "messages", lines);
            }
            if (conv.length() > 0) put(o, "conversation", conv);
            if (text.length() == 0) {
                CharSequence[] tl = ex.getCharSequenceArray(Notification.EXTRA_TEXT_LINES);
                if (tl != null && tl.length > 0) text = str(tl[tl.length - 1]);
            }
        }
        if (title.length() == 0 && text.length() == 0 && n.tickerText != null) text = str(n.tickerText);
        put(o, "title", clip(title, 200));
        put(o, "text", clip(text, 1000));
        JSONArray acts = new JSONArray();
        if (n.actions != null) {
            for (int i = 0; i < n.actions.length; i++) {
                Notification.Action a = n.actions[i];
                if (a == null || a.title == null) continue;
                RemoteInput[] ri = a.getRemoteInputs();
                boolean reply = false;
                String hint = "";
                if (ri != null) {
                    for (RemoteInput r : ri) {
                        if (r.getAllowFreeFormInput()) {
                            reply = true;
                            if (r.getLabel() != null) hint = r.getLabel().toString();
                        }
                    }
                }
                JSONObject a2 = new JSONObject();
                put(a2, "i", i);
                put(a2, "title", clip(a.title.toString(), 60));
                put(a2, "reply", reply);
                if (hint.length() > 0) put(a2, "hint", clip(hint, 60));
                acts.put(a2);
            }
        }
        put(o, "actions", acts);
        return o;
    }

    private static String personName(Object person) {
        // android.app.Person (API 28) tidak ada di android.jar API 23: panggil lewat refleksi
        try {
            Object name = person.getClass().getMethod("getName").invoke(person);
            return name == null ? "" : name.toString();
        } catch (Exception e) {
            return "";
        }
    }

    private String label(String pkg) {
        synchronized (labels) {
            String l = labels.get(pkg);
            if (l != null) return l;
            try {
                PackageManager pm = getPackageManager();
                ApplicationInfo ai = pm.getApplicationInfo(pkg, 0);
                l = pm.getApplicationLabel(ai).toString();
            } catch (Exception e) {
                l = "";
            }
            labels.put(pkg, l);
            return l;
        }
    }

    private void broadcastFull(JSONObject m) {
        for (Client c : clients) if (c.full) c.send(m);
    }

    // ------------------------------------------------------------------ baterai

    private final BroadcastReceiver batteryReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context ctx, Intent i) {
            int level = i.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
            int scale = i.getIntExtra(BatteryManager.EXTRA_SCALE, 100);
            int status = i.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
            int plugged = i.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0);
            int temp = i.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Integer.MIN_VALUE);
            int volt = i.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1);
            int pct = (level >= 0 && scale > 0) ? Math.round(level * 100f / scale) : -1;
            String st;
            switch (status) {
                case BatteryManager.BATTERY_STATUS_CHARGING: st = "charging"; break;
                case BatteryManager.BATTERY_STATUS_FULL: st = "full"; break;
                case BatteryManager.BATTERY_STATUS_NOT_CHARGING: st = "not_charging"; break;
                case BatteryManager.BATTERY_STATUS_DISCHARGING: st = "discharging"; break;
                default: st = "unknown";
            }
            String plug;
            switch (plugged) {
                case BatteryManager.BATTERY_PLUGGED_AC: plug = "ac"; break;
                case BatteryManager.BATTERY_PLUGGED_USB: plug = "usb"; break;
                case BatteryManager.BATTERY_PLUGGED_WIRELESS: plug = "wireless"; break;
                case 8: plug = "dock"; break;                        // BATTERY_PLUGGED_DOCK (API 33)
                default: plug = plugged == 0 ? "none" : "other";
            }
            JSONObject b = obj("type", "battery");
            put(b, "level", pct);
            put(b, "status", st);
            put(b, "plugged", plug);
            put(b, "charging", "charging".equals(st) || ("full".equals(st) && plugged != 0));
            if (temp != Integer.MIN_VALUE) put(b, "temp", temp / 10.0);
            if (volt > 0) put(b, "voltage", volt);
            try {
                BatteryManager bm = (BatteryManager) getSystemService(Context.BATTERY_SERVICE);
                int cur = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW);
                if (cur != Integer.MIN_VALUE && cur != 0) put(b, "current_ua", cur);
            } catch (Exception ignored) { }
            battery = b;
            String sig = pct + "|" + st + "|" + plug + "|" + (temp / 5);   // abaikan getaran suhu < 0,5C
            if (sig.equals(batterySig)) return;
            batterySig = sig;
            for (Client c : clients) c.send(b);
        }
    };

    // ------------------------------------------------------------------ pembantu JSON

    private JSONObject hello(boolean full) {
        JSONObject h = obj("type", "hello");
        put(h, "v", PROTO);
        put(h, "app", BuildInfo.VERSION);
        put(h, "sdk", Build.VERSION.SDK_INT);
        put(h, "model", Build.MANUFACTURER + " " + Build.MODEL);
        put(h, "full", full);
        put(h, "listening", connected);
        return h;
    }

    private static JSONObject result(Object id, boolean ok, String error) {
        JSONObject r = obj("type", "result");
        put(r, "id", id == null ? JSONObject.NULL : id);
        put(r, "ok", ok);
        if (error != null) put(r, "error", error);
        return r;
    }

    static JSONObject obj(String k, Object v) {
        JSONObject o = new JSONObject();
        put(o, k, v);
        return o;
    }

    static void put(JSONObject o, String k, Object v) {
        try {
            o.put(k, v);
        } catch (JSONException ignored) { }
    }

    static String str(CharSequence cs) {
        return cs == null ? "" : cs.toString().trim();
    }

    static String clip(String s, int max) {
        if (s.length() <= max) return s;
        int end = max - 1;
        if (Character.isHighSurrogate(s.charAt(end - 1))) end--;         // jangan potong emoji di tengah
        return s.substring(0, end) + "\u2026";
    }
}
