#!/usr/bin/env python3
"""
Bangun linkdeck-debian_<versi>_all.deb: aplikasi LinkDeck untuk Debian di arsitektur apa pun
(termasuk Debian 13 di HP, arm64). Isinya kode Python + antarmuka + scrcpy-server bawaan;
adb, scrcpy, dan pustaka Python diambil dari repositori Debian.

Butuh lebih dulu:  python build/fetch_deps.py linux   (noVNC, xterm.js, dan scrcpy-server)
Hasil: dist/linkdeck-debian_<versi>_all.deb
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from debtool import build_deb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VERSION = os.environ.get("LINKDECK_VERSION") or (ROOT / "VERSION").read_text().strip()
LIB = "usr/lib/linkdeck"
DESKTOP = """[Desktop Entry]
Type=Application
Name=LinkDeck
GenericName=Jembatan Android dan Debian
Comment=Layar baru, cermin, kamera, Mode Game, dan clipboard Android di Debian
Exec=linkdeck
Icon=linkdeck
Terminal=false
Categories=Utility;Network;
StartupWMClass=LinkDeck
"""


def walk(src: Path, prefix: str):
    for p in sorted(src.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            yield f"{prefix}/{p.relative_to(src).as_posix()}", p.read_bytes(), 0o644, None


def main() -> Path:
    jar, ver = ROOT / "vendor/scrcpy/scrcpy-server", ROOT / "vendor/scrcpy/VERSION"
    for need in (jar, ver, ROOT / "static/novnc/core/rfb.js", ROOT / "static/xterm/xterm.js"):
        if not need.exists():
            raise SystemExit(f"Tidak ada {need}. Jalankan dulu: python build/fetch_deps.py linux")
    files = []
    for name in ("app.py", "server.py", "features.py", "richclip.py", "debiantools.py", "tray.py", "mediadev.py",
                 "companionlink.py", "kvm.py", "notif.py", "pcclip.py"):
        files.append((f"{LIB}/{name}", (ROOT / name).read_bytes(), 0o644, None))
    apk = ROOT / "companion" / "linkdeck-companion.apk"
    if apk.exists():
        files.append((f"{LIB}/companion/{apk.name}", apk.read_bytes(), 0o644, None))
    files.append((f"{LIB}/VERSION", VERSION.encode() + b"\n", 0o644, None))
    files += list(walk(ROOT / "static", f"{LIB}/static"))
    files += [(f"{LIB}/bin/scrcpy-server", jar.read_bytes(), 0o644, None),
              (f"{LIB}/bin/VERSION", ver.read_bytes(), 0o644, None)]
    for deb in sorted((ROOT / "phone").glob("linkdeck-agent*.deb")):
        files.append((f"{LIB}/phone/{deb.name}", deb.read_bytes(), 0o644, None))
    for script in ("linkdeck", "linkdeck-scrcpy-build"):
        files.append((f"usr/bin/{script}", (ROOT / "debian-app" / script).read_bytes(), 0o755, None))
    files += [("usr/share/applications/linkdeck.desktop", DESKTOP.encode(), 0o644, None),
              ("usr/share/icons/hicolor/256x256/apps/linkdeck.png",
               (ROOT / "build/icons/linkdeck-256.png").read_bytes(), 0o644, None)]
    control = {
        "Package": "linkdeck-debian",
        "Version": VERSION,
        "Section": "utils",
        "Priority": "optional",
        "Architecture": "all",
        "Maintainer": "LinkDeck <linkdeck@users.noreply.github.com>",
        "Installed-Size": "auto",
        "Depends": "python3 (>= 3.11), python3-aiohttp, python3-pyperclip, python3-qrcode, "
                   "adb | android-tools-adb, xclip | xsel | wl-clipboard",
        "Recommends": "scrcpy, chromium, python3-xlib, python3-pynput, python3-pystray, python3-pil, pulseaudio-utils, python3-av",
        "Conflicts": "linkdeck",
        "Description": "LinkDeck untuk Debian (semua arsitektur, termasuk HP arm64)\n"
                       " Tampilkan Android (layar baru, cermin, kamera, Mode Game) dan sinkronkan\n"
                       " clipboard Android di Debian. Versi tanpa biner per arsitektur dari LinkDeck.",
    }
    out = build_deb(ROOT / "dist" / f"linkdeck-debian_{VERSION}_all.deb", control, files)
    print(out)
    return out


if __name__ == "__main__":
    main()
