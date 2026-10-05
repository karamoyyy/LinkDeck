#!/usr/bin/env python3
"""
Unduh dependensi yang dibundel ke aplikasi:
  - scrcpy (sudah termasuk adb) untuk OS target -> vendor/scrcpy/
  - noVNC + xterm.js -> static/
Pakai:  python build/fetch_deps.py windows|linux|macos-arm64|macos-x86_64
Versi scrcpy: env SCRCPY_VERSION (mis. 4.1), default rilis terbaru.
"""
import hashlib
import io
import os
import shutil
import stat
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "scrcpy"
REPO = "https://github.com/Genymobile/scrcpy/releases"
ASSET = {
    "windows": "scrcpy-win64-v{v}.zip",
    "linux": "scrcpy-linux-x86_64-v{v}.tar.gz",
    "macos-arm64": "scrcpy-macos-aarch64-v{v}.tar.gz",
    "macos-x86_64": "scrcpy-macos-x86_64-v{v}.tar.gz",
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "linkdeck-build"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def latest_version() -> str:
    req = urllib.request.Request(f"{REPO}/latest", headers={"User-Agent": "linkdeck-build"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl().rstrip("/").rsplit("/v", 1)[1]


def fetch_scrcpy(target: str) -> None:
    v = os.environ.get("SCRCPY_VERSION") or latest_version()
    name = ASSET[target].format(v=v)
    print(f"scrcpy {v}: {name}")
    data = get(f"{REPO}/download/v{v}/{name}")
    sums = get(f"{REPO}/download/v{v}/SHA256SUMS.txt").decode()
    want = next((l.split()[0] for l in sums.splitlines() if l.strip().endswith(name)), None)
    got = hashlib.sha256(data).hexdigest()
    if not want or want != got:
        raise SystemExit(f"Checksum {name} tidak cocok ({got} != {want})")
    shutil.rmtree(VENDOR, ignore_errors=True)
    VENDOR.mkdir(parents=True)
    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for m in z.infolist():
                rel = m.filename.split("/", 1)[1] if "/" in m.filename else m.filename
                if rel and not m.is_dir():
                    dest = VENDOR / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(z.read(m))
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
            for m in t.getmembers():
                rel = m.name.split("/", 1)[1] if "/" in m.name else ""
                if rel and m.isfile() and ".." not in rel:
                    dest = VENDOR / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(t.extractfile(m).read())
                    if m.mode & 0o111:
                        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    for junk in ("scrcpy-console.bat", "scrcpy-noconsole.vbs", "open_a_terminal_here.bat", "icon.png"):
        (VENDOR / junk).unlink(missing_ok=True)
    (VENDOR / "VERSION").write_text(v)
    print("  ->", sorted(p.name for p in VENDOR.iterdir()))


def fetch_assets() -> None:
    sys.path.insert(0, str(ROOT))
    import server
    server.NOVNC_DIR = ROOT / "static" / "novnc"
    server.XTERM_DIR = ROOT / "static" / "xterm"
    for d in (server.NOVNC_DIR, server.XTERM_DIR):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    server.download_assets()
    print("noVNC", server.NOVNC_VERSION, "dan xterm.js ->", ROOT / "static")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ASSET:
        raise SystemExit(f"Pakai: fetch_deps.py {'|'.join(ASSET)}")
    fetch_scrcpy(sys.argv[1])
    fetch_assets()
