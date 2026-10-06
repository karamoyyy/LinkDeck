# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec LinkDeck.  Jalankan dari root proyek:  pyinstaller build/linkdeck.spec --noconfirm
import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICONS = ROOT / "build" / "icons"
VENDOR = ROOT / "vendor" / "scrcpy"
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

datas = [
    (str(ROOT / "static"), "static"),
    (str(ROOT / "VERSION"), "."),
]

datas += [(str(p), "phone") for p in (ROOT / "phone").glob("linkdeck-agent*.deb")]

binaries = []
if VENDOR.is_dir():
    for f in VENDOR.iterdir():
        is_bin = f.suffix.lower() in (".exe", ".dll") or (not IS_WIN and os.access(f, os.X_OK))
        (binaries if is_bin else datas).append((str(f), "bin"))

hidden = ["pyperclip", "pcclip", "qrcode", "qrcode.image.svg", "notif", "kvm", "pynput.keyboard", "pynput.mouse"]
# backend pynput disebut eksplisit: hook bawaannya butuh layar aktif saat build (tidak ada di CI)
_pyn = {"win32": "win32", "darwin": "darwin"}.get(sys.platform, "xorg")
hidden += [f"pynput.keyboard._{_pyn}", f"pynput.mouse._{_pyn}", f"pynput._util.{_pyn}"]
if _pyn == "xorg":
    hidden += ["pynput._util.xorg_keysyms", "Xlib", "Xlib.display", "Xlib.ext.xtest", "Xlib.ext.record", "Xlib.XK", "Xlib.keysymdef.xkb"]
if _pyn == "win32":
    hidden += ["pynput._util.win32_vks"]
if _pyn == "darwin":
    hidden += ["pynput._util.darwin_vks", "Quartz"]
excludes = ["tkinter", "unittest", "pydoc_data", "test"]
if sys.platform.startswith("linux"):
    excludes.append("webview")      # Linux memakai Chrome/Chromium mode aplikasi
else:
    hidden.append("webview")

a = Analysis([str(ROOT / "app.py")], pathex=[str(ROOT)], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=excludes, noarchive=False)
pyz = PYZ(a.pure)

exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LinkDeck",
          console=False, icon=str(ICONS / ("linkdeck.icns" if IS_MAC else "linkdeck.ico")),
          upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="LinkDeck", upx=False)

if IS_MAC:
    version = (ROOT / "VERSION").read_text().strip()
    app = BUNDLE(coll, name="LinkDeck.app", icon=str(ICONS / "linkdeck.icns"),
                 bundle_identifier="id.linkdeck.desktop",
                 info_plist={
                     "CFBundleShortVersionString": version,
                     "CFBundleVersion": version,
                     "NSHighResolutionCapable": True,
                     "LSMinimumSystemVersion": "11.0",
                 })
