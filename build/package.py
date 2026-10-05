#!/usr/bin/env python3
"""
Kemas hasil PyInstaller (dist/LinkDeck) jadi berkas rilis di out/.
  windows      -> LinkDeck-<v>-windows-setup.exe + LinkDeck-<v>-windows-portable.zip
  macos-*      -> LinkDeck-<v>-macos-<arch>.dmg
  linux        -> linkdeck_<v>_amd64.deb + LinkDeck-<v>-x86_64.AppImage + LinkDeck-<v>-linux-x86_64.tar.gz
Juga menyalin paket agen HP (dist/linkdeck-agent_*.deb) ke out/.
"""
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from debtool import build_deb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
OUT = ROOT / "out"
ICONS = ROOT / "build" / "icons"
VERSION = os.environ.get("LINKDECK_VERSION") or (ROOT / "VERSION").read_text().strip()
DESKTOP = """[Desktop Entry]
Type=Application
Name=LinkDeck
GenericName=Jembatan HP dan PC
Comment=Tampilkan Android dan Debian dari HP di PC, monitor, atau TV
Exec={exec}
Icon=linkdeck
Terminal=false
Categories=Utility;Network;
StartupWMClass=LinkDeck
"""


def sh(*args, **kw):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kw)


def windows():
    iscc = shutil.which("iscc") or next((str(p) for p in (
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6/ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6/ISCC.exe") if p.exists()), None)
    if not iscc:
        raise SystemExit("Inno Setup (ISCC.exe) tidak ditemukan")
    sh(iscc, f"/DAppVersion={VERSION}", ROOT / "build/windows/linkdeck.iss")
    shutil.make_archive(str(OUT / f"LinkDeck-{VERSION}-windows-portable"), "zip", DIST, "LinkDeck")


def macos(arch):
    app = DIST / "LinkDeck.app"
    stage = ROOT / "build/dmg-stage"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    sh("ditto", app, stage / "LinkDeck.app")
    (stage / "Applications").symlink_to("/Applications")
    sh("codesign", "--force", "--deep", "--sign", "-", stage / "LinkDeck.app")  # tanda tangan ad-hoc
    dmg = OUT / f"LinkDeck-{VERSION}-macos-{arch}.dmg"
    sh("hdiutil", "create", "-volname", "LinkDeck", "-srcfolder", stage, "-ov", "-format", "UDZO", dmg)


def _walk(src: Path, prefix: str):
    for p in sorted(src.rglob("*")):
        rel = f"{prefix}/{p.relative_to(src).as_posix()}"
        if p.is_symlink():
            yield rel, None, 0, os.readlink(p)
        elif p.is_file():
            mode = 0o755 if os.access(p, os.X_OK) else 0o644
            yield rel, p.read_bytes(), mode, None


def linux():
    app = DIST / "LinkDeck"
    icon = (ICONS / "linkdeck-256.png").read_bytes()
    # .deb
    files = list(_walk(app, "opt/linkdeck"))
    files += [("usr/bin/linkdeck", None, 0, "/opt/linkdeck/LinkDeck"),
              ("usr/share/applications/linkdeck.desktop", DESKTOP.format(exec="/opt/linkdeck/LinkDeck").encode(), 0o644, None),
              ("usr/share/icons/hicolor/256x256/apps/linkdeck.png", icon, 0o644, None)]
    build_deb(OUT / f"linkdeck_{VERSION}_amd64.deb", {
        "Package": "linkdeck", "Version": VERSION, "Section": "utils", "Priority": "optional",
        "Architecture": "amd64", "Maintainer": "LinkDeck <linkdeck@localhost>", "Installed-Size": "auto",
        "Depends": "libc6 (>= 2.35), xclip | xsel | wl-clipboard",
        "Recommends": "chromium | google-chrome-stable | microsoft-edge-stable, android-sdk-platform-tools-common",
        "Description": "Jembatan layar, clipboard, dan berkas antara HP dan PC\n"
                       " Tampilkan Android (layar virtual) dan Debian XFCE dari HP di PC, monitor, atau TV.",
    }, files)
    # tar.gz portabel
    with tarfile.open(OUT / f"LinkDeck-{VERSION}-linux-x86_64.tar.gz", "w:gz") as t:
        t.add(app, arcname="LinkDeck")
    # AppImage
    appdir = ROOT / "build/LinkDeck.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(app, appdir / "usr/lib/linkdeck", symlinks=True)
    (appdir / "AppRun").write_text('#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\n'
                                   'exec "$HERE/usr/lib/linkdeck/LinkDeck" "$@"\n')
    (appdir / "AppRun").chmod(0o755)
    (appdir / "linkdeck.desktop").write_text(DESKTOP.format(exec="LinkDeck"))
    (appdir / "linkdeck.png").write_bytes(icon)
    tool = ROOT / "build/appimagetool"
    if not tool.exists():
        url = "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
        with urllib.request.urlopen(url, timeout=120) as r:
            tool.write_bytes(r.read())
        tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    env = {**os.environ, "ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1"}
    sh(tool, appdir, OUT / f"LinkDeck-{VERSION}-x86_64.AppImage", env=env)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    OUT.mkdir(exist_ok=True)
    if target == "windows":
        windows()
    elif target.startswith("macos-"):
        macos(target.split("-", 1)[1])
    elif target == "linux":
        linux()
    else:
        raise SystemExit("Pakai: package.py windows|linux|macos-arm64|macos-x86_64")
    for deb in DIST.glob("linkdeck-agent_*.deb"):
        shutil.copy2(deb, OUT / deb.name)
    print("Hasil:", *sorted(p.name for p in OUT.iterdir()), sep="\n  ")
