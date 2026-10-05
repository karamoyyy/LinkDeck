#!/usr/bin/env python3
"""Bangun linkdeck-agent_<versi>_all.deb untuk Debian di HP.  Hasil: dist/ dan phone/."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from debtool import build_deb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VERSION = os.environ.get("LINKDECK_VERSION") or (ROOT / "VERSION").read_text().strip()


def main() -> Path:
    files = [("usr/lib/linkdeck-agent/agent.py", (ROOT / "phone/agent.py").read_bytes(), 0o755, None)]
    for f in sorted((ROOT / "phone/bin").iterdir()):
        files.append((f"usr/bin/{f.name}", f.read_bytes(), 0o755, None))
    files.append(("usr/share/doc/linkdeck-agent/README", (
        "LinkDeck agent\n\nJalankan: linkdeck-start  (atau linkdeck-start bagikan)\n"
        "Ubah PIN/sandi/resolusi: linkdeck-setup\nBerhenti: linkdeck-stop\n").encode(), 0o644, None))
    control = {
        "Package": "linkdeck-agent",
        "Version": VERSION,
        "Section": "x11",
        "Priority": "optional",
        "Architecture": "all",
        "Maintainer": "LinkDeck <linkdeck@localhost>",
        "Installed-Size": "auto",
        "Depends": "python3, python3-aiohttp, python3-xlib, xclip, openssl, x11-xserver-utils, tigervnc-standalone-server, "
                   "tigervnc-scraping-server, tigervnc-tools, dbus-x11, xdg-utils, procps",
        "Recommends": "xfce4, pulseaudio-utils",
        "Description": "Agen LinkDeck: tampilkan desktop Debian di PC, monitor, atau TV\n"
                       " Menyediakan desktop XFCE lewat VNC, clipboard dua arah, kirim berkas,\n"
                       " dan membuka tautan dari aplikasi LinkDeck di PC.",
    }
    out = build_deb(ROOT / "dist" / f"linkdeck-agent_{VERSION}_all.deb", control, files)
    (ROOT / "phone").mkdir(exist_ok=True)
    for old in (ROOT / "phone").glob("linkdeck-agent*.deb"):
        old.unlink()
    shutil.copy2(out, ROOT / "phone" / out.name)   # ikut dibundel ke aplikasi desktop
    print(out)
    return out


if __name__ == "__main__":
    main()
