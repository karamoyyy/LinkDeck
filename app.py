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


def run_webview() -> bool:
    try:
        import webview
    except ImportError:
        return False
    gui = {"win32": "edgechromium", "darwin": "cocoa"}.get(sys.platform)
    api = Api()
    try:
        api._window = webview.create_window(
            "LinkDeck", URL, width=1440, height=940, min_size=(900, 640),
            js_api=api, background_color="#2a1f25", text_select=True)
        store = server.user_data_dir() / "webview"
        store.mkdir(parents=True, exist_ok=True)
        webview.start(gui=gui, private_mode=False, storage_path=str(store))
        return True
    except Exception as e:
        print("pywebview gagal:", e)
        return False


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


def run_chromium() -> bool:
    exe = find_chromium()
    if not exe:
        return False
    profile = server.user_data_dir() / "chromium-profile"
    profile.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.Popen([exe, f"--app={URL}", f"--user-data-dir={profile}",
                                 "--window-size=1440,940", "--no-first-run",
                                 "--no-default-browser-check", "--class=LinkDeck"])
    except OSError:
        return False
    started = time.time()
    proc.wait()
    # Peluncur yang langsung keluar (mis. snap) berarti jendela diurus proses lain
    if time.time() - started < 3:
        wait_forever()
    return True


def wait_forever() -> None:
    if SECONDARY:
        return
    print("LinkDeck tetap berjalan. Tekan Ctrl+C untuk berhenti.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


def open_ui() -> None:
    choice = os.environ.get("LINKDECK_UI", "").lower()
    if sys.platform == "linux":
        order = [run_chromium, run_webview]
    else:
        order = [run_webview, run_chromium]
    if choice == "webview":
        order = [run_webview]
    elif choice == "chromium":
        order = [run_chromium]
    elif choice == "browser":
        order = []
    for fn in order:
        if fn():
            return
    webbrowser.open(URL)
    wait_forever()


def main() -> None:
    setup_logging()
    server.OPEN_BROWSER = False
    global SECONDARY
    if linkdeck_running():          # sudah ada yang jalan: cukup buka jendelanya
        SECONDARY = True
        open_ui()
        return
    stop = start_server()
    if hasattr(signal, "SIGTERM"):     # ditutup dari luar: tetap bereskan mirror & adb
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    print(f"LinkDeck {server.VERSION} siap di {URL}")
    try:
        open_ui()
    finally:
        stop()


if __name__ == "__main__":
    main()
