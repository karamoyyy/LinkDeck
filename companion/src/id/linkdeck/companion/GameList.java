package id.linkdeck.companion;

import android.content.pm.ApplicationInfo;
import android.os.IBinder;

import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Enumeration;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Daftar game yang terpasang, untuk Mode Game LinkDeck. Tidak perlu memasang aplikasi:
 * LinkDeck mengirim APK ini ke /data/local/tmp lalu menjalankan
 *
 *     CLASSPATH=/data/local/tmp/linkdeck-companion.apk app_process / id.linkdeck.companion.GameList
 *
 * sebagai pengguna adb (shell). Keluaran, satu baris per game:  GAME <paket> <alasan>
 *   category : aplikasi menyatakan dirinya game (android:appCategory="game")
 *   flag     : android:isGame="true" (cara lama, masih dipakai Unity dan banyak game)
 *   unity / unreal / cocos / godot : mesin game terdeteksi di dalam APK
 * Baris terakhir:  DONE <jumlah aplikasi> <jumlah game>
 */
public final class GameList {
    private static final int CATEGORY_GAME = 0;            // ApplicationInfo.CATEGORY_GAME (API 26)

    private GameList() { }

    public static void main(String[] args) {
        try {
            int user = 0;
            if (args.length > 0) {
                try {
                    user = Integer.parseInt(args[0]);
                } catch (NumberFormatException ignored) { }
            }
            List<?> apps = installed(user);
            Field category = null;
            try {
                category = ApplicationInfo.class.getField("category");
            } catch (NoSuchFieldException ignored) { }   // Android 7 ke bawah
            Field splits = null;
            try {
                splits = ApplicationInfo.class.getField("splitSourceDirs");
            } catch (NoSuchFieldException ignored) { }
            int games = 0;
            for (Object o : apps) {
                ApplicationInfo ai = (ApplicationInfo) o;
                String why = null;
                if (category != null && category.getInt(ai) == CATEGORY_GAME) {
                    why = "category";
                } else if ((ai.flags & ApplicationInfo.FLAG_IS_GAME) != 0) {
                    why = "flag";
                } else if ((ai.flags & ApplicationInfo.FLAG_SYSTEM) == 0
                        || (ai.flags & ApplicationInfo.FLAG_UPDATED_SYSTEM_APP) != 0) {
                    why = engine(ai.sourceDir);
                    String[] parts = splits != null ? (String[]) splits.get(ai) : null;
                    if (why == null && parts != null) {
                        for (String p : parts) {
                            why = engine(p);
                            if (why != null) break;
                        }
                    }
                }
                if (why != null) {
                    System.out.println("GAME " + ai.packageName + " " + why);
                    games++;
                }
            }
            System.out.println("DONE " + apps.size() + " " + games);
        } catch (Throwable t) {
            Throwable c = t.getCause() != null ? t.getCause() : t;
            System.out.println("ERROR " + c.getClass().getSimpleName() + ": " + c.getMessage());
        }
    }

    /** IPackageManager.getInstalledApplications lewat refleksi (tanda tangannya berbeda antar versi Android). */
    private static List<?> installed(int user) throws Exception {
        Class<?> sm = Class.forName("android.os.ServiceManager");
        IBinder binder = (IBinder) sm.getMethod("getService", String.class).invoke(null, "package");
        Object pm = Class.forName("android.content.pm.IPackageManager$Stub")
                .getMethod("asInterface", IBinder.class).invoke(null, binder);
        // cari lewat antarmuka publik IPackageManager: kelas Proxy di baliknya bersifat private
        for (Method m : Class.forName("android.content.pm.IPackageManager").getMethods()) {
            if (!"getInstalledApplications".equals(m.getName())) continue;
            Class<?>[] p = m.getParameterTypes();
            if (p.length != 2 || p[1] != int.class) continue;
            Object flags = p[0] == long.class ? (Object) Long.valueOf(0) : (Object) Integer.valueOf(0);
            accessible(m);
            Object res = m.invoke(pm, flags, user);
            if (res instanceof List) return (List<?>) res;
            Method getList = Class.forName("android.content.pm.ParceledListSlice").getMethod("getList");
            accessible(getList);
            return (List<?>) getList.invoke(res);
        }
        throw new NoSuchMethodException("getInstalledApplications");
    }

    private static void accessible(Method m) {
        try {
            m.setAccessible(true);
        } catch (Exception ignored) { }
    }

    /** Cari tanda mesin game di daftar isi APK (hanya direktori zip yang dibaca, cepat). */
    private static String engine(String path) {
        if (path == null || !new File(path).canRead()) return null;
        ZipFile zip = null;
        try {
            zip = new ZipFile(path);
            Enumeration<? extends ZipEntry> en = zip.entries();
            while (en.hasMoreElements()) {
                String n = en.nextElement().getName();
                if (n.startsWith("lib/")) {
                    String f = n.substring(n.lastIndexOf('/') + 1);
                    if (f.equals("libunity.so") || f.equals("libil2cpp.so")) return "unity";
                    if (f.equals("libUE4.so") || f.equals("libUnreal.so")) return "unreal";
                    if (f.startsWith("libcocos2d") || f.equals("libcocos.so")) return "cocos";
                    if (f.equals("libgodot_android.so")) return "godot";
                } else if (n.startsWith("assets/bin/Data/")) {
                    return "unity";
                }
            }
        } catch (Exception ignored) {
        } finally {
            if (zip != null) {
                try {
                    zip.close();
                } catch (Exception ignored) { }
            }
        }
        return null;
    }
}
