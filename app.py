#!/usr/bin/env python3
"""
LinkDeck desktop — menjalankan server lokal di thread latar lalu membuka jendela aplikasi.

Urutan jendela:
  Windows/macOS : pywebview (WebView2 / WKWebView) -> Chrome/Edge mode aplikasi -> browser biasa
  Linux         : Chrome/Chromium/Edge mode aplikasi -> pywebview (jika ada) -> browser biasa
Paksa salah satunya dengan LINKDECK_UI=webview|chromium|browser.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import server
from aiohttp import web

URL = f"http://{server.HOST}:{server.PORT}/"
SECONDARY = False   # True bila server sudah dijalankan instans lain


def setup_logging() -> None:
    if not server.FROZEN:
        return
    d = server.user_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    log = open(d / "linkdeck.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stderr = log
    print(f"\n--- LinkDeck {server.VERSION} dimulai {time.ctime()} ---")


def linkdeck_running() -> bool:
    try:
        with socket.create_connection((server.HOST, server.PORT), 0.5):
            pass
    except OSError:
        return False
    try:
        with urllib.request.urlopen(URL, timeout=2) as r:
            return b"LinkDeck" in r.read(4096)
    except Exception:
        return False


def start_server():
    """Jalankan aiohttp di thread sendiri. Mengembalikan fungsi stop()."""
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    err: list[BaseException] = []

    def worker() -> None:
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(server.build_app())
        try:
            loop.run_until_complete(runner.setup())
            loop.run_until_complete(web.TCPSite(runner, server.HOST, server.PORT).start())
        except BaseException as e:  # port terpakai, dll.
            err.append(e)
            ready.set()
            return
        ready.set()
        loop.run_forever()
        loop.run_until_complete(runner.cleanup())   # memicu on_shutdown: hentikan mirror, adb, dll.

    t = threading.Thread(target=worker, name="linkdeck-server", daemon=True)
    t.start()
    ready.wait(20)
    if err:
        raise err[0]

    def stop() -> None:
        loop.call_soon_threadsafe(loop.stop)
        t.join(10)

    return stop


# ------------------------------------------------------------------ jendela

class Api:
    """Dipanggil dari halaman lewat window.pywebview.api.*"""

    def __init__(self) -> None:
        self._window = None
        self._full = False

    def screens(self):
        import webview
        return [{"i": i, "x": getattr(s, "x", 0), "y": getattr(s, "y", 0),
                 "width": s.width, "height": s.height} for i, s in enumerate(webview.screens)]

    def fullscreen_on(self, index=None):
        import webview
        w = self._window
        if w is None:
            return False
        if index is not None and not self._full:
            scr = webview.screens
            i = int(index)
            if 0 <= i < len(scr):
                w.move(getattr(scr[i], "x", 0) + 40, getattr(scr[i], "y", 0) + 40)
                time.sleep(0.2)
        if not self._full:
            w.toggle_fullscreen()
            self._full = True
        return True

    def exit_fullscreen(self):
        if self._window is not None and self._full:
            self._window.toggle_fullscreen()
            self._full = False
        return True


class Desktop:
    """Jendela, ikon tray, dan keluar. Satu objek per proses (server.DESKTOP)."""

    def __init__(self, start_hidden: bool) -> None:
        self.start_hidden = start_hidden
        self.quitting = threading.Event()
        self.mode: str | None = None          # webview | chromium | browser
        self.window = None                    # jendela pywebview
        self.proc: subprocess.Popen | None = None
        self.exe: str | None = None
        self.tray = None
        self.notified = False
        self.lock = threading.Lock()
        self.detached = threading.Event()      # peluncur Chromium keluar cepat: jendela milik proses lain

    # ---------- dipanggil dari server / tray (thread mana pun)
    def info(self) -> dict:
        return {"mode": self.mode, "tray": bool(self.tray and self.tray.visible()),
                "tray_menu": bool(self.tray and self.tray.has_menu)}

    def keep_in_tray(self) -> bool:
        return bool(server.S.settings.get("tray", True) and self.tray and self.tray.visible())

    def show(self) -> None:
        if self.quitting.is_set():
            return
        if self.mode == "webview" and self.window is not None:
            self.window.show()
            try:
                self.window.restore()
            except Exception:
                pass
        elif self.mode == "chromium":
            self.launch_chromium()
        elif self.mode == "browser":
            webbrowser.open(URL)

    def quit(self) -> None:
        self.quitting.set()
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass
        with self.lock:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
        if self.tray:
            self.tray.stop()

    def mirror(self) -> None:
        import features
        if server.S.loop:
            asyncio.run_coroutine_threadsafe(features.hotkey_action("mirror"), server.S.loop)

    def told_once(self) -> None:
        if not self.notified and self.tray:
            self.notified = True
            self.tray.notify("LinkDeck tetap berjalan di tray. Klik ikonnya untuk membuka lagi.")

    def make_tray(self) -> bool:
        if sys.platform == "darwin":
            return False                       # macOS: buka lagi lewat Dock (pystray bentrok dengan WKWebView)
        import tray
        lang = server.S.settings.get("lang") or ""
        if lang not in ("id", "en"):        # belum memilih: ikuti bahasa sistem untuk pemasangan baru
            loc = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()
            if sys.platform == "win32":
                import locale
                loc = (locale.getlocale()[0] or "").lower()      # mis. "Indonesian_Indonesia"
            lang = "id" if server.S.settings.get("onboarded") or loc.startswith(
                ("id", "ms", "in_", "indonesian", "malay")) else "en"
        t = tray.Tray(on_open=self.show, on_quit=self.quit, on_mirror=self.mirror, lang=lang)
        if t.create():
            self.tray = t
            return True
        print("[tray]", t.error, flush=True)
        return False

    # ---------- pywebview (Windows/macOS)
    def on_closing(self):
        if self.quitting.is_set() or not self.keep_in_tray():
            self.quitting.set()
            return None                        # tutup sungguhan
        threading.Timer(0.05, self.window.hide).start()
        self.told_once()
        return False                           # batalkan tutup: sembunyikan ke tray

    def run_webview(self) -> bool:
        try:
            import webview
        except ImportError:
            return False
        gui = {"win32": "edgechromium", "darwin": "cocoa"}.get(sys.platform)
        has_tray = self.make_tray()
        api = Api()
        try:
            self.window = webview.create_window(
                "LinkDeck", URL, width=1440, height=940, min_size=(900, 640),
                js_api=api, background_color="#2a1f25", text_select=True,
                hidden=self.start_hidden and has_tray, minimized=self.start_hidden and not has_tray)
            api._window = self.window
            self.window.events.closing += self.on_closing
            self.mode = "webview"
            if has_tray:
                self.tray.run_in_thread()
            store = server.user_data_dir() / "webview"
            store.mkdir(parents=True, exist_ok=True)
            webview.start(gui=gui, private_mode=False, storage_path=str(store))
            return True
        except Exception as e:
            print("pywebview gagal:", e)
            self.window, self.mode = None, None
            if self.tray:
                self.tray.stop()
                self.tray = None
            return False
        finally:
            if self.mode == "webview":
                self.quit()

    # ---------- Chrome/Edge mode aplikasi (Linux; cadangan di Windows/macOS)
    def chromium_args(self) -> list[str]:
        profile = server.user_data_dir() / "chromium-profile"
        profile.mkdir(parents=True, exist_ok=True)
        args = [self.exe, f"--app={URL}", f"--user-data-dir={profile}", "--window-size=1440,940",
                "--no-first-run", "--no-default-browser-check", "--class=LinkDeck"]
        if server.ON_PHONE or (hasattr(os, "geteuid") and os.geteuid() == 0):
            # Debian di HP (proot) / root: sandbox Chromium tidak tersedia
            args += ["--no-sandbox", "--test-type", "--disable-dev-shm-usage"]
        return args

    def launch_chromium(self) -> bool:
        with self.lock:
            if self.proc and self.proc.poll() is None:
                return True                    # jendela sudah terbuka
            try:
                self.proc = subprocess.Popen(self.chromium_args())
            except OSError as e:
                print("Chromium gagal dibuka:", e)
                return False
            proc = self.proc
        threading.Thread(target=self._watch_chromium, args=(proc, time.time()), daemon=True).start()
        return True

    def _watch_chromium(self, proc: subprocess.Popen, started: float) -> None:
        proc.wait()
        if self.quitting.is_set():
            return
        if time.time() - started < 3:
            self.detached.set()                # peluncur yang langsung keluar: jendela diurus proses lain
            return
        if self.keep_in_tray():
            self.told_once()
        else:
            self.quit()                        # tanpa tray: menutup jendela = keluar

    def run_chromium(self) -> bool:
        self.exe = find_chromium()
        if not self.exe:
            return False
        self.mode = "chromium"
        has_tray = self.make_tray()
        if not self.start_hidden or not has_tray:
            if not self.launch_chromium():
                self.mode = None
                return False
        if has_tray:
            self.tray.run()                    # blok di thread utama sampai Keluar
            if self.quitting.is_set():
                return True
            print("[tray]", self.tray.error or "ikon tray berhenti", flush=True)
            self.tray = None                   # ikon tray berhenti sendiri: lanjut tanpa tray
            self.launch_chromium()
        while not self.quitting.wait(0.5):     # tanpa tray: tutup jendela = keluar (lihat _watch_chromium)
            if self.detached.is_set():
                wait_forever(self.quitting)
                break
        return True

    # ---------- browser biasa
    def run_browser(self) -> None:
        self.mode = "browser"
        if not self.start_hidden:
            webbrowser.open(URL)
        if self.make_tray():
            self.tray.run()
            if self.quitting.is_set():
                return
        if self.start_hidden:
            webbrowser.open(URL)
        wait_forever(self.quitting)

    def run(self) -> None:
        choice = os.environ.get("LINKDECK_UI", "").lower()
        order = [self.run_chromium, self.run_webview] if sys.platform.startswith("linux") \
            else [self.run_webview, self.run_chromium]
        if choice == "webview":
            order = [self.run_webview]
        elif choice == "chromium":
            order = [self.run_chromium]
        elif choice == "browser":
            order = []
        for fn in order:
            if fn():
                return
        self.run_browser()


def find_chromium() -> str | None:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "microsoft-edge", "microsoft-edge-stable", "brave-browser"):
        p = shutil.which(name)
        if p:
            return p
    candidates = []
    if sys.platform == "win32":
        for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if base:
                candidates += [Path(base) / "Microsoft/Edge/Application/msedge.exe",
                               Path(base) / "Google/Chrome/Application/chrome.exe"]
    elif sys.platform == "darwin":
        candidates += [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                       Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                       Path("/Applications/Chromium.app/Contents/MacOS/Chromium")]
    return next((str(c) for c in candidates if c.exists()), None)


def wait_forever(stop: threading.Event | None = None) -> None:
    if SECONDARY:
        return
    print("LinkDeck tetap berjalan. Tekan Ctrl+C untuk berhenti.")
    try:
        (stop or threading.Event()).wait()
    except KeyboardInterrupt:
        pass


def call_running(path: str, payload: dict | None = None, timeout: float = 10) -> dict | None:
    """Panggil API LinkDeck yang sedang berjalan (instans lain). None bila tidak bisa."""
    try:
        info = json.loads((server.user_data_dir() / "session.json").read_text())
        req = urllib.request.Request(f"http://{server.HOST}:{info['port']}{path}",
                                     data=json.dumps(payload or {}).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-LinkDeck-Token": info["token"]})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def send_files(paths: list[str]) -> bool:
    """Kirim berkas ke HP lewat LinkDeck yang sedang berjalan. False bila LinkDeck belum berjalan."""
    r = call_running("/api/sendfiles", {"paths": paths}, timeout=600)
    return bool(r and r.get("ok"))


def main() -> None:
    if "--send" in sys.argv:                        # klik kanan → Kirim ke → LinkDeck (HP Android)
        paths = [os.path.abspath(p) for p in sys.argv[sys.argv.index("--send") + 1:] if os.path.exists(p)]
        if paths and send_files(paths):
            return
        os.environ["LINKDECK_PENDING"] = json.dumps(paths)   # belum berjalan: buka LinkDeck, kirim saat HP siap
        sys.argv = [sys.argv[0]]
    start_hidden = "--tray" in sys.argv             # jalan otomatis saat login: diam di tray
    setup_logging()
    server.OPEN_BROWSER = False
    global SECONDARY
    if linkdeck_running():
        if start_hidden:
            return                                  # sudah berjalan; jalan otomatis tidak perlu apa-apa
        r = call_running("/api/app/show")
        if r and r.get("ok") and r.get("shown"):
            return                                  # jendela instans pertama dimunculkan
        SECONDARY = True                            # instans lama tanpa /api/app/show: buka jendela biasa
        Desktop(False).run()
        return
    stop = start_server()
    if hasattr(signal, "SIGTERM"):     # ditutup dari luar: tetap bereskan mirror & adb
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    print(f"LinkDeck {server.VERSION} siap di {URL}")
    desk = Desktop(start_hidden)
    server.DESKTOP = desk
    try:
        desk.run()
    finally:
        stop()


if __name__ == "__main__":
    main()
